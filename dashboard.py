import os
import re
import json
import uuid
import time
import requests
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from flask_cors import CORS
import pdfplumber
import datetime
import threading as _threading
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
_db_lock = _threading.Lock()

app = Flask(__name__, static_folder="interview_app")
CORS(app)

# ================= CONFIG =====================
# ── STEP 1: Google Gemini (Primary — FREE) ─────────────────────
# Get key: aistudio.google.com → "Get API Key" (30 seconds, no credit card)
# Free tier: 1500 req/day per key — add keys from multiple Google accounts!
# 3 accounts × 1500 = 4500 free requests/day = enough for 500 students
# ── Gemini keys (get free at aistudio.google.com) ──────────────
# Paste your AIza... keys below. Each Google account = 1500 req/day free.
# Leave empty to use Groq only (already working with your 3 Groq keys).
GEMINI_API_KEYS = [
    os.environ.get("GEMINI_API_KEY_1", ""),
    os.environ.get("GEMINI_API_KEY_2", ""),
    os.environ.get("GEMINI_API_KEY_3", ""),
]
GEMINI_API_KEYS = [k for k in GEMINI_API_KEYS if k and len(k) > 20 and k.startswith("AIza")]
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL    = "gemini-1.5-flash"      # fast, free, high quality
GEMINI_FALLBACK = "gemini-1.5-flash-8b"  # lighter fallback

# ── STEP 2: Groq (Secondary fallback — FREE) ───────────────────
# Get key: console.groq.com → "Create API Key" (30 seconds)
# Add keys from multiple free accounts for more quota
GROQ_API_KEYS = [
    os.environ.get("GROQ_API_KEY_1", ""),
    os.environ.get("GROQ_API_KEY_2", ""),
    os.environ.get("GROQ_API_KEY_3", ""),
]
GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k]  # remove empty
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODELS   = [
    "llama-3.3-70b-versatile",   # primary — confirmed working
    "llama-3.1-8b-instant",      # fast fallback — confirmed working
    "llama-3.1-70b-versatile",   # extra fallback
    # llama3-8b-8192 and mixtral-8x7b-32768 DECOMMISSIONED — do not add
]
# NOTE: llama3-8b-8192 and mixtral-8x7b-32768 are DECOMMISSIONED by Groq — do not add back

# ── STEP 3: MongoDB Atlas (Database — FREE) ────────────────────
MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    ""
)

# ── App config ─────────────────────────────────────────────────
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")

# ── Anthropic API key (for Indeed MCP) — get at console.anthropic.com ──
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ══════════════════════════════════════════════════════════════
#  FREE JOB APIs — all give DIRECT apply links, no credit card
#  System tries each in order, falls back to next if quota hit
# ══════════════════════════════════════════════════════════════

# 1. Adzuna — 1000 req/DAY free, covers India ✅ BEST FREE OPTION
#    Get key: developer.adzuna.com → Register → My Apps → Create App
#    Takes 2 minutes, no credit card
ADZUNA_APP_ID  = os.environ.get("ADZUNA_APP_ID",  "")   # ← paste App ID here
ADZUNA_API_KEY = os.environ.get("ADZUNA_API_KEY", "")   # ← paste API Key here

# 2. JSearch (RapidAPI) — 200 req/MONTH free
#    Get key: rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch → Subscribe FREE
JSEARCH_API_KEY = os.environ.get("JSEARCH_API_KEY", "")

# 3. HasData Indeed + Glassdoor — 1000 credits free (no credit card)
#    Get key: hasdata.com → Sign up → Dashboard → copy API key
#    Endpoints: /scrape/indeed/listing  and  /scrape/glassdoor/listing
HASDATA_API_KEY = os.environ.get("HASDATA_API_KEY", "")

# 4. ScrapeOps Indeed — 1000 free credits
#    Get key: scrapeops.io → Sign up free → copy API key
SCRAPEOPS_API_KEY = os.environ.get("SCRAPEOPS_API_KEY", "")

# ── Email (optional — Gmail SMTP) ──────────────────────────────
EMAIL_ENABLED  = os.environ.get("EMAIL_ENABLED", "false").lower() == "true"
EMAIL_SENDER   = os.environ.get("EMAIL_SENDER",   "your_gmail@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "your_app_password_here")
EMAIL_SUBJECT  = "Your AGI Career Report & Mock Interview — {name}"


# ================= AI CLIENT (Gemini multi-key + Groq multi-key rotation) ============
class AIClient:
    """
    Primary:  Gemini 1.5 Flash — rotates across ALL your Gemini keys
              When key 1 hits daily limit → auto-switch to key 2 → key 3
    Fallback: Groq — rotates across ALL your Groq keys + models
    Result:   System NEVER stops. 3 Gemini + 3 Groq = 6 API sources.
    """
    def __init__(self):
        self.gemini_keys    = GEMINI_API_KEYS
        self.gemini_idx     = 0
        self.gemini_ok      = len(GEMINI_API_KEYS) > 0
        self.groq_keys      = GROQ_API_KEYS
        self.groq_ok        = bool(GROQ_API_KEYS)
        self.groq_key_idx   = 0
        self.groq_model_idx = 0
        # Per-key request counters for rate limiting (15 req/min per key)
        self.req_counts     = [0] * max(len(GEMINI_API_KEYS), 1)
        self.last_minutes   = [time.time()] * max(len(GEMINI_API_KEYS), 1)

        if self.gemini_ok:
            print(f"  [AI] ✅ Gemini active ({len(self.gemini_keys)} keys) + Groq fallback ({len(self.groq_keys)} keys)")
            print(f"  [AI]    Gemini capacity: {len(self.gemini_keys) * 1500}/day | Groq: unlimited rotation")
        elif self.groq_ok:
            print(f"  [AI] ✅ Groq only — {GROQ_MODELS[0]} ({len(self.groq_keys)} keys)")
            print(f"  [AI]    Add Gemini keys at aistudio.google.com for more speed")
        else:
            print("  [AI] ⚠️  No API keys! Add GEMINI_API_KEY_1 or GROQ_API_KEY_1")

    def _rate_limit_gemini(self, idx):
        """Stay under 14 req/min for this Gemini key."""
        self.req_counts[idx] += 1
        if self.req_counts[idx] >= 14:
            elapsed = time.time() - self.last_minutes[idx]
            if elapsed < 62:
                wait = 63 - elapsed
                print(f"  [Gemini key {idx+1}] Rate limit — waiting {wait:.0f}s...")
                time.sleep(wait)
            self.req_counts[idx]   = 0
            self.last_minutes[idx] = time.time()

    def call(self, messages, temperature=0.2, max_tokens=4000, retries=4):
        # Try each Gemini key in order — skip permanently failed keys
        if self.gemini_ok and self.gemini_keys:
            attempted = 0
            for i in range(len(self.gemini_keys)):
                idx    = (self.gemini_idx + i) % len(self.gemini_keys)
                result = self._gemini_call(messages, temperature, max_tokens, idx)
                if result:
                    self.gemini_idx = idx  # remember last working key
                    return result
                attempted += 1
                if attempted < len(self.gemini_keys):
                    print(f"  [AI] Gemini key {idx+1} failed — trying key {((idx+1)%len(self.gemini_keys))+1}...")

            # All keys failed — disable Gemini permanently for this session
            print(f"  [AI] All {len(self.gemini_keys)} Gemini keys failed — using Groq only for this session")
            self.gemini_ok = False

        # Groq fallback
        if self.groq_ok:
            return self._groq_call(messages, temperature, max_tokens)

        print("  [AI] ❌ All API keys exhausted.")
        return None

    def _gemini_call(self, messages, temperature, max_tokens, key_idx=0):
        key = self.gemini_keys[key_idx]
        # Convert OpenAI-style messages → Gemini format
        contents    = []
        system_text = ""
        for m in messages:
            role = m.get("role", "user")
            text = m.get("content", "")
            if role == "system":
                system_text = text
            elif role == "user":
                full = (system_text + "\n\n" + text).strip() if system_text else text
                contents.append({"role": "user", "parts": [{"text": full}]})
                system_text = ""
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": text}]})

        if not contents:
            contents = [{"role": "user", "parts": [{"text": messages[-1].get("content", "")}]}]

        model = GEMINI_MODEL
        for attempt in range(4):
            try:
                self._rate_limit_gemini(key_idx)
                resp = requests.post(
                    f"{GEMINI_BASE_URL}/{model}:generateContent?key={key}",
                    json={"contents": contents,
                          "generationConfig": {"temperature": temperature,
                                               "maxOutputTokens": max_tokens}},
                    timeout=45
                )
                if resp.status_code == 200:
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                elif resp.status_code == 429:
                    # Daily quota hit for this key — rotate to next key
                    print(f"  [Gemini key {key_idx+1}] Daily quota hit — rotating to next key...")
                    return None
                elif resp.status_code == 404:
                    print(f"  [Gemini key {key_idx+1}] ❌ Invalid key — skipping")
                    return None
                elif resp.status_code in (400, 403):
                    print(f"  [Gemini key {key_idx+1}] ❌ HTTP {resp.status_code} — skipping")
                    return None
                else:
                    print(f"  [Gemini key {key_idx+1}] HTTP {resp.status_code}")
                    time.sleep(5)
            except Exception as e:
                print(f"  [Gemini key {key_idx+1}] Error: {e}")
                time.sleep(3)
        return None

    def _groq_call(self, messages, temperature, max_tokens, retries=6):
        keys_tried = set()
        for attempt in range(retries):
            key_idx   = self.groq_key_idx % len(self.groq_keys)
            key       = self.groq_keys[key_idx]
            model     = GROQ_MODELS[self.groq_model_idx % len(GROQ_MODELS)]
            try:
                resp = requests.post(
                    f"{GROQ_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json={"model": model, "messages": messages,
                          "temperature": temperature, "max_tokens": max_tokens},
                    timeout=45
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                elif resp.status_code == 429:
                    err_body = resp.json().get("error", {})
                    err_msg  = err_body.get("message", "")
                    # Daily quota exhausted — no point retrying this key
                    if "day" in err_msg.lower() or "quota" in err_msg.lower():
                        print(f"  [Groq] Daily quota hit on key #{key_idx+1} — rotating key")
                        keys_tried.add(key_idx)
                        self.groq_key_idx += 1
                        # If all keys exhausted for today, stop immediately
                        if len(keys_tried) >= len(self.groq_keys):
                            print("  [Groq] All keys daily quota exhausted — using fallback")
                            return None
                    else:
                        print(f"  [Groq] Rate limit on key #{key_idx+1} — rotating...")
                        self.groq_key_idx   += 1
                        self.groq_model_idx += 1
                        time.sleep(3)  # short wait only
                elif resp.status_code == 400:
                    err_msg = resp.json().get("error", {}).get("message", "")
                    if "decommissioned" in err_msg or "deprecated" in err_msg or "not supported" in err_msg:
                        print(f"  [Groq] ⚠️  Model {model} decommissioned — skipping")
                        self.groq_model_idx += 1
                        if self.groq_model_idx % len(GROQ_MODELS) == 0:
                            return None  # all models decommissioned
                    else:
                        print(f"  [Groq] HTTP 400: {err_msg[:100]}")
                        return None  # bad request — don't retry
                elif resp.status_code == 401:
                    print(f"  [Groq] ❌ Invalid key #{key_idx+1} — rotating...")
                    self.groq_key_idx += 1
                    if self.groq_key_idx >= len(self.groq_keys):
                        return None
                else:
                    print(f"  [Groq] HTTP {resp.status_code}: {resp.text[:100]}")
                    time.sleep(3)
            except Exception as e:
                print(f"  [Groq] Error (attempt {attempt+1}): {e}")
                time.sleep(2)
        print("  [AI] Groq retries exhausted — using fallback")
        return None

# Global AI client
nvidia_client = AIClient()   # kept as nvidia_client so all existing code works
groq_rotator  = nvidia_client





INTERVIEW_SESSIONS = {}

# ================= UTILS =====================
def safe_cell(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(map(str, value))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)

def groq_json(prompt, temperature=0.2, max_tokens=4000):
    try:
        raw = groq_rotator.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        if not raw:
            return None
        # Clean invalid control characters (causes JSON parse errors)
        import re as _re
        raw = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw)
        # Strip markdown fences
        if "```" in raw:
            raw = _re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        # Extract JSON object
        s = raw.find('{'); e = raw.rfind('}') + 1
        if s != -1 and e > s:
            raw = raw[s:e]
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"groq_json parse error: {e}")
        return None
    except Exception as e:
        print("groq_json error:", e)
        return None


def groq_text(prompt, temperature=0.5):
    try:
        raw = groq_rotator.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=1000
        )
        return raw.strip() if raw else "Keep learning and growing every day!"
    except Exception as e:
        print("groq_text error:", e)
        return "Keep learning and growing every day!"

# ================= PDF =====================
def extract_text_from_pdf(file):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                if page.extract_text():
                    text += page.extract_text() + "\n"
    except Exception as e:
        print("PDF error:", e)
    return text

# ================= SECTION A: BASIC DETAILS =====================
def extract_basic_details(text, filename):
    email = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    phone = re.findall(r"\+?\d[\d\s\-]{8,15}", text)
    name = text.strip().split("\n")[0][:60]
    cgpa_match = re.findall(r"(?:CGPA|GPA|cgpa|gpa)[:\s]*([0-9]+\.?[0-9]*)", text)
    percent_match = re.findall(r"([0-9]+\.?[0-9]*)\s*%", text)
    degree_match = re.findall(
        r"(B\.?Tech|M\.?Tech|B\.?E|M\.?E|BCA|MCA|B\.?Sc|M\.?Sc|MBA|B\.?Com|Ph\.?D)[^\n]*",
        text, re.IGNORECASE
    )
    return {
        "filename": filename,
        "name": name,
        "email": email[0] if email else "",
        "phone": phone[0] if phone else "",
        "cgpa": cgpa_match[0] if cgpa_match else (percent_match[0] + "%" if percent_match else ""),
        "education": degree_match[0] if degree_match else "Not detected"
    }

# ================= SECTION A: AI ANALYSIS =====================
def ai_analyze(resume_text):
    print("  [A] Running deep resume analysis...")

    # Use up to 4000 chars for richer context
    resume_chunk = resume_text[:4000]

    prompt = f"""You are an expert resume analyst. Read this resume carefully and extract EVERYTHING needed to generate personalized interview questions.

RESUME:
{resume_chunk}

Return ONLY valid JSON. Be very specific — do NOT use generic labels.

{{
  "domain": "The candidate's primary field — e.g. 'Physics', 'Machine Learning', 'Finance', 'Civil Engineering', 'Biology', 'Marketing', 'Law', 'Mechanical Engineering', etc.",
  "skills": ["List every specific skill, tool, technology, subject, technique, language, framework mentioned. Be exhaustive. E.g. for physics: ['Quantum Mechanics', 'Thermodynamics', 'MATLAB', 'Spectroscopy']. For CS: ['Python', 'PyTorch', 'REST APIs']. For finance: ['DCF Valuation', 'Financial Modelling', 'Excel']"],
  "subjects_studied": ["Key academic subjects from their degree — e.g. ['Electromagnetic Theory', 'Signals and Systems'] or ['Corporate Finance', 'Econometrics']"],
  "projects": ["Brief title of each project — e.g. 'Fingerprint matching using Deep Learning', 'Quantum dot synthesis experiment'"],
  "tools_and_software": ["Every tool, software, instrument, library mentioned"],
  "experience_context": "1 sentence describing their work/research/internship experience if any",
  "strengths": "2 specific sentences about what makes this candidate strong",
  "weaknesses": "2 kind, constructive sentences about areas to grow",
  "skill_gaps": "Comma-separated skills missing for their target role",
  "achievements": "Key achievements as bullet points",
  "career_fit": ["3-5 specific job titles matching their background"],
  "education": "Full degree name and institution",
  "confidence_level": "High or Medium or Low"
}}

CRITICAL: The 'skills' array must contain real, specific items from THIS resume — not placeholders or generic terms."""

    result = groq_json(prompt, max_tokens=2000)
    if not result:
        print("  [A] Groq failed — returning empty analysis")
        return {
            "domain": "General", "skills": [], "subjects_studied": [],
            "projects": [], "tools_and_software": [],
            "experience_context": "", "strengths": "", "weaknesses": "",
            "skill_gaps": "", "achievements": "", "career_fit": [],
            "education": "", "confidence_level": "Medium"
        }

    # Merge tools and subjects into skills so question generator has full picture
    all_skills = result.get("skills", [])
    for extra in result.get("subjects_studied", []) + result.get("tools_and_software", []):
        if extra and extra not in all_skills:
            all_skills.append(extra)
    result["skills"] = all_skills

    print(f"  [A] Domain: {result.get('domain','?')} | Skills: {all_skills[:5]} ...")
    return result

# ================= SECTION B: JOB FETCH (FAST - only 3 calls) =====================
def calculate_match_percent(job_description, candidate_skills):
    """Calculate real match % by counting skill keywords found in job description."""
    if not job_description or not candidate_skills:
        return 0
    desc_lower = job_description.lower()
    skills_list = [s.strip().lower() for s in candidate_skills if len(s.strip()) > 1]
    if not skills_list:
        return 0
    matched = sum(1 for skill in skills_list if skill in desc_lower)
    pct = round((matched / len(skills_list)) * 100)
    return min(pct, 99)  # cap at 99%


def fetch_jobs_from_google(query, location="India"):
    """
    Scrape Google Jobs search results — free, no API key needed.
    Uses Google's public job search endpoint.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # Google Jobs search URL
        search_query = f"{query} jobs {location}".replace(" ", "+")
        url = f"https://www.google.com/search?q={search_query}&ibp=htl;jobs"

        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []

        # Parse job titles and companies from Google Jobs HTML
        text = resp.text
        jobs = []

        # Extract job snippets using regex patterns
        import re
        # Look for job data in the page
        title_patterns = re.findall(r'"([^"]{5,60}(?:Engineer|Developer|Scientist|Analyst|Manager|Specialist|Designer|Consultant)[^"]{0,30})"', text)
        company_patterns = re.findall(r'"([A-Z][a-zA-Z\s&]{2,30}(?:Inc|Ltd|Pvt|Technologies|Solutions|Systems|Services|Labs|AI|Tech)[^"]{0,10})"', text)

        seen = set()
        for i, title in enumerate(title_patterns[:10]):
            if title in seen: continue
            seen.add(title)
            company = company_patterns[i] if i < len(company_patterns) else "Company"
            q = f"{title} {company}".replace(" ", "+")
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "experience": "Fresher / Entry",
                "description": f"{title} role at {company}",
                "url": f"https://www.google.com/search?q={q}+jobs+apply",
                "match": "0%"
            })

        print(f"  [B] Google Jobs: {len(jobs)} results for '{query}'")
        return jobs[:8]
    except Exception as e:
        print(f"  [B] Google Jobs error: {e}")
        return []


def fetch_jobs_from_indeed(analysis):
    """
    Fetch real jobs from Indeed via the Claude MCP connector.
    This is called from a separate /fetch_indeed_jobs endpoint
    because MCP tools can only be called from Claude context, not Flask.
    Falls back gracefully if Indeed is not connected.
    """
    # Indeed MCP is only available in Claude context
    # Flask calls /fetch_indeed_jobs which proxies through Claude API
    domain  = analysis.get("domain", "General")
    skills  = analysis.get("skills", [])
    career  = analysis.get("career_fit", ["Software Engineer"])
    role    = career[0] if career else "Engineer"
    skill_str = ", ".join(skills[:4]) if skills else domain

    try:
        # Call our own /fetch_indeed_jobs endpoint
        resp = requests.post(
            f"{BASE_URL}/fetch_indeed_jobs",
            json={"query": f"{role} {skill_str}", "location": "India"},
            timeout=15
        )
        if resp.status_code == 200:
            jobs = resp.json().get("jobs", [])
            if jobs:
                print(f"  [B] Indeed: {len(jobs)} real jobs fetched")
                return jobs
    except Exception as e:
        print(f"  [B] Indeed proxy error: {e}")

    return []


def fetch_jobs_from_resume(analysis):
    """
    3-tier job fetching — uses 1 API credit per resume (not 15):
    1. RapidAPI Batch (JSearch/Adzuna) → up to 15 real live jobs in ONE call
    2. Groq AI                         → fills remaining slots with AI-generated jobs
    3. Merge + gap analysis            → combine real + AI jobs, rank by match %
    """
    domain = analysis.get("domain", "General")
    career = analysis.get("career_fit", ["Engineer"])
    skills = analysis.get("skills", [])

    # ── Tier 1: Batch fetch real jobs (1 API call only) ──────────
    any_key = JSEARCH_API_KEY or ADZUNA_APP_ID or HASDATA_API_KEY or SCRAPEOPS_API_KEY
    real_jobs = []
    if any_key:
        print("  [B] Fetching real jobs via RapidAPI (1 batch call)...")
        real_jobs = fetch_real_jobs_batch(domain, career, skills)
        if real_jobs:
            # Calculate proper match % for real jobs
            for job in real_jobs:
                desc = job.get("description","") + " " + job.get("title","")
                calc = calculate_match_percent(desc, skills)
                job["match"] = f"{max(calc, 15)}%"
            print(f"  [B] ✅ {len(real_jobs)} real jobs with direct apply links")

    # ── Tier 2: Groq AI fills the rest ───────────────────────────
    groq_jobs = fetch_jobs_from_groq(analysis)

    # ── Tier 3: Merge — real jobs first, then Groq fills to 15 ──
    combined = real_jobs[:]
    seen_titles = {j.get("title","").lower() for j in combined}
    for job in groq_jobs:
        if job.get("title","").lower() not in seen_titles:
            combined.append(job)
            seen_titles.add(job.get("title","").lower())
        if len(combined) >= 15:
            break

    combined.sort(
        key=lambda j: int(str(j.get("match","0%")).replace("%","").strip() or "0"),
        reverse=True
    )
    print(f"  [B] Final: {len(combined)} jobs ({len(real_jobs)} real + {len(combined)-len(real_jobs)} AI)")
    return combined[:15]



# Domain → real Indian employer map
# ── Indian Startup Hub — used across ALL domains ─────────────────────────────
INDIA_STARTUPS = [
    # Bengaluru startups
    ("Razorpay",       "https://razorpay.com/jobs",                   "Bengaluru"),
    ("Freshworks",     "https://www.freshworks.com/company/careers",  "Bengaluru"),
    ("Zepto",          "https://www.zepto.team/jobs",                 "Bengaluru"),
    ("Meesho",         "https://meesho.io/jobs",                      "Bengaluru"),
    ("Cred",           "https://careers.cred.club",                   "Bengaluru"),
    ("Darwinbox",      "https://darwinbox.com/careers",               "Bengaluru"),
    ("Unacademy",      "https://unacademy.com/careers",               "Bengaluru"),
    ("Scaler",         "https://www.scaler.com/careers",              "Bengaluru"),
    ("BrowserStack",   "https://www.browserstack.com/careers",        "Bengaluru"),
    ("Postman",        "https://www.postman.com/company/careers",     "Bengaluru"),
    ("CleverTap",      "https://clevertap.com/careers",               "Bengaluru"),
    ("Chargebee",      "https://www.chargebee.com/jobs",              "Bengaluru"),
    ("Licious",        "https://www.licious.in/blog/post/career",     "Bengaluru"),
    ("Rapido",         "https://rapido.bike/careers",                 "Bengaluru"),
    ("Koo",            "https://www.kooapp.com/careers",              "Bengaluru"),
    ("GoComet",        "https://gocomet.com/careers",                 "Bengaluru"),
    ("Zetwerk",        "https://www.zetwerk.com/careers",             "Bengaluru"),
    ("InstaBase",      "https://instabase.com/careers",               "Bengaluru"),
    ("Haptik",         "https://www.haptik.ai/careers",               "Bengaluru"),
    ("Slintel",        "https://www.slintel.com/careers",             "Bengaluru"),
    # Hyderabad startups
    ("HealthifyMe",    "https://www.healthifyme.com/careers",         "Hyderabad"),
    ("Slice",          "https://sliceit.com/careers",                 "Hyderabad"),
    ("Darwinbox",      "https://darwinbox.com/careers",               "Hyderabad"),
    ("FabIndia Tech",  "https://www.fabindia.com/careers",            "Hyderabad"),
    ("Keka HR",        "https://www.keka.com/careers",                "Hyderabad"),
    ("Ameyo",          "https://www.ameyo.com/careers",               "Hyderabad"),
    ("NxtWave",        "https://www.ccbp.in/careers",                 "Hyderabad"),
    ("Mihup",          "https://mihup.com/careers",                   "Hyderabad"),
    ("Infor",          "https://careers.infor.com",                   "Hyderabad"),
    ("Optum",          "https://www.optum.in/careers",                "Hyderabad"),
    ("SLK Software",   "https://www.slksoftware.com/careers",         "Hyderabad"),
    ("Avekshaa",       "https://avekshaa.com/careers",                "Hyderabad"),
    # Mumbai startups
    ("Zerodha",        "https://zerodha.com/careers",                 "Mumbai"),
    ("Groww",          "https://groww.in/jobs",                       "Mumbai"),
    ("Navi",           "https://navi.com/careers",                    "Mumbai"),
    ("Smallcase",      "https://smallcase.com/careers",               "Mumbai"),
    ("Pocketly",       "https://pocketly.in/careers",                 "Mumbai"),
    ("Yellow.ai",      "https://yellow.ai/careers",                   "Mumbai"),
    ("Ecom Express",   "https://ecomexpress.in/careers",              "Mumbai"),
    ("OkCredit",       "https://www.okcredit.in/careers",             "Mumbai"),
    ("Leap Finance",   "https://leapfinance.com/careers",             "Mumbai"),
    ("Rupeek",         "https://rupeek.com/careers",                  "Mumbai"),
    # Delhi/Noida/Gurugram startups
    ("Paytm",          "https://paytm.com/careers",                   "Noida"),
    ("InMobi",         "https://www.inmobi.com/careers",              "Gurugram"),
    ("Delhivery",      "https://www.delhivery.com/careers",           "Gurugram"),
    ("PolicyBazaar",   "https://www.policybazaar.com/careers",        "Gurugram"),
    ("Cars24",         "https://www.cars24.com/careers",              "Gurugram"),
    ("Zomato",         "https://www.zomato.com/careers",              "Gurugram"),
    ("Naukri",         "https://www.infoedge.in/careers",             "Noida"),
    ("Spinny",         "https://www.spinny.com/careers",              "Gurugram"),
    ("Virgio",         "https://virgio.com/careers",                  "Gurugram"),
    ("OfBusiness",     "https://www.ofbusiness.com/careers",          "Gurugram"),
    ("CureFit",        "https://www.cult.fit/careers",                "Gurugram"),
    ("Stanza Living",  "https://stanzaliving.com/careers",            "Noida"),
    # Chennai startups
    ("Zoho",           "https://careers.zohocorp.com",                "Chennai"),
    ("Freshworks",     "https://www.freshworks.com/company/careers",  "Chennai"),
    ("Chargebee",      "https://www.chargebee.com/jobs",              "Chennai"),
    ("Kissflow",       "https://kissflow.com/careers",                "Chennai"),
    ("Ola Electric",   "https://olaelectric.com/careers",             "Chennai"),
    ("Emeritus",       "https://emeritus.org/careers",                "Chennai"),
    ("Mad Street Den", "https://www.madstreetden.com/careers",        "Chennai"),
    ("SirionLabs",     "https://sirionlabs.com/careers",              "Chennai"),
    # Pune startups
    ("Persistent",     "https://careers.persistent.com",              "Pune"),
    ("Icertis",        "https://www.icertis.com/company/careers",     "Pune"),
    ("Druva",          "https://www.druva.com/careers",               "Pune"),
    ("ThoughtWorks",   "https://www.thoughtworks.com/careers",        "Pune"),
    ("Whirlpool Tech", "https://www.whirlpoolcareers.com",            "Pune"),
    ("Cummins India",  "https://www.cummins.com/careers",             "Pune"),
    # Other cities
    ("Juspay",         "https://juspay.in/careers",                   "Bengaluru"),
    ("Sigmoid",        "https://www.sigmoid.com/careers",             "Bengaluru"),
    ("Sprinklr",       "https://www.sprinklr.com/careers",            "Bengaluru"),
    ("HashedIn",       "https://hashedin.com/careers",                "Bengaluru"),
    ("Sarvam AI",      "https://www.sarvam.ai/careers",               "Bengaluru"),
    ("Krutrim",        "https://olakrutrim.com/careers",              "Bengaluru"),
    ("Suki AI",        "https://www.suki.ai/careers",                 "Bengaluru"),
    ("Mad Street Den", "https://www.madstreetden.com/careers",        "Chennai"),
    ("AIProxy",        "https://aiproxy.pro/careers",                 "Bengaluru"),
    ("Niramai",        "https://niramai.com/careers",                 "Bengaluru"),
]

# ── Domain employer map — each domain gets startups + established companies ──
DOMAIN_EMPLOYERS = {
    "physics": [
        ("BARC", "https://www.barc.gov.in/careers"),
        ("ISRO", "https://www.isro.gov.in/Careers.html"),
        ("DRDO", "https://www.drdo.gov.in/careers"),
        ("TIFR", "https://www.tifr.res.in/"),
        ("NPCIL", "https://npcil.nic.in"),
        ("ONGC", "https://ongcindia.com/careers"),
        ("Bharat Electronics", "https://bel-india.in/careers"),
        ("CSIR Labs", "https://www.csir.res.in/"),
        ("Niramai", "https://niramai.com/careers"),         # startup
        ("SciSpace", "https://scispace.com/careers"),        # startup
        ("Ati Motors", "https://atimotors.com/careers"),     # startup
        ("Agnikul Cosmos", "https://agnikul.in/careers"),    # space startup
        ("Pixxel", "https://www.pixxel.space/careers"),      # satellite startup
        ("Skyroot", "https://skyroot.in/careers"),           # space startup
        ("GalaxEye", "https://www.galaxeye.space/careers"),  # startup
    ],
    "chemistry": [
        ("Dr. Reddy's Labs", "https://careers.drreddys.com"),
        ("Sun Pharma", "https://www.sunpharma.com/careers"),
        ("Cipla", "https://www.cipla.com/careers"),
        ("Biocon", "https://www.biocon.com/careers"),
        ("Aurobindo Pharma", "https://www.aurobindo.com/careers"),
        ("Divi's Lab", "https://www.divislabs.com/careers"),
        ("Aragen Life Sciences", "https://www.aragen.com/careers"),  # startup
        ("Hykros", "https://hykros.com/careers"),                     # startup
        ("Genotypic", "https://www.genotypic.co.in/careers"),         # startup
        ("StringBio", "https://stringbio.com/careers"),               # startup
        ("Praj Industries", "https://www.praj.net/careers"),          # startup
        ("Zymergen India", "https://zymergen.com/careers"),
        ("Syngene", "https://www.syngeneintl.com/careers"),
        ("Strides Pharma", "https://www.stridespharma.com/careers"),
        ("Suven Pharma", "https://www.suvenpharma.com/careers"),
    ],
    "biology": [
        ("Biocon", "https://www.biocon.com/careers"),
        ("Serum Institute", "https://www.seruminstitute.com/career.php"),
        ("Apollo Hospitals", "https://www.apollohospitals.com/careers"),
        ("MedGenome", "https://www.medgenome.com/careers"),            # startup
        ("Strand Life Sciences", "https://www.strandls.com/careers"),  # startup
        ("Niramai", "https://niramai.com/careers"),                    # AI health startup
        ("Tricog Health", "https://tricog.com/careers"),               # startup
        ("Qure.ai", "https://qure.ai/careers"),                        # AI+health startup
        ("SigTuple", "https://sigtuple.com/careers"),                  # startup
        ("Molbio Diagnostics", "https://www.molbiodiagnostics.com/careers"),
        ("AgriGenome", "https://agrigenome.com/careers"),              # agri biotech startup
        ("Panacea Biotech", "https://www.panaceabiotech.com/careers"),
        ("Intas Pharma", "https://www.intaspharma.com/careers"),
        ("ICMR", "https://www.icmr.gov.in"),
        ("Fortis Healthcare", "https://www.fortishealthcare.com/careers"),
    ],
    "finance": [
        ("Zerodha", "https://zerodha.com/careers"),
        ("Groww", "https://groww.in/jobs"),
        ("Razorpay", "https://razorpay.com/jobs"),
        ("PhonePe", "https://www.phonepe.com/careers"),
        ("Paytm", "https://paytm.com/careers"),
        ("CRED", "https://careers.cred.club"),
        ("Smallcase", "https://smallcase.com/careers"),
        ("Navi", "https://navi.com/careers"),
        ("Slice", "https://sliceit.com/careers"),
        ("Leap Finance", "https://leapfinance.com/careers"),
        ("Rupeek", "https://rupeek.com/careers"),
        ("OfBusiness", "https://www.ofbusiness.com/careers"),
        ("PolicyBazaar", "https://www.policybazaar.com/careers"),
        ("BankBazaar", "https://www.bankbazaar.com/careers"),
        ("Perfios", "https://www.perfios.com/careers"),
    ],
    "education": [
        ("Scaler", "https://www.scaler.com/careers"),
        ("NxtWave", "https://www.ccbp.in/careers"),
        ("upGrad", "https://careers.upgrad.com"),
        ("Unacademy", "https://unacademy.com/careers"),
        ("Vedantu", "https://www.vedantu.com/careers"),
        ("Emeritus", "https://emeritus.org/careers"),
        ("Edureka", "https://www.edureka.co/careers"),
        ("Simplilearn", "https://www.simplilearn.com/company/careers"),
        ("iNeuron", "https://ineuron.ai/careers"),
        ("Springboard", "https://www.springboard.com/careers"),
        ("Great Learning", "https://www.mygreatlearning.com/careers"),
        ("Masai School", "https://www.masaischool.com/careers"),
        ("Coding Ninjas", "https://www.codingninjas.com/careers"),
        ("Extramarks", "https://www.extramarks.com/careers"),
        ("PlanetSpark", "https://www.planetspark.in/careers"),
    ],
    "mechanical": [
        ("Ola Electric", "https://olaelectric.com/careers"),
        ("Ather Energy", "https://www.atherenergy.com/careers"),
        ("Yulu", "https://www.yulu.bike/careers"),
        ("Bounce", "https://www.bounce.bike/careers"),
        ("Simple Energy", "https://simpleenergy.in/careers"),
        ("Tata Motors", "https://www.tatamotors.com/careers"),
        ("Mahindra", "https://careers.mahindra.com"),
        ("Bosch India", "https://www.bosch.in/careers"),
        ("Zetwerk", "https://www.zetwerk.com/careers"),
        ("Infra.Market", "https://www.inframarket.in/careers"),
        ("Atomberg", "https://atomberg.com/careers"),
        ("Log 9 Materials", "https://log9materials.com/careers"),
        ("Exponent Energy", "https://www.exponent.energy/careers"),
        ("BHEL", "https://www.bhel.com/career"),
        ("HAL", "https://hal-india.co.in/Careers/pg_Careers.aspx"),
    ],
    "civil": [
        ("NoBroker", "https://www.nobroker.in/careers"),
        ("Housing.com", "https://housing.com/careers"),
        ("Square Yards", "https://www.squareyards.com/careers"),
        ("Infra.Market", "https://www.inframarket.in/careers"),
        ("Brick&Bolt", "https://bricknbolt.com/careers"),
        ("Housr", "https://housr.in/careers"),
        ("Stanza Living", "https://stanzaliving.com/careers"),
        ("L&T Construction", "https://www.lntecc.com/careers"),
        ("DLF", "https://www.dlf.in/careers"),
        ("Godrej Properties", "https://www.godrejproperties.com/careers"),
        ("Shapoorji Pallonji", "https://www.shapoorjipallonji.com/careers"),
        ("NHAI", "https://nhai.gov.in/career"),
        ("Afcons Infrastructure", "https://www.afcons.com/careers"),
        ("Prestige Group", "https://www.prestigeconstructions.com/careers"),
        ("Brigade Group", "https://www.brigadegroup.com/careers"),
    ],
    "electrical": [
        ("Ola Electric", "https://olaelectric.com/careers"),
        ("Ather Energy", "https://www.atherenergy.com/careers"),
        ("Exponent Energy", "https://www.exponent.energy/careers"),
        ("Log 9 Materials", "https://log9materials.com/careers"),
        ("Amara Raja", "https://www.amararaja.co.in/careers"),
        ("NTPC", "https://ntpccareers.net"),
        ("Power Grid", "https://www.powergridindia.com/career"),
        ("ABB India", "https://new.abb.com/in/careers"),
        ("Siemens India", "https://www.siemens.co.in/careers"),
        ("Schneider Electric", "https://www.se.com/in/en/about-us/careers"),
        ("Tata Power", "https://www.tatapower.com/careers"),
        ("Greenko", "https://www.greenko.net/careers"),
        ("ReNew Power", "https://www.renewpower.in/careers"),
        ("Sterling & Wilson", "https://www.sterlingandwilson.com/careers"),
        ("Havells", "https://www.havells.com/careers"),
    ],
    "law": [
        ("NoBroker", "https://www.nobroker.in/careers"),
        ("Razorpay", "https://razorpay.com/jobs"),
        ("Zerodha", "https://zerodha.com/careers"),
        ("LegalDesk", "https://legaldesk.com/careers"),
        ("LawRato", "https://lawrato.com/careers"),
        ("MyAdvo", "https://www.myadvo.in/careers"),
        ("Vakil Search", "https://vakilsearch.com/careers"),
        ("Cyril Amarchand", "https://www.camcofin.com/careers"),
        ("AZB Partners", "https://www.azbpartners.com/careers"),
        ("Khaitan & Co", "https://www.khaitanco.com/careers"),
        ("Trilegal", "https://www.trilegal.com/careers"),
        ("IndusLaw", "https://induslaw.com/careers"),
        ("Nishith Desai", "https://www.nishithdesai.com/careers"),
        ("LawSikho", "https://lawsikho.com/careers"),
        ("Legistify", "https://legistify.com/careers"),
    ],
    "marketing": [
        ("Zomato", "https://www.zomato.com/careers"),
        ("Swiggy", "https://careers.swiggy.com"),
        ("Meesho", "https://meesho.io/jobs"),
        ("CRED", "https://careers.cred.club"),
        ("Nykaa", "https://www.nykaa.com/careers"),
        ("Mamaearth", "https://mamaearth.in/careers"),
        ("Sugar Cosmetics", "https://www.sugarcosmetics.com/careers"),
        ("boAt", "https://www.boat-lifestyle.com/careers"),
        ("Boat Lifestyle", "https://www.boat-lifestyle.com/careers"),
        ("Bombay Shaving", "https://www.bombayshavingcompany.com/careers"),
        ("WOW Skin Science", "https://www.wowskinscienceindia.com/careers"),
        ("Bewakoof", "https://www.bewakoof.com/careers"),
        ("Lenskart", "https://www.lenskart.com/careers"),
        ("Classplus", "https://classplus.co/careers"),
        ("Vedix", "https://vedix.com/careers"),
    ],
    "computer science": [
        ("Razorpay", "https://razorpay.com/jobs"),
        ("Freshworks", "https://www.freshworks.com/company/careers"),
        ("Zepto", "https://www.zepto.team/jobs"),
        ("BrowserStack", "https://www.browserstack.com/careers"),
        ("Postman", "https://www.postman.com/company/careers"),
        ("Chargebee", "https://www.chargebee.com/jobs"),
        ("CleverTap", "https://clevertap.com/careers"),
        ("Darwinbox", "https://darwinbox.com/careers"),
        ("Haptik", "https://www.haptik.ai/careers"),
        ("Sprinklr", "https://www.sprinklr.com/careers"),
        ("Druva", "https://www.druva.com/careers"),
        ("Icertis", "https://www.icertis.com/company/careers"),
        ("HashedIn", "https://hashedin.com/careers"),
        ("Juspay", "https://juspay.in/careers"),
        ("Slintel", "https://www.slintel.com/careers"),
    ],
    "data science": [
        ("Sigmoid", "https://www.sigmoid.com/careers"),
        ("Fractal Analytics", "https://fractal.ai/careers"),
        ("Mu Sigma", "https://www.mu-sigma.com/careers"),
        ("Houseware", "https://www.houseware.io/careers"),
        ("Atlan", "https://atlan.com/careers"),
        ("Slintel", "https://www.slintel.com/careers"),
        ("LatentView", "https://www.latentview.com/careers"),
        ("Tiger Analytics", "https://www.tigeranalytics.com/careers"),
        ("Tredence", "https://tredence.com/careers"),
        ("Quantiphi", "https://quantiphi.com/careers"),
        ("Crayon Data", "https://crayondata.ai/careers"),
        ("Bridgei2i", "https://bridgei2i.com/careers"),
        ("ThoughtWorks", "https://www.thoughtworks.com/careers"),
        ("Meesho Data", "https://meesho.io/jobs"),
        ("Swiggy Data", "https://careers.swiggy.com"),
    ],
    "artificial intelligence": [
        ("Sarvam AI", "https://www.sarvam.ai/careers"),
        ("Krutrim", "https://olakrutrim.com/careers"),
        ("Mad Street Den", "https://www.madstreetden.com/careers"),
        ("Haptik", "https://www.haptik.ai/careers"),
        ("Yellow.ai", "https://yellow.ai/careers"),
        ("Mihup", "https://mihup.com/careers"),
        ("Qure.ai", "https://qure.ai/careers"),
        ("SigTuple", "https://sigtuple.com/careers"),
        ("Niramai", "https://niramai.com/careers"),
        ("Quantiphi", "https://quantiphi.com/careers"),
        ("Fractal Analytics", "https://fractal.ai/careers"),
        ("Sigmoid", "https://www.sigmoid.com/careers"),
        ("Juspay", "https://juspay.in/careers"),
        ("Slintel", "https://www.slintel.com/careers"),
        ("Sprinklr", "https://www.sprinklr.com/careers"),
    ],
    "machine learning": [
        ("Sarvam AI", "https://www.sarvam.ai/careers"),
        ("Krutrim", "https://olakrutrim.com/careers"),
        ("Razorpay", "https://razorpay.com/jobs"),
        ("Swiggy", "https://careers.swiggy.com"),
        ("Zomato", "https://www.zomato.com/careers"),
        ("Meesho", "https://meesho.io/jobs"),
        ("Ola", "https://www.olacabs.com/careers"),
        ("Juspay", "https://juspay.in/careers"),
        ("Haptik", "https://www.haptik.ai/careers"),
        ("Yellow.ai", "https://yellow.ai/careers"),
        ("Fractal Analytics", "https://fractal.ai/careers"),
        ("Quantiphi", "https://quantiphi.com/careers"),
        ("Mad Street Den", "https://www.madstreetden.com/careers"),
        ("Mihup", "https://mihup.com/careers"),
        ("Sigmoid", "https://www.sigmoid.com/careers"),
    ],
    "general": [
        ("Razorpay", "https://razorpay.com/jobs"),
        ("Zepto", "https://www.zepto.team/jobs"),
        ("Meesho", "https://meesho.io/jobs"),
        ("CRED", "https://careers.cred.club"),
        ("Delhivery", "https://www.delhivery.com/careers"),
        ("Nykaa", "https://www.nykaa.com/careers"),
        ("Cars24", "https://www.cars24.com/careers"),
        ("OfBusiness", "https://www.ofbusiness.com/careers"),
        ("Zetwerk", "https://www.zetwerk.com/careers"),
        ("Spinny", "https://www.spinny.com/careers"),
        ("TCS", "https://www.tcs.com/careers"),
        ("Infosys", "https://www.infosys.com/careers"),
        ("Wipro", "https://careers.wipro.com"),
        ("HCL", "https://www.hcltech.com/careers"),
        ("Accenture", "https://www.accenture.com/in-en/careers"),
    ],
}

def get_domain_employers(domain_str):
    """Match domain string to employer list — fuzzy, case-insensitive."""
    d = domain_str.lower()
    # Direct match
    for key in DOMAIN_EMPLOYERS:
        if key in d or d in key:
            return DOMAIN_EMPLOYERS[key]
    # Partial word match (handles "Artificial Intelligence and Machine Learning")
    for key, employers in DOMAIN_EMPLOYERS.items():
        words = [w for w in key.split() if len(w) > 3]
        if any(word in d for word in words):
            return employers
    return DOMAIN_EMPLOYERS["general"]

def analyze_job_skill_gaps(candidate_skills, job_required_skills, job_title, company, domain):
    """
    Per-job gap analysis — compares THIS job's required skills vs candidate.
    Gap advice is specific to the missing skills for THIS exact role.
    No Groq call — instant, zero cost, always different per job.
    """
    candidate_lower = {s.strip().lower() for s in candidate_skills}

    matched = []
    missing = []
    for s in job_required_skills:
        s_clean = s.strip()
        # Check exact match and partial match (e.g. "PyTorch" matches "pytorch")
        if s_clean.lower() in candidate_lower or any(
            s_clean.lower() in c or c in s_clean.lower()
            for c in candidate_lower
        ):
            matched.append(s_clean)
        else:
            missing.append(s_clean)

    match_pct = round(len(matched) / max(len(job_required_skills), 1) * 100)

    # Build specific gap advice based on actual missing skills
    if not missing:
        gap_advice = f"✅ You match all key requirements for {job_title} at {company}! Apply immediately — your profile is a strong fit."
    elif len(missing) == 1:
        sk = missing[0]
        gap_advice = f"You're only missing {sk}. Spend 1-2 weeks on a hands-on project using {sk} and you'll be fully qualified for {job_title} at {company}."
    elif len(missing) <= 3:
        top2 = " and ".join(missing[:2])
        gap_advice = f"Focus on {top2} first — these are the most critical gaps for {job_title} at {company}. A 3-4 week focused effort on these will make your profile competitive. {missing[2] if len(missing) > 2 else ''} can be learned on the job."
    else:
        top3 = ", ".join(missing[:3])
        rest = len(missing) - 3
        gap_advice = f"Priority gaps for {job_title} at {company}: learn {top3} first ({rest} more gaps exist). Start with the one most mentioned in their JD. Build one project demonstrating each skill before applying."

    # Add specific learning resource hint based on missing skills
    skill_resources = {
        "docker":       "→ Free: Docker official docs + Play with Docker (labs.play-with-docker.com)",
        "kubernetes":   "→ Free: KillerKoda.com has free K8s labs",
        "mlops":        "→ Free: MLflow docs + Hugging Face MLOps course",
        "aws":          "→ Free: AWS Free Tier + AWS Skill Builder",
        "azure":        "→ Free: Microsoft Learn (learn.microsoft.com)",
        "langchain":    "→ Free: LangChain docs + DeepLearning.AI short courses",
        "react":        "→ Free: React official docs + Scrimba React course",
        "sql":          "→ Free: SQLZoo.net + Mode Analytics SQL tutorial",
        "spark":        "→ Free: Databricks Community Edition",
        "tensorflow":   "→ Free: TensorFlow official tutorials",
        "pytorch":      "→ Free: PyTorch.org tutorials",
        "fastapi":      "→ Free: FastAPI official docs (tiangolo.com)",
        "git":          "→ Free: learngitbranching.js.org",
        "linux":        "→ Free: OverTheWire.org + Linux Journey",
    }
    hints = []
    for sk in missing[:2]:
        for key, resource in skill_resources.items():
            if key in sk.lower():
                hints.append(f"{sk} {resource}")
                break
    if hints:
        gap_advice += " | " + " | ".join(hints)

    return {
        "matched_skills": matched[:8],
        "missing_skills": missing[:6],
        "match_pct":      match_pct,
        "gap_advice":     gap_advice
    }


def fetch_direct_apply_links_adzuna(title, location):
    """Adzuna API — 1000 req/DAY free, best free option for India."""
    if not ADZUNA_APP_ID or not ADZUNA_API_KEY:
        return None
    try:
        city = location.split(",")[0].strip().lower()
        resp = requests.get(
            f"https://api.adzuna.com/v1/api/jobs/in/search/1",
            params={
                "app_id":        ADZUNA_APP_ID,
                "app_key":       ADZUNA_API_KEY,
                "what":          title,
                "where":         city,
                "results_per_page": 3,
                "max_days_old":  30,
                "content-type":  "application/json"
            },
            timeout=10
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            jobs = []
            for r in results:
                jobs.append({
                    "direct_url":  r.get("redirect_url", ""),
                    "job_title":   r.get("title", title),
                    "employer":    r.get("company", {}).get("display_name", ""),
                    "location":    r.get("location", {}).get("display_name", location),
                    "salary":      f"₹{r.get('salary_min','')}-{r.get('salary_max','')} LPA" if r.get("salary_min") else "",
                    "description": r.get("description", "")[:300],
                    "posted_at":   r.get("created", "")[:10],
                    "source":      "Adzuna",
                    "is_direct":   True
                })
            if jobs:
                print(f"  [Adzuna] ✅ {len(jobs)} direct links for '{title}'")
                return jobs
    except Exception as e:
        print(f"  [Adzuna] Error: {e}")
    return None


def fetch_direct_apply_links_jsearch(title, location):
    """JSearch RapidAPI — 200 req/month free. Single-job query."""
    if not JSEARCH_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={
                "X-RapidAPI-Key":  JSEARCH_API_KEY,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            },
            params={
                "query":       f"{title} in {location} India",
                "page":        "1",
                "num_pages":   "1",
                "date_posted": "month",
                "country":     "in"
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            jobs = []
            for r in data[:3]:
                jobs.append({
                    "direct_url":  r.get("job_apply_link") or r.get("job_google_link", ""),
                    "job_title":   r.get("job_title", title),
                    "employer":    r.get("employer_name", ""),
                    "location":    r.get("job_city", location),
                    "salary":      "",
                    "description": r.get("job_description", "")[:300],
                    "posted_at":   r.get("job_posted_at_datetime_utc", "")[:10],
                    "source":      r.get("job_publisher", "JSearch"),
                    "is_direct":   True
                })
            if jobs:
                print(f"  [JSearch] ✅ {len(jobs)} direct links for '{title}'")
                return jobs
        elif resp.status_code == 429:
            print("  [JSearch] Monthly quota exceeded")
    except Exception as e:
        print(f"  [JSearch] Error: {e}")
    return None


def fetch_real_jobs_batch(domain, career, skills, location="India"):
    """
    ONE API call to fetch 10 real live jobs for the candidate's domain.
    Uses only 1 API credit per resume (not 15).
    Returns list of real job dicts with direct apply links.
    """
    any_key = JSEARCH_API_KEY or ADZUNA_APP_ID or HASDATA_API_KEY or SCRAPEOPS_API_KEY
    if not any_key:
        return []

    role    = career[0] if career else domain
    query   = f"{role} {domain} fresher India"
    jobs    = []

    # ── JSearch batch: 1 call → up to 10 real jobs ──────────────
    if JSEARCH_API_KEY:
        try:
            resp = requests.get(
                "https://jsearch.p.rapidapi.com/search",
                headers={
                    "X-RapidAPI-Key":  JSEARCH_API_KEY,
                    "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
                },
                params={
                    "query":       query,
                    "page":        "1",
                    "num_pages":   "2",      # 2 pages = up to 20 results in 1 API call
                    "date_posted": "month",
                    "country":     "in",
                    "language":    "en"
                },
                timeout=15
            )
            if resp.status_code == 200:
                for r in resp.json().get("data", [])[:15]:
                    url = r.get("job_apply_link") or r.get("job_google_link","")
                    if not url:
                        continue
                    # Parse salary from job description / highlights
                    salary = ""
                    highlights = r.get("job_highlights", {})
                    for item in highlights.get("Qualifications", []):
                        if "lpa" in item.lower() or "salary" in item.lower() or "₹" in item:
                            salary = item[:40]
                            break

                    jobs.append({
                        "title":           r.get("job_title", role),
                        "company":         r.get("employer_name", ""),
                        "location":        r.get("job_city") or r.get("job_state","") or location,
                        "experience":      "Fresher / Entry Level",
                        "salary":          salary or "As per industry standards",
                        "description":     (r.get("job_description",""))[:400],
                        "required_skills": skills[:6],   # will be refined below
                        "nice_to_have":    [],
                        "url":             url,
                        "naukri_url":      f"https://www.naukri.com/{r.get('job_title','').lower().replace(' ','-')}-jobs",
                        "linkedin_url":    f"https://www.linkedin.com/jobs/search/?keywords={r.get('job_title','').replace(' ','%20')}&location=India&f_TPR=r2592000",
                        "internshala_url": f"https://internshala.com/jobs/{r.get('job_title','').lower().replace(' ','-')}-jobs",
                        "is_direct":       True,
                        "posted_at":       r.get("job_posted_at_datetime_utc","")[:10],
                        "source":          r.get("job_publisher","Indeed"),
                        "match":           "0%"
                    })
                print(f"  [JSearch Batch] ✅ {len(jobs)} real jobs fetched in 1 API call")
        except Exception as e:
            print(f"  [JSearch Batch] Error: {e}")

    # ── Adzuna batch fallback ─────────────────────────────────────
    if not jobs and ADZUNA_APP_ID and ADZUNA_API_KEY:
        try:
            resp = requests.get(
                f"https://api.adzuna.com/v1/api/jobs/in/search/1",
                params={
                    "app_id":      ADZUNA_APP_ID,
                    "app_key":     ADZUNA_API_KEY,
                    "results_per_page": 15,
                    "what":        f"{role} {domain}",
                    "where":       "India",
                    "max_days_old": 30,
                    "content-type": "application/json"
                },
                timeout=12
            )
            if resp.status_code == 200:
                for r in resp.json().get("results", [])[:15]:
                    url = r.get("redirect_url","")
                    if not url:
                        continue
                    jobs.append({
                        "title":           r.get("title", role),
                        "company":         r.get("company",{}).get("display_name",""),
                        "location":        r.get("location",{}).get("display_name", location),
                        "experience":      "Fresher / Entry Level",
                        "salary":          f"₹{int(r.get('salary_min',0)/100000 or 4)}-{int(r.get('salary_max',0)/100000 or 8)} LPA" if r.get("salary_min") else "As per industry",
                        "description":     r.get("description","")[:400],
                        "required_skills": skills[:6],
                        "nice_to_have":    [],
                        "url":             url,
                        "naukri_url":      f"https://www.naukri.com/{r.get('title','').lower().replace(' ','-')}-jobs",
                        "linkedin_url":    f"https://www.linkedin.com/jobs/search/?keywords={r.get('title','').replace(' ','%20')}&location=India",
                        "internshala_url": f"https://internshala.com/jobs/{r.get('title','').lower().replace(' ','-')}-jobs",
                        "is_direct":       True,
                        "posted_at":       r.get("created","")[:10],
                        "source":          "Adzuna",
                        "match":           "0%"
                    })
                print(f"  [Adzuna Batch] ✅ {len(jobs)} real jobs fetched")
        except Exception as e:
            print(f"  [Adzuna Batch] Error: {e}")

    return jobs[:15]


def fetch_direct_apply_links_hasdata(title, location):
    """
    HasData Indeed + Glassdoor APIs — 1000 free credits each.
    Correct endpoints from official docs:
    - Indeed:    api.hasdata.com/scrape/indeed/listing
    - Glassdoor: api.hasdata.com/scrape/glassdoor/listing
    """
    if not HASDATA_API_KEY:
        return None
    headers = {
        "Content-Type": "application/json",
        "x-api-key":    HASDATA_API_KEY
    }
    jobs = []

    # ── Indeed listings ──────────────────────────────────────────
    try:
        resp = requests.get(
            "https://api.hasdata.com/scrape/indeed/listing",
            headers=headers,
            params={
                "keyword":  title,
                "location": f"{location}, India",
                "domain":   "in.indeed.com",   # India domain
                "datePosted": "last30days"
            },
            timeout=12
        )
        if resp.status_code == 200:
            results = resp.json().get("jobs", []) or resp.json().get("jobResults", [])
            for r in results[:5]:
                url = r.get("jobUrl") or r.get("url") or r.get("applyUrl","")
                if url:
                    jobs.append({
                        "direct_url":  url,
                        "job_title":   r.get("jobTitle") or r.get("title", title),
                        "employer":    r.get("companyName") or r.get("company",""),
                        "location":    r.get("jobLocation") or r.get("location", location),
                        "salary":      r.get("jobSalary") or r.get("salary",""),
                        "description": (r.get("jobDescription") or r.get("description",""))[:300],
                        "posted_at":   (r.get("datePosted") or r.get("postedAt",""))[:10],
                        "source":      "Indeed (HasData)",
                        "is_direct":   True
                    })
            print(f"  [HasData Indeed] ✅ {len(jobs)} jobs for '{title}'")
    except Exception as e:
        print(f"  [HasData Indeed] Error: {e}")

    # ── Glassdoor listings (bonus) ───────────────────────────────
    if not jobs:
        try:
            resp2 = requests.get(
                "https://api.hasdata.com/scrape/glassdoor/listing",
                headers=headers,
                params={
                    "keyword":  title,
                    "location": f"{location}, India",
                },
                timeout=12
            )
            if resp2.status_code == 200:
                results2 = resp2.json().get("jobs", []) or resp2.json().get("jobListings",[])
                for r in results2[:3]:
                    url = r.get("jobUrl") or r.get("applyUrl","")
                    if url:
                        jobs.append({
                            "direct_url":  url,
                            "job_title":   r.get("jobTitle") or r.get("title", title),
                            "employer":    r.get("employerName") or r.get("company",""),
                            "location":    r.get("location", location),
                            "salary":      r.get("salaryEstimate") or r.get("salary",""),
                            "description": (r.get("jobDescription",""))[:300],
                            "posted_at":   "",
                            "source":      "Glassdoor (HasData)",
                            "is_direct":   True
                        })
                print(f"  [HasData Glassdoor] {len(jobs)} jobs for '{title}'")
        except Exception as e:
            print(f"  [HasData Glassdoor] Error: {e}")

    return jobs if jobs else None


def fetch_direct_apply_links_scrapeops(title, location):
    """
    ScrapeOps Indeed API — 1000 free credits.
    Endpoint: proxy.scrapeops.io/v1/structured-data/indeed/job-search
    """
    if not SCRAPEOPS_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://proxy.scrapeops.io/v1/structured-data/indeed/job-search",
            params={
                "api_key":  SCRAPEOPS_API_KEY,
                "query":    title,
                "location": f"{location}, India",
                "country":  "in"
            },
            timeout=12
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("jobs", []) or data.get("results", [])
            jobs = []
            for r in results[:5]:
                url = r.get("url") or r.get("job_url") or r.get("applyLink","")
                if url:
                    jobs.append({
                        "direct_url":  url,
                        "job_title":   r.get("title") or r.get("job_title", title),
                        "employer":    r.get("company") or r.get("company_name",""),
                        "location":    r.get("location", location),
                        "salary":      r.get("salary",""),
                        "description": (r.get("description",""))[:300],
                        "posted_at":   (r.get("date") or r.get("posted_at",""))[:10],
                        "source":      "Indeed (ScrapeOps)",
                        "is_direct":   True
                    })
            if jobs:
                print(f"  [ScrapeOps] ✅ {len(jobs)} jobs for '{title}'")
                return jobs
        elif resp.status_code == 429:
            print("  [ScrapeOps] Quota exceeded")
    except Exception as e:
        print(f"  [ScrapeOps] Error: {e}")
    return None



def fetch_direct_apply_links(title, location):
    """
    4-API waterfall for DIRECT apply links — tries each free API in order:
    1. Adzuna    → 1000 req/DAY  (best — most generous)
    2. JSearch   → 200 req/month
    3. HasData   → 1000 credits  (Indeed + Glassdoor)
    4. ScrapeOps → 1000 credits  (Indeed)
    Returns list of job dicts with direct_url, or None if all fail/not configured.
    """
    result = fetch_direct_apply_links_adzuna(title, location)
    if result:
        return result

    result = fetch_direct_apply_links_jsearch(title, location)
    if result:
        return result

    result = fetch_direct_apply_links_hasdata(title, location)
    if result:
        return result

    result = fetch_direct_apply_links_scrapeops(title, location)
    if result:
        return result

    return None



def make_job_url(title, company, location, domain):
    """
    Build all apply links for a job.
    Priority: JSearch direct link → search page fallbacks.
    """
    role_query = title.replace(" ", "+")
    loc_query  = location.replace(" ", "+")
    li_role    = title.replace(" ", "%20")
    li_loc     = location.replace(" ", "%20")

    return {
        # Direct apply (via JSearch — filled in post-processing if key exists)
        "apply_url":       f"https://www.google.com/search?q={role_query}+jobs+{loc_query}+India&ibp=htl;jobs&tbs=qdr:m",
        "naukri_url":      f"https://www.naukri.com/{title.lower().replace(' ','-')}-jobs-in-{location.lower().replace(' ','-')}",
        "linkedin_url":    f"https://www.linkedin.com/jobs/search/?keywords={li_role}&location={li_loc}%2C%20India&f_TPR=r604800&f_E=1%2C2",
        "internshala_url": f"https://internshala.com/jobs/{title.lower().replace(' ','-')}-jobs",
        "is_direct":       False
    }



def fetch_jobs_from_groq(analysis):
    """
    Generate 10 rich job listings with:
    - Full job description (5-6 sentences)
    - Required skills list
    - Salary range
    - Apply link (real career page)
    - Per-job skill gap analysis vs candidate resume
    """
    print("  [B] Generating rich job listings via Groq...")
    domain         = analysis.get("domain", "General")
    candidate_skills = analysis.get("skills", [])
    skills_str     = ", ".join(candidate_skills[:10])
    career         = safe_cell(analysis.get("career_fit", []))
    education      = safe_cell(analysis.get("education", ""))

    employers      = get_domain_employers(domain)
    employer_list  = ", ".join(f"{name}" for name, _ in employers[:12])
    employer_urls  = {name: url for name, url in employers}

    # Split into 2 batches of 5 jobs — smaller prompts = better quality, no truncation
    all_jobs = []
    careers_list = analysis.get("career_fit", ["Engineer"])

    for batch_num in range(3):  # 3 batches × 5 jobs = 15 total
        batch_roles = careers_list[batch_num % len(careers_list)] if careers_list else "Engineer"
        cities = ["Hyderabad", "Bengaluru", "Mumbai", "Chennai", "Pune",
                  "Delhi", "Noida", "Gurugram", "Kolkata", "Ahmedabad", "Jaipur"]
        city_slice = ", ".join(cities[batch_num*3:(batch_num+1)*3 + 2])

        prompt = f"""Indian tech recruiter. Generate 5 realistic job postings. Return ONLY JSON array.

CANDIDATE: {domain} | Skills: {skills_str} | Target: {career}
COMPANIES: {employer_list}
CITIES FOR THIS BATCH: {city_slice}

[
  {{
    "title": "Job title for {domain} professional",
    "company": "Real Indian startup name",
    "location": "City from: {city_slice}",
    "experience": "Fresher / Entry Level OR 0-2 years",
    "salary": "₹X LPA - ₹Y LPA",
    "description": "3 sentences: what the role does, what they build, why join this startup.",
    "required_skills": ["list", "8", "specific", "skills", "this", "role", "actually", "needs"],
    "nice_to_have": ["bonus1", "bonus2"],
    "match": "XX%"
  }}
]

CRITICAL RULES:
- required_skills must be ROLE-SPECIFIC — NOT copied from candidate profile above
- Each job must be different company, different city, different role title
- Mix: some skills candidate HAS, some they DON'T (realistic job requirements)
- match% = honest % of candidate skills that overlap with required_skills
- Return ONLY the JSON array"""

        result = groq_rotator.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=2000
        )

        if result:
            try:
                text = result.strip()
                if text.startswith("```"):
                    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
                s = text.find("["); e = text.rfind("]") + 1
                if s != -1 and e > s:
                    batch = json.loads(text[s:e])
                    if isinstance(batch, list):
                        all_jobs.extend(batch)
                        print(f"  [B] Batch {batch_num+1}: {len(batch)} jobs")
            except Exception as ex:
                print(f"  [B] Batch {batch_num+1} parse error: {ex}")

    jobs = all_jobs

    # Smart fallback — only if Groq completely failed
    if len(jobs) < 5:
        print(f"  [B] Groq returned only {len(jobs)} — using smart fallback")
        # Pre-defined role-specific skill sets (NOT candidate skills)
        role_skills = {
            "ai": ["Python", "PyTorch", "TensorFlow", "MLOps", "Docker", "REST APIs", "SQL", "Git"],
            "ml": ["Python", "Scikit-learn", "XGBoost", "Feature Engineering", "Pandas", "MLflow", "AWS", "SQL"],
            "nlp": ["Python", "Transformers", "SpaCy", "NLTK", "BERT", "FastAPI", "Docker", "Git"],
            "data": ["Python", "SQL", "Tableau", "Power BI", "Pandas", "Statistics", "Excel", "BigQuery"],
            "backend": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "Kubernetes", "AWS", "Git"],
            "default": ["Python", "SQL", "REST APIs", "Git", "Linux", "Docker", "Cloud", "Problem Solving"]
        }
        d = domain.lower()
        rk = "ai" if "artificial" in d or "ai" in d else \
             "ml" if "machine" in d else \
             "nlp" if "nlp" in d or "language" in d else \
             "data" if "data" in d else \
             "backend" if "computer" in d or "software" in d else "default"
        fallback_skills = role_skills[rk]

        locs = ["Hyderabad","Bengaluru","Mumbai","Chennai","Pune","Delhi","Noida","Gurugram","Jaipur","Kolkata"]
        for i, (company, url) in enumerate(employers[:15]):
            role = careers_list[i % len(careers_list)] if careers_list else "Engineer"
            jobs.append({
                "title":          role,
                "company":        company,
                "location":       locs[i % len(locs)],
                "experience":     "Fresher / Entry Level" if i < 8 else "0-2 years",
                "salary":         "₹4 LPA - ₹8 LPA" if i < 8 else "₹8 LPA - ₹15 LPA",
                "description":    f"Join {company}'s {domain} team as a {role}. You will build production-grade systems, work with modern tools, and grow rapidly in a fast-paced startup environment. This is a high-ownership role with direct impact.",
                "required_skills": fallback_skills,   # ← role-specific, NOT candidate skills
                "nice_to_have":    ["Cloud experience", "Open source contributions"],
                "match":          f"{max(25, 60 - i*4)}%"
            })

    # Post-process each job — add URLs and gap analysis
    for job in jobs:
        company  = job.get("company", "")
        title    = job.get("title", "")
        location = job.get("location", "India")

        # ── Ensure all apply links exist (real jobs already have urls) ──
        if not job.get("url"):
            urls = make_job_url(title, company, location, domain)
            job["url"] = urls["apply_url"]
        if not job.get("naukri_url"):
            job["naukri_url"] = f"https://www.naukri.com/{title.lower().replace(' ','-')}-jobs-in-{location.lower().replace(' ','-')}"
        if not job.get("linkedin_url"):
            job["linkedin_url"] = f"https://www.linkedin.com/jobs/search/?keywords={title.replace(' ','%20')}&location={location.replace(' ','%20')}%2C%20India&f_TPR=r2592000"
        if not job.get("internshala_url"):
            job["internshala_url"] = f"https://internshala.com/jobs/{title.lower().replace(' ','-')}-jobs"
        if "is_direct" not in job:
            job["is_direct"] = False

        # Match known career page URL
        for emp_name, emp_url in employer_urls.items():
            if emp_name.lower() in company.lower() or company.lower() in emp_name.lower():
                job["career_page"] = emp_url
                break

        # ── Per-job skill gap analysis (specific to THIS job's required_skills) ──
        required = job.get("required_skills", [])
        if required and candidate_skills:
            gap_data = analyze_job_skill_gaps(
                candidate_skills, required, title, company, domain
            )
            job["matched_skills"] = gap_data["matched_skills"]
            job["missing_skills"] = gap_data["missing_skills"]
            job["gap_advice"]     = gap_data["gap_advice"]
            calc_pct  = gap_data["match_pct"]
            groq_pct  = int(str(job.get("match","0%")).replace("%","").strip() or "0")
            job["match"] = f"{max(calc_pct, min(groq_pct, 95))}%"
        else:
            calc = calculate_match_percent(
                job.get("description","") + " " + title, candidate_skills
            )
            job["match"]          = f"{max(calc, 20)}%"
            job["matched_skills"] = []
            job["missing_skills"] = []
            job["gap_advice"]     = f"Review the job description carefully and build 1-2 projects that directly use the required skills for {title} at {company}."

    # Sort by match % descending
    jobs.sort(key=lambda j: int(str(j.get("match","0%")).replace("%","").strip() or "0"), reverse=True)
    print(f"  [B] ✅ {len(jobs)} rich jobs generated with skill gap analysis")
    return jobs[:15]


# ================= SECTION C: LEARNING RESOURCES =====================
def learning_resources_agent(analysis):
    print("  [C] Generating learning resources...")
    skills = safe_cell(analysis.get("skills", []))
    skill_gaps = analysis.get("skill_gaps", "")
    career_fit = safe_cell(analysis.get("career_fit", []))

    prompt = f"""Create a learning plan. Return ONLY valid JSON:
{{
  "books": ["Book Title by Author", "Book2 by Author2", "Book3 by Author3"],
  "courses": ["Course Name on Platform - URL", "Course2 on Platform2"],
  "youtube": ["Channel Name - topic", "Channel2 - topic2"],
  "websites": ["sitename.com - purpose", "site2.com - purpose2"],
  "learning_path": "Week 1: Topic. Week 2: Topic. Week 3: Topic. Week 4: Topic.",
  "mindmap": "Core Skill -> Sub1, Sub2, Sub3 | Related -> A, B, C"
}}

Skills: {skills}
Gaps: {skill_gaps}
Career: {career_fit}"""

    result = groq_json(prompt, temperature=0.3)
    if not result:
        return {
            "books": "Clean Code by Robert Martin, The Pragmatic Programmer",
            "courses": "Full Stack Web Dev on Udemy",
            "youtube": "Traversy Media, Tech With Tim",
            "websites": "leetcode.com, geeksforgeeks.org",
            "learning_path": "Week 1: Fundamentals. Week 2: Projects. Week 3: DSA. Week 4: Interview Prep.",
            "mindmap": "Programming -> DSA, Projects, System Design"
        }
    # Flatten lists to strings for sheet
    flat = {}
    for k, v in result.items():
        flat[k] = safe_cell(v)
    print("  [C] Resources generated.")
    return flat

# ================= FALLBACK QUESTION BANK =====================
# Used when Groq API is rate-limited. Guarantees questions always exist.
FALLBACK_QUESTIONS = {
    "default": [
        # Level 1 - Beginner
        {"q": "What is a variable? Give an example.", "answer": "A variable is a named storage location in memory. Example: x = 10", "level": 1},
        {"q": "What is the difference between a compiler and an interpreter?", "answer": "A compiler translates the entire program at once; an interpreter executes line by line.", "level": 1},
        {"q": "What is an algorithm?", "answer": "A step-by-step procedure to solve a problem or accomplish a task.", "level": 1},
        {"q": "What is object-oriented programming?", "answer": "A programming paradigm based on objects containing data (attributes) and code (methods).", "level": 1},
        {"q": "What are the four pillars of OOP?", "answer": "Encapsulation, Abstraction, Inheritance, and Polymorphism.", "level": 1},
        {"q": "What is a function/method?", "answer": "A reusable block of code that performs a specific task.", "level": 1},
        {"q": "What is the difference between == and ===?", "answer": "== checks value equality; === checks both value and type equality.", "level": 1},
        {"q": "What is a loop? Name the types.", "answer": "A loop repeats code. Types: for, while, do-while.", "level": 1},
        {"q": "What is a data structure?", "answer": "A way of organizing data for efficient access and modification. Examples: array, list, stack, queue.", "level": 1},
        {"q": "What is the difference between stack and queue?", "answer": "Stack is LIFO (Last In First Out); Queue is FIFO (First In First Out).", "level": 1},
        {"q": "What is recursion?", "answer": "A function that calls itself to solve a smaller version of the same problem.", "level": 1},
        {"q": "What is a linked list?", "answer": "A linear data structure where each element points to the next via a reference/pointer.", "level": 1},
        {"q": "What is the difference between an array and a linked list?", "answer": "Arrays have fixed size and direct indexing; linked lists have dynamic size but sequential access.", "level": 1},
        {"q": "What is a primary key in a database?", "answer": "A unique identifier for each record in a table.", "level": 1},
        {"q": "What is HTTP vs HTTPS?", "answer": "HTTP transfers data in plain text; HTTPS encrypts data using SSL/TLS.", "level": 1},
        {"q": "What is version control?", "answer": "A system that records changes to files over time. Git is the most popular.", "level": 1},
        {"q": "What is a class vs an object?", "answer": "A class is a blueprint; an object is an instance of a class.", "level": 1},
        {"q": "What is inheritance in OOP?", "answer": "A mechanism where a child class acquires properties and methods of a parent class.", "level": 1},
        {"q": "What is an exception?", "answer": "An error that occurs at runtime that can be caught and handled gracefully.", "level": 1},
        {"q": "What is Big O notation?", "answer": "A mathematical notation describing the time/space complexity of an algorithm as input grows.", "level": 1},
        # Level 2 - Intermediate
        {"q": "Explain the concept of polymorphism with an example.", "answer": "Polymorphism allows one interface to be used for different data types. E.g., method overriding in subclasses.", "level": 2},
        {"q": "What is a REST API?", "answer": "A web service using HTTP methods (GET, POST, PUT, DELETE) to interact with resources identified by URLs.", "level": 2},
        {"q": "What is the difference between SQL and NoSQL databases?", "answer": "SQL is structured/relational (tables); NoSQL is unstructured/flexible (documents, key-value, graphs).", "level": 2},
        {"q": "Explain normalization in databases.", "answer": "Organizing data to reduce redundancy. Normal forms (1NF, 2NF, 3NF) progressively eliminate anomalies.", "level": 2},
        {"q": "What is a binary search tree?", "answer": "A tree where left child < parent < right child, enabling O(log n) search.", "level": 2},
        {"q": "What is the difference between process and thread?", "answer": "A process is an independent program; a thread is a lightweight unit within a process sharing its memory.", "level": 2},
        {"q": "What is a deadlock?", "answer": "A state where two or more threads are blocked forever, each waiting for the other to release resources.", "level": 2},
        {"q": "What is dependency injection?", "answer": "A design pattern where objects receive their dependencies from outside rather than creating them internally.", "level": 2},
        {"q": "What is the difference between GET and POST?", "answer": "GET retrieves data and appends params to URL; POST sends data in request body, used for creating/updating.", "level": 2},
        {"q": "What is caching?", "answer": "Storing copies of data temporarily to speed up future requests and reduce database load.", "level": 2},
        {"q": "What is a hash table?", "answer": "A data structure that maps keys to values using a hash function for O(1) average lookup time.", "level": 2},
        {"q": "Explain MVC architecture.", "answer": "Model-View-Controller: Model handles data, View handles UI, Controller handles business logic between them.", "level": 2},
        {"q": "What is a foreign key?", "answer": "A column that creates a relationship between two tables by referencing the primary key of another table.", "level": 2},
        {"q": "What is the difference between inner join and outer join?", "answer": "INNER JOIN returns matching rows from both tables; OUTER JOIN includes unmatched rows from one or both tables.", "level": 2},
        {"q": "What is asynchronous programming?", "answer": "Code that runs non-blocking — tasks execute independently so the program doesn't wait for slow operations.", "level": 2},
        {"q": "What is Git branching strategy?", "answer": "Using branches (feature, develop, main) to isolate work. Common strategies: GitFlow, trunk-based development.", "level": 2},
        {"q": "What is time complexity of quicksort?", "answer": "Average O(n log n), worst case O(n²) when pivot is always the smallest/largest element.", "level": 2},
        {"q": "What is the singleton design pattern?", "answer": "Ensures a class has only one instance and provides a global point of access to it.", "level": 2},
        {"q": "What is a microservice?", "answer": "An architectural style where an application is built as small, independent services communicating via APIs.", "level": 2},
        {"q": "What is the difference between authentication and authorization?", "answer": "Authentication verifies identity (who you are); authorization verifies permissions (what you can do).", "level": 2},
        # Level 3 - Advanced
        {"q": "Explain the CAP theorem.", "answer": "A distributed system can only guarantee 2 of 3: Consistency, Availability, Partition Tolerance.", "level": 3},
        {"q": "What is eventual consistency?", "answer": "A consistency model where all replicas eventually converge to the same value if no new updates are made.", "level": 3},
        {"q": "Explain database sharding.", "answer": "Horizontal partitioning of a database across multiple machines, each holding a subset of data (a shard).", "level": 3},
        {"q": "What is a distributed transaction?", "answer": "A transaction that spans multiple nodes/databases, managed via protocols like 2-Phase Commit (2PC).", "level": 3},
        {"q": "What is a load balancer?", "answer": "A server that distributes incoming network traffic across multiple backend servers to ensure reliability and performance.", "level": 3},
        {"q": "Explain how a garbage collector works.", "answer": "It identifies and frees memory no longer referenced. Common algorithms: mark-and-sweep, generational GC.", "level": 3},
        {"q": "What is a B-tree index?", "answer": "A self-balancing tree data structure used in databases for efficient sorted data storage and O(log n) lookups.", "level": 3},
        {"q": "What is ACID in databases?", "answer": "Atomicity (all or nothing), Consistency (valid state), Isolation (independent transactions), Durability (persisted).", "level": 3},
        {"q": "How would you design a URL shortener like bit.ly?", "answer": "Use a hash function to generate short codes, store mapping in DB, use redirect with 301/302, add caching layer.", "level": 3},
        {"q": "What is a race condition?", "answer": "When two threads access shared data simultaneously and the result depends on execution order, causing bugs.", "level": 3},
        {"q": "Explain the SOLID principles.", "answer": "Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.", "level": 3},
        {"q": "What is a consensus algorithm?", "answer": "A protocol for nodes in a distributed system to agree on a value. Examples: Raft, Paxos.", "level": 3},
        {"q": "What is event sourcing?", "answer": "Storing state as a sequence of events rather than current state, allowing replay and audit trail.", "level": 3},
        {"q": "How does a CDN work?", "answer": "Content Delivery Network caches content at edge servers globally, serving users from the nearest location.", "level": 3},
        {"q": "What is the difference between horizontal and vertical scaling?", "answer": "Horizontal: add more machines. Vertical: upgrade existing machine's CPU/RAM. Horizontal is more fault-tolerant.", "level": 3},
        {"q": "Explain the observer design pattern.", "answer": "Objects (observers) subscribe to a subject; when the subject changes state, it notifies all observers automatically.", "level": 3},
        {"q": "What is connection pooling?", "answer": "Reusing a pool of pre-established database connections rather than creating new ones per request, improving performance.", "level": 3},
        {"q": "What is a bloom filter?", "answer": "A probabilistic data structure to test set membership with possible false positives but no false negatives.", "level": 3},
        {"q": "How do you prevent SQL injection?", "answer": "Use parameterized queries/prepared statements, ORMs, input validation, and principle of least privilege.", "level": 3},
        {"q": "What is the two-phase commit protocol?", "answer": "A distributed algorithm ensuring all nodes either commit or rollback a transaction atomically, in prepare and commit phases.", "level": 3},
    ]
}

def get_fallback_questions(skill, count=20):
    """Return fallback questions tagged with the given skill."""
    base = FALLBACK_QUESTIONS["default"]
    result = []
    for q in base[:count]:
        result.append({**q, "topic": skill})
    return result

# ================= SECTION D: INTERVIEW QUESTIONS =====================
# One Groq call per skill — clean, focused, always within token limits.
# Works for ANY background: tech, physics, finance, biology, law, arts, etc.

def questions_for_skill(skill, resume_context, career, domain, level):
    """Generate 10 questions for ONE skill at ONE level — fast, focused, resume-grounded."""
    level_label = {
        1: "beginner — definitions, basic concepts, fundamentals",
        2: "intermediate — practical application, real scenarios",
        3: "advanced — deep expertise, edge cases, design decisions"
    }

    prompt = f"""Expert interviewer generating interview questions.

CANDIDATE BACKGROUND:
{resume_context}

Generate exactly 10 interview questions about: {skill}
Difficulty: Level {level} — {level_label[level]}
Field: {domain} | Role: {career}

Rules:
1. Questions must be specific to "{skill}" for THIS candidate's background
2. Use their actual projects/tools/subjects to make questions concrete
3. Match their domain — never ask coding questions unless skill IS a coding language
4. Mix types: conceptual, applied, experiential, analytical

Return ONLY JSON array, no markdown:
[{{"q":"question","answer":"concise answer","level":{level},"topic":"{skill}"}}]"""

    try:
        raw = groq_rotator.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500   # reduced from 2500
        )
        if not raw:
            raise Exception("Empty response")
        s = raw.find("["); e = raw.rfind("]") + 1
        if s == -1 or e == 0:
            raise Exception("No JSON array")
        parsed = json.loads(raw[s:e])
        if not isinstance(parsed, list) or len(parsed) == 0:
            raise Exception("Empty list")
        for q in parsed:
            q["topic"] = skill
            q["level"] = level
        return parsed
    except Exception as err:
        print(f"    ✗ {skill} L{level}: failed ({err}) — using fallback")
        return [
            {"q": f"What is your experience with {skill}? Give a specific example.", "answer": "Describe with concrete examples.", "level": level, "topic": skill},
            {"q": f"What are the key concepts in {skill} relevant to your field?", "answer": "List 3-5 key concepts.", "level": level, "topic": skill},
            {"q": f"How have you applied {skill} in your projects or coursework?", "answer": "Use STAR method.", "level": level, "topic": skill},
        ]


def generate_hr_aptitude_logical(resume_context, career, has_coding):
    """Generate HR, aptitude, logical, and coding questions in one Groq call."""
    coding_instruction = (
        "\"coding\": [10 coding/DSA questions relevant to their tech stack]"
        if has_coding else
        "\"coding\": []"
    )
    prompt = f"""Generate interview questions for this candidate.

CANDIDATE BACKGROUND:
{resume_context}
TARGET ROLE: {career}

Return ONLY valid JSON with these keys:
{{
  "aptitude": [15 questions with q/answer/level fields],
  "logical":  [15 questions with q/answer/level fields],
  "hr":       [15 questions with q/tip fields — tailored to their field],
  {coding_instruction}
}}

- Aptitude: numerical, percentage, ratio, time-work problems
- Logical: series, analogy, direction, syllogism
- HR: MUST reference their specific domain, skills and career goals — not generic
- Level 1=easy, 2=medium, 3=hard"""

    result = groq_json(prompt, temperature=0.3, max_tokens=4000)
    if result and isinstance(result, dict) and result.get("hr"):
        print(f"    ✓ HR/Aptitude/Logical: {len(result.get('hr',[]))} HR, "
              f"{len(result.get('aptitude',[]))} aptitude, "
              f"{len(result.get('logical',[]))} logical, "
              f"{len(result.get('coding',[]))} coding")
        return result

    # Built-in fallback
    print("    ✗ HR/Aptitude failed — using built-in fallback")
    return {
        "aptitude": [
            {"q": "A train travels 300km in 5 hours. What is its speed?", "answer": "60 km/h", "level": 1},
            {"q": "If 8 workers finish a job in 6 days, how long for 12 workers?", "answer": "4 days", "level": 2},
            {"q": "What is 35% of 400?", "answer": "140", "level": 1},
            {"q": "Simple interest on ₹8000 at 5% for 3 years?", "answer": "₹1200", "level": 1},
            {"q": "A:B = 3:4, B:C = 2:5. Find A:C.", "answer": "3:10", "level": 2},
        ],
        "logical": [
            {"q": "Odd one out: 3, 9, 15, 21, 25", "answer": "25 (not divisible by 3)", "level": 1},
            {"q": "Find missing: 2, 6, 18, 54, ?", "answer": "162 (×3 pattern)", "level": 1},
            {"q": "If all A are B, some B are C — are some A necessarily C?", "answer": "Not necessarily.", "level": 2},
            {"q": "A walks 4km north, 3km east. Distance from start?", "answer": "5 km (Pythagorean)", "level": 2},
            {"q": "Series: 1, 4, 9, 16, 25, ?", "answer": "36 (perfect squares)", "level": 1},
        ],
        "hr": [
            {"q": "Tell me about yourself and your background.", "tip": "Use Present-Past-Future structure."},
            {"q": f"Why do you want to work as {career}?", "tip": "Connect your education and passion to the role."},
            {"q": "What is your greatest strength?", "tip": "Give a specific example."},
            {"q": "Describe a challenging situation and how you handled it.", "tip": "Use STAR method."},
            {"q": "Where do you see yourself in 5 years?", "tip": "Show ambition aligned with the role."},
            {"q": "What motivates you in your work?", "tip": "Be genuine."},
            {"q": "How do you handle pressure and deadlines?", "tip": "Give a specific example."},
            {"q": "What is your biggest weakness?", "tip": "Be honest, show self-awareness."},
        ],
        "coding": []
    }


def generate_interview_questions(analysis):
    """Generate questions per-skill IN PARALLEL — fast for any background."""

    domain    = analysis.get("domain", "General")
    raw_skills = analysis.get("skills", [])
    career    = safe_cell(analysis.get("career_fit", []))
    education = analysis.get("education", "")
    projects  = analysis.get("projects", [])
    experience = analysis.get("experience_context", "")
    strengths = analysis.get("strengths", "")
    weaknesses = analysis.get("weaknesses", "")

    resume_context = f"""Domain: {domain}
Education: {education}
Skills: {", ".join(raw_skills[:15])}
Career Target: {career}
Projects: {"; ".join(projects[:4]) if projects else "Not specified"}
Experience: {experience}
Strengths: {strengths}"""

    print(f"  [D] Domain: {domain} | Education: {education[:60]}")
    print(f"  [D] Skills extracted: {raw_skills[:8]}")

    # Infer skills if none found
    if not raw_skills:
        print("  [D] No skills — inferring from resume...")
        infer_prompt = f"""Candidate background: {resume_context}
List 4-5 specific topics to interview them about (match their actual field).
Return ONLY a JSON array of strings."""
        try:
            raw = groq_rotator.call(
                messages=[{"role": "user", "content": infer_prompt}],
                temperature=0.3, max_tokens=150
            )
            if raw:
                s2 = raw.find("["); e2 = raw.rfind("]") + 1
                if s2 != -1:
                    raw_skills = json.loads(raw[s2:e2])
                    print(f"  [D] Inferred: {raw_skills}")
        except Exception as ex:
            print(f"  [D] Inference failed: {ex}")
        if not raw_skills:
            raw_skills = [domain, "Problem Solving", "Domain Knowledge"]

    # Detect coding skills
    coding_kw = {"python","java","c++","javascript","sql","r programming","matlab",
                 "coding","programming","software","algorithm","typescript","scala",
                 "rust","go","kotlin","swift","c#","ruby","php","bash","shell"}
    resume_lower = (education + " " + domain + " " + " ".join(raw_skills)).lower()
    has_coding = any(kw in resume_lower for kw in coding_kw)
    print(f"  [D] Has coding: {has_coding} | Domain: {domain}")

    # ── Use top 3 skills (was 5) — 3×3×10 = 90 questions, much faster ──
    skills_to_use = raw_skills[:3]
    print(f"  [D] Generating questions for: {skills_to_use} (parallel with stagger)")

    # ── PARALLEL generation with 0.8s stagger to avoid Groq rate limits ──
    all_technical = []
    skill_results = {}
    lock = _threading.Lock()

    def fetch_skill_level(skill, level, delay=0):
        if delay:
            time.sleep(delay)
        qs = questions_for_skill(skill, resume_context, career, domain, level)
        with lock:
            if skill not in skill_results:
                skill_results[skill] = {}
            skill_results[skill][level] = qs
            # Print progress
            total_batches = sum(len(v) for v in skill_results.values())
            print(f"    ✓ [{domain}] {skill} L{level}: {len(qs)} questions")

    threads = []
    delay   = 0.0
    for skill in skills_to_use:
        for level in [1, 2, 3]:
            t = _threading.Thread(
                target=fetch_skill_level,
                args=(skill, level, delay),
                daemon=True
            )
            threads.append(t)
            t.start()
            delay += 0.8   # stagger 0.8s — avoids Groq rate limit hammering

    for t in threads:
        t.join()

    # Reassemble in skill order
    for skill in skills_to_use:
        for level in [1, 2, 3]:
            all_technical.extend(skill_results.get(skill, {}).get(level, []))

    # HR + aptitude + logical
    print("  [D] Generating HR/aptitude/logical...")
    common = generate_hr_aptitude_logical(resume_context, career, has_coding)

    result = {
        "technical": all_technical,
        "aptitude":  common.get("aptitude", []),
        "logical":   common.get("logical", []),
        "hr":        common.get("hr", []),
        "coding":    common.get("coding", [])
    }

    print(f"  [D] ✅ Done: {len(all_technical)} technical "
          f"({len(skills_to_use)} skills × 3 levels × ~10), "
          f"{len(result['aptitude'])} aptitude, "
          f"{len(result['hr'])} HR, "
          f"{len(result['coding'])} coding")
    return result
# ================= SECTION E: AGI FEEDBACK =====================
def agi_feedback(analysis):
    print("  [E] Generating AGI feedback...")
    prompt = f"""Write a warm, motivating 300-word career feedback letter for this candidate.
Celebrate strengths, address weaknesses kindly, give 3 next steps, end with inspiration.
Use second person. Be like a brilliant mentor.

Strengths: {analysis.get('strengths', '')}
Weaknesses: {analysis.get('weaknesses', '')}
Skill gaps: {analysis.get('skill_gaps', '')}
Career fit: {safe_cell(analysis.get('career_fit', []))}
Confidence: {analysis.get('confidence_level', 'Medium')}"""

    feedback = groq_text(prompt, temperature=0.7)
    print("  [E] Feedback generated.")
    return feedback

# ================= EVALUATE ANSWER =====================
@app.route("/evaluate_answer", methods=["POST"])
def evaluate_answer():
    data = request.json
    question   = data.get("question", "")
    answer     = data.get("answer", "").strip()
    expected   = data.get("expected_answer", "")
    topic      = data.get("topic", "General")
    level      = data.get("level", 1)
    domain     = data.get("domain", "General")
    career     = data.get("career", "Professional")

    # Empty / too-short answer
    if len(answer) < 8:
        return jsonify({
            "score": 0, "grade": "F", "correct": False,
            "feedback": "No answer was provided. Please attempt the question.",
            "what_was_right": "",
            "what_was_wrong": "Answer was blank or too short.",
            "improvement": "Write at least a few sentences explaining your understanding.",
            "model_answer_hint": f"A good answer would cover the core concepts of {topic}.",
            "encouragement": "Every expert was once a beginner. Give it a try!",
            "confidence_impact": "negative"
        })

    level_context = {1: "beginner", 2: "intermediate", 3: "advanced"}.get(level, "intermediate")

    prompt = f"""You are a senior {domain} interviewer evaluating a candidate's answer.

INTERVIEW CONTEXT:
- Domain: {domain}
- Topic: {topic}
- Difficulty: Level {level} ({level_context})
- Target Role: {career}

QUESTION ASKED:
{question}

EXPECTED ANSWER (reference):
{expected}

CANDIDATE'S ACTUAL ANSWER:
{answer}

Evaluate the answer DEEPLY and return ONLY valid JSON:
{{
  "score": <integer 0-10>,
  "grade": "<A/B/C/D/F>",
  "correct": <true if score >= 6>,
  "feedback": "2-3 sentences of specific, kind, constructive feedback referencing what they actually said",
  "what_was_right": "Specific things the candidate got right (quote their words if possible)",
  "what_was_wrong": "Specific gaps or misconceptions in their answer",
  "improvement": "One concrete, actionable tip to improve this answer",
  "model_answer_hint": "A 2-3 sentence hint of what a perfect answer would include (not the full answer)",
  "encouragement": "One genuinely motivating sentence tailored to their domain/level",
  "confidence_impact": "<positive/neutral/negative>"
}}

SCORING GUIDE:
- 9-10: Exceptional — covers all key concepts with depth and examples
- 7-8: Good — covers main points, minor gaps
- 5-6: Partial — understands basics but missing important aspects
- 3-4: Weak — some awareness but significant gaps or misconceptions
- 1-2: Poor — answer is mostly wrong or irrelevant
- 0: No attempt or completely off-topic

Be honest but kind. Reference their actual words in feedback."""

    result = groq_json(prompt, temperature=0.2, max_tokens=600)
    if not result:
        # Smart fallback based on answer length
        length = len(answer.split())
        score = min(7, max(3, length // 8))
        result = {
            "score": score,
            "grade": "B" if score >= 7 else "C" if score >= 5 else "D",
            "correct": score >= 6,
            "feedback": f"Your answer shows {'good' if score >= 6 else 'some'} understanding of {topic}. {'Well structured response.' if score >= 6 else 'Try to be more specific and detailed.'}",
            "what_was_right": "You attempted the question with relevant content.",
            "what_was_wrong": "Could not fully evaluate — please ensure your answer is detailed.",
            "improvement": f"Add concrete examples from your experience with {topic}.",
            "model_answer_hint": f"A strong answer would define {topic}, explain its importance, and give a real-world example.",
            "encouragement": f"Keep practicing {domain} concepts — consistency is key!",
            "confidence_impact": "neutral"
        }
    # Clamp score
    result["score"] = max(0, min(10, int(result.get("score", 5))))
    return jsonify(result)

# ================= SESSION ROUTES =====================
@app.route("/create_session", methods=["POST"])
def create_session():
    data = request.json
    session_id = str(uuid.uuid4())
    INTERVIEW_SESSIONS[session_id] = data
    return jsonify({"session_id": session_id})

@app.route("/session/<session_id>", methods=["GET"])
def get_session(session_id):
    session = INTERVIEW_SESSIONS.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session)

@app.route("/interview/<session_id>")
def interview_page(session_id):
    return send_from_directory("interview_app", "index.html")

# ================= MONGODB STORAGE =====================

_mongo_client = None
_mongo_db     = None
_mongo_col    = None

def init_db():
    """Connect to MongoDB Atlas and ensure email index exists."""
    global _mongo_client, _mongo_db, _mongo_col
    try:
        # Try multiple SSL strategies for Python 3.11 compatibility
        import ssl
        try:
            import certifi
            _mongo_client = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=8000,
                tlsCAFile=certifi.where()
            )
        except Exception:
            # Fallback: disable SSL verification (safe for local dev)
            _mongo_client = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=8000,
                tls=True,
                tlsAllowInvalidCertificates=True
            )
        _mongo_client.server_info()
        _mongo_db  = _mongo_client["agi_career"]
        _mongo_col = _mongo_db["candidates"]
        _mongo_col.create_index("email", unique=True, sparse=True)
        print("  [DB] ✅ MongoDB connected")
    except Exception as e:
        print(f"  [DB] ❌ MongoDB connection failed: {e}")
        _mongo_col = None

def get_col():
    global _mongo_col
    if _mongo_col is None:
        init_db()
    return _mongo_col

def get_existing_emails():
    try:
        col = get_col()
        if col is None: return set()
        return {d["email"].strip().lower() for d in col.find({"email":{"$exists":True}},{"email":1})}
    except Exception as e:
        print(f"  [DB] Email fetch error: {e}")
        return set()

def ensure_table_exists():
    return get_col() is not None



def save_to_sheet(details, analysis, jobs, resources, feedback, interview_link, session_id=""):
    """Save candidate to MongoDB Atlas."""
    name  = details.get("name", "Unknown")
    email = details.get("email", "").strip().lower()
    print(f"  [DB] Saving: {name}")

    top_job = jobs[0] if jobs else {}
    doc = {
        "name":          safe_cell(name),
        "email":         email,
        "phone":         safe_cell(details.get("phone","")),
        "education":     safe_cell(details.get("education","")),
        "cgpa":          safe_cell(details.get("cgpa","")),
        "domain":        safe_cell(analysis.get("domain","")),
        "skills":        safe_cell(analysis.get("skills",[])),
        "career_fit":    safe_cell(analysis.get("career_fit",[])),
        "confidence":    safe_cell(analysis.get("confidence_level","Medium")),
        "strengths":     safe_cell(analysis.get("strengths","")),
        "weaknesses":    safe_cell(analysis.get("weaknesses","")),
        "skill_gaps":    safe_cell(analysis.get("skill_gaps","")),
        "top_jobs":      " | ".join(f"{j.get('title','')} @ {j.get('company','')} [{j.get('match','?')}]" for j in jobs[:5]),
        "best_title":    safe_cell(top_job.get("title","")),
        "best_company":  safe_cell(top_job.get("company","")),
        "location":      safe_cell(top_job.get("location","")),
        "match_pct":     safe_cell(top_job.get("match","0%")),
        "apply_url":     safe_cell(top_job.get("url","")),
        "books":         safe_cell(resources.get("books","")),
        "courses":       safe_cell(resources.get("courses","")),
        "youtube":       safe_cell(resources.get("youtube","")),
        "learning_path": safe_cell(resources.get("learning_path","")),
        "agi_feedback":  str(feedback or "")[:2000],
        "interview_link": interview_link,
        "status":        "New",
        "processed_at":  datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    try:
        col = get_col()
        if col is not None:
            col.update_one(
                {"email": email} if email else {"interview_link": interview_link},
                {"$set": doc},
                upsert=True
            )
            print(f"  [DB] ✅ Saved to MongoDB: {name}")
        else:
            print("  [DB] ⚠️  MongoDB not connected — data not saved")
    except Exception as e:
        print(f"  [DB] ❌ Save failed: {e}")

    # Send email to candidate
    try:
        sync_to_google_sheet(details, analysis, jobs, resources, feedback, interview_link, session_id)
    except Exception as e:
        print(f"  [Email] Error: {e}")



# ── Google Sheets sync (runs after every SQLite save) ────────────

def send_candidate_email(to_email, name, report_link, interview_link):
    """Send personalised email to candidate with their 2 links."""
    if not EMAIL_ENABLED or not to_email:
        return
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        subject = EMAIL_SUBJECT.format(name=name)
        body = f"""<html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;">
  <div style="background:linear-gradient(135deg,#6c63ff,#00d4aa);padding:32px;text-align:center;">
    <h1 style="color:#fff;margin:0;">🎓 Your AGI Career Report is Ready!</h1>
    <p style="color:rgba(255,255,255,0.85);margin-top:8px;">Hello <strong>{name}</strong></p>
  </div>
  <div style="padding:32px;">
    <a href="{report_link}" style="display:block;background:#6c63ff;color:#fff;padding:14px;border-radius:8px;text-decoration:none;font-weight:bold;text-align:center;margin-bottom:12px;">📋 View Career Report →</a>
    <a href="{interview_link}" style="display:block;background:#00d4aa;color:#111;padding:14px;border-radius:8px;text-decoration:none;font-weight:bold;text-align:center;">🎤 Start Mock Interview →</a>
  </div>
</div></body></html>"""
        msg = MIMEMultipart("alternative")
        msg["From"] = EMAIL_SENDER
        msg["To"]   = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        print(f"  [Email] ✅ Sent to {to_email}")
    except Exception as e:
        print(f"  [Email] ❌ {to_email}: {e}")

def sync_to_google_sheet(details, analysis, jobs, resources, feedback, interview_link, session_id):
    """Send email to candidate."""
    report_link = f"{BASE_URL}/report/{session_id}"
    send_candidate_email(
        details.get("email",""),
        details.get("name",""),
        report_link,
        interview_link
    )
    print(f"  [Sync] ✅ Saved to SQLite. Report: {report_link}")


@app.route("/candidates", methods=["GET"])
def get_candidates():
    try:
        col  = get_col()
        rows = list(col.find({}, {"_id": 0}).sort("processed_at", -1)) if col else []
        return jsonify({"total": len(rows), "candidates": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/candidates/export", methods=["GET"])
def export_candidates():
    import csv, io
    try:
        col  = get_col()
        rows = list(col.find({}, {"_id": 0}).sort("processed_at", -1)) if col else []
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        from flask import Response
        return Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=candidates.csv"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/db-test", methods=["GET"])
def db_test():
    col = get_col()
    if col is None:
        return jsonify({"status": "FAILED", "error": "MongoDB not connected — check MONGODB_URI"}), 500
    try:
        col.update_one({"email": "test@test.com"},
                       {"$set": {"name":"TEST","email":"test@test.com","domain":"Test",
                                 "processed_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}},
                       upsert=True)
        count = col.count_documents({})
        return jsonify({"status": "✅ MongoDB working", "total_candidates": count,
                        "view_all": f"{BASE_URL}/candidates",
                        "export_csv": f"{BASE_URL}/candidates/export"})
    except Exception as e:
        return jsonify({"status": "FAILED", "error": str(e)}), 500





@app.route("/uploadresume", methods=["POST"])
def upload_resume():
    import threading
    print("\n=== New resume received ===")
    file = request.files["resume"]
    filename = file.filename
    print("File:", filename)

    # Read file bytes immediately (can't pass file object to thread)
    file_bytes = file.read()

    print("[1/2] Extracting PDF text...")
    import io
    resume_text = extract_text_from_pdf(io.BytesIO(file_bytes))
    print("  Text length:", len(resume_text), "chars")

    print("[2/2] Extracting basic details...")
    details = extract_basic_details(resume_text, filename)
    print("  Name:", details['name'])

    # Create session ID and interview link IMMEDIATELY
    session_id = str(uuid.uuid4())
    interview_link = BASE_URL + "/interview/" + session_id

    # Pre-register session with placeholder so link works right away
    INTERVIEW_SESSIONS[session_id] = {
        "name": details["name"],
        "status": "processing",
        "questions": {},
        "career_fit": [],
        "skills": []
    }

    def background_processing():
        """Run all heavy Groq + sheet tasks in parallel background threads."""
        print(f"\n[BG] Starting parallel processing for {details['name']}...")

        analysis_result = {}
        jobs_result     = [{}]
        resources_result= {}
        questions_result= {}
        feedback_result = [""]

        def run_analysis():
            print("  [BG-A] AI analysis...")
            analysis_result.update(ai_analyze(resume_text))
            print("  [BG-A] Done.")

        # Run analysis first (others depend on it)
        t_analysis = threading.Thread(target=run_analysis)
        t_analysis.start()
        t_analysis.join()  # wait — others need analysis output

        # Now run jobs, resources, questions, feedback IN PARALLEL
        def run_jobs():
            print("  [BG-B] Fetching jobs...")
            jobs_result.clear()
            jobs_result.extend(fetch_jobs_from_resume(analysis_result))
            # Save to session immediately so report page can show jobs
            INTERVIEW_SESSIONS[session_id]["jobs"] = list(jobs_result)
            print(f"  [BG-B] Done. {len(jobs_result)} jobs.")

        def run_resources():
            print("  [BG-C] Learning resources...")
            resources_result.update(learning_resources_agent(analysis_result))
            # Save to session immediately
            INTERVIEW_SESSIONS[session_id]["resources"] = dict(resources_result)
            print("  [BG-C] Done.")

        def run_questions():
            print("  [BG-D] Interview questions...")
            try:
                questions_result.update(generate_interview_questions(analysis_result))
            except Exception as e:
                print(f"  [BG-D] Question generation error: {e}")
                import traceback; traceback.print_exc()
            # Update session with everything
            INTERVIEW_SESSIONS[session_id]["questions"]    = questions_result
            INTERVIEW_SESSIONS[session_id]["career_fit"]   = analysis_result.get("career_fit", [])
            INTERVIEW_SESSIONS[session_id]["skills"]       = analysis_result.get("skills", [])
            INTERVIEW_SESSIONS[session_id]["domain"]       = analysis_result.get("domain", "General")
            INTERVIEW_SESSIONS[session_id]["education"]    = analysis_result.get("education", "")
            INTERVIEW_SESSIONS[session_id]["status"]       = "ready"
            INTERVIEW_SESSIONS[session_id]["strengths"]    = analysis_result.get("strengths", "")
            INTERVIEW_SESSIONS[session_id]["weaknesses"]   = analysis_result.get("weaknesses", "")
            INTERVIEW_SESSIONS[session_id]["skill_gaps"]   = analysis_result.get("skill_gaps", "")
            INTERVIEW_SESSIONS[session_id]["achievements"] = analysis_result.get("achievements", "")
            # Jobs/resources may already be set by their threads — only update if missing
            if not INTERVIEW_SESSIONS[session_id].get("jobs"):
                INTERVIEW_SESSIONS[session_id]["jobs"]      = list(jobs_result)
            if not INTERVIEW_SESSIONS[session_id].get("resources"):
                INTERVIEW_SESSIONS[session_id]["resources"] = dict(resources_result)
            total_q = sum(len(v) for v in questions_result.values() if isinstance(v, list))
            print(f"  [BG-D] ✅ Done. {total_q} total questions. Interview is LIVE.")

        def run_feedback():
            print("  [BG-E] AGI feedback...")
            feedback_result[0] = agi_feedback(analysis_result)
            print("  [BG-E] Done.")
            # Save to DB once feedback is ready
            save_to_sheet(details, analysis_result, jobs_result, resources_result,
                          feedback_result[0], interview_link, session_id)
            print("  [BG-E] Saved to DB — report page now has full data.")

        threads = [
            threading.Thread(target=run_jobs),
            threading.Thread(target=run_resources),
            threading.Thread(target=run_questions),
            threading.Thread(target=run_feedback),
        ]
        for t in threads: t.start()
        for t in threads: t.join()
        print(f"=== [BG] All done for {details['name']} ===\n")

    # Start background thread — don't wait for it
    bg = threading.Thread(target=background_processing, daemon=True)
    bg.start()

    # Return interview link INSTANTLY
    print(f"[FAST RETURN] Interview link ready: {interview_link}")
    return jsonify({
        "message": "Resume received! Processing in background.",
        "candidate": details["name"],
        "interview_link": interview_link,
        "status": "processing",
        "note": "Interview link is live now. Questions will be ready in ~30 seconds."
    })


def _render_jobs(sess_jobs, jobs_text, apply_url):
    """Render job cards as HTML string — compatible with Python 3.11 (no nested f-strings)."""
    if not sess_jobs:
        # Fallback to plain text jobs
        cards = "".join(
            "<div class='job-card'><h3>" + line + "</h3></div>"
            for line in jobs_text.split(" | ") if line
        )
        return cards

    parts = []
    for j in sess_jobs[:15]:
        title    = j.get('title', '—')
        company  = j.get('company', '—')
        location = j.get('location', 'India')
        exp      = j.get('experience', 'Fresher')
        salary   = j.get('salary', '')
        desc     = j.get('description', '')
        match    = j.get('match', '—')
        url      = j.get('url', '#')
        naukri   = j.get('naukri_url', '#')
        linkedin = j.get('linkedin_url', '#')
        intern   = j.get('internshala_url', '#')
        career_p = j.get('career_page', '')
        is_direct = j.get('is_direct', False)
        posted   = j.get('posted_at', 'recent')
        source   = j.get('source', '')
        gap      = j.get('gap_advice', '')
        req_skills    = j.get('required_skills', [])
        matched_skills = j.get('matched_skills', [])
        missing_skills = j.get('missing_skills', [])

        # Match % color
        try:
            mp = int(str(match).replace('%','').strip() or '0')
        except:
            mp = 0
        match_color = '#00d4aa' if mp >= 60 else '#f5a623' if mp >= 35 else '#ff6b6b'

        # Salary badge
        salary_html = ("&nbsp;·&nbsp; 💰 " + salary) if salary else ""

        # Required skills tags
        req_html = ""
        if req_skills:
            tags = "".join(
                "<span style='background:rgba(108,99,255,0.12);border:1px solid rgba(108,99,255,0.25);"
                "border-radius:4px;padding:2px 9px;font-size:11px;margin:2px;display:inline-block;color:#a89cff;'>"
                + s + "</span>" for s in req_skills
            )
            req_html = ("<div style='margin-bottom:8px;'><div style='font-size:11px;color:#6b6b85;"
                       "text-transform:uppercase;letter-spacing:1px;margin-bottom:5px;'>Required Skills</div>"
                       "<div>" + tags + "</div></div>")

        # Matched / missing skills
        skills_html = ""
        if matched_skills or missing_skills:
            matched_html = ""
            if matched_skills:
                mtags = "".join(
                    "<span style='background:rgba(0,212,170,0.08);border:1px solid rgba(0,212,170,0.25);"
                    "border-radius:4px;padding:2px 9px;font-size:11px;margin:2px;display:inline-block;color:#00d4aa;'>✓ "
                    + s + "</span>" for s in matched_skills
                )
                matched_html = ("<div><div style='font-size:11px;color:#00d4aa;text-transform:uppercase;"
                               "letter-spacing:1px;margin-bottom:4px;'>✅ You Have</div>"
                               "<div>" + mtags + "</div></div>")
            missing_html = ""
            if missing_skills:
                mstags = "".join(
                    "<span style='background:rgba(255,107,107,0.08);border:1px solid rgba(255,107,107,0.25);"
                    "border-radius:4px;padding:2px 9px;font-size:11px;margin:2px;display:inline-block;color:#ff9999;'>+ "
                    + s + "</span>" for s in missing_skills
                )
                missing_html = ("<div><div style='font-size:11px;color:#ff9999;text-transform:uppercase;"
                               "letter-spacing:1px;margin-bottom:4px;'>⚠️ Need to Learn</div>"
                               "<div>" + mstags + "</div></div>")
            skills_html = ("<div style='display:flex;gap:20px;flex-wrap:wrap;margin-bottom:8px;'>"
                          + matched_html + missing_html + "</div>")

        # Gap analysis
        gap_html = ""
        if gap:
            gap_html = ("<div style='background:rgba(245,166,35,0.06);border-left:3px solid #f5a623;"
                       "border-radius:0 6px 6px 0;padding:10px 14px;margin-bottom:12px;font-size:13px;"
                       "color:#ffd580;line-height:1.65;'><strong>🎯 Gap Analysis: </strong>"
                       + gap + "</div>")

        # Apply buttons
        apply_label = "⚡ Direct Apply" if is_direct else "🔍 Search Jobs"
        direct_badge = ""
        if is_direct:
            direct_badge = ("<span style='font-size:11px;color:#00d4aa;background:rgba(0,212,170,0.1);"
                           "border:1px solid rgba(0,212,170,0.25);padding:3px 8px;border-radius:10px;'>"
                           "✓ Real listing · " + posted + " · via " + source + "</span>")

        career_btn = ""
        if career_p:
            career_btn = ("<a href='" + career_p + "' target='_blank' style='background:rgba(245,166,35,0.1);"
                         "border:1px solid rgba(245,166,35,0.3);color:#f5c842;padding:7px 14px;"
                         "border-radius:6px;font-size:12px;text-decoration:none;font-weight:600;'>Career Page</a>")

        card = (
            "<div class='job-card' style='margin-bottom:20px;'>"
            "<div style='display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;'>"
            "<div style='flex:1;'>"
            "<h3 style='font-size:16px;font-weight:700;color:#e8e8f0;margin-bottom:4px;'>" + title + "</h3>"
            "<div style='font-size:13px;color:#9999b3;margin-bottom:6px;'>"
            "🏢 <strong style='color:#a89cff;'>" + company + "</strong>"
            "&nbsp;·&nbsp; 📍 " + location +
            "&nbsp;·&nbsp; 💼 " + exp + salary_html +
            "</div>"
            "<span style='background:rgba(0,212,170,0.1);border:1px solid rgba(0,212,170,0.25);"
            "color:#00d4aa;padding:2px 10px;border-radius:12px;font-size:11px;'>🕐 Recent postings — last 30 days</span>"
            "</div>"
            "<div style='text-align:right;min-width:60px;'>"
            "<div style='font-size:22px;font-weight:800;color:" + match_color + ";'>" + match + "</div>"
            "<div style='font-size:10px;color:#6b6b85;'>skill match</div>"
            "</div></div>"
            "<p style='font-size:13px;color:#c8c8e0;line-height:1.7;margin:10px 0;'>" + desc + "</p>"
            + req_html + skills_html + gap_html +
            "<div style='display:flex;gap:8px;flex-wrap:wrap;align-items:center;'>"
            "<a href='" + url + "' target='_blank' style='background:linear-gradient(135deg,#6c63ff,#00d4aa);"
            "color:#fff;padding:8px 18px;border-radius:6px;font-size:13px;text-decoration:none;font-weight:700;'>"
            + apply_label + "</a>"
            + direct_badge +
            "<a href='" + naukri + "' target='_blank' style='background:rgba(108,99,255,0.15);"
            "border:1px solid rgba(108,99,255,0.35);color:#a89cff;padding:7px 14px;border-radius:6px;"
            "font-size:12px;text-decoration:none;font-weight:600;'>Naukri</a>"
            "<a href='" + linkedin + "' target='_blank' style='background:rgba(0,119,181,0.15);"
            "border:1px solid rgba(0,119,181,0.35);color:#7ab8d8;padding:7px 14px;border-radius:6px;"
            "font-size:12px;text-decoration:none;font-weight:600;'>LinkedIn</a>"
            "<a href='" + intern + "' target='_blank' style='background:rgba(0,180,100,0.12);"
            "border:1px solid rgba(0,180,100,0.3);color:#5edd9a;padding:7px 14px;border-radius:6px;"
            "font-size:12px;text-decoration:none;font-weight:600;'>Internshala</a>"
            + career_btn +
            "</div></div>"
        )
        parts.append(card)

    result = "".join(parts)
    if apply_url and apply_url != "#":
        result += ("<a href='" + apply_url + "' target='_blank' class='btn btn-outline' "
                  "style='margin-top:12px;display:inline-block;'>Apply to Top Match →</a>")
    return result


@app.route("/report/<session_id>")
def personal_report(session_id):
    """Student personal report page — shows their analysis, jobs, resources."""
    session = INTERVIEW_SESSIONS.get(session_id)
    if not session:
        return "<h2 style='font-family:sans-serif;text-align:center;margin-top:80px;color:#fff;background:#0a0a0f;min-height:100vh;padding:40px;'>Report not found or server restarted. Please re-upload your resume.</h2>", 404

    name       = str(session.get("name", "Candidate") or "Candidate")
    domain     = str(session.get("domain", "") or "")
    education  = str(session.get("education", "") or "")
    skills     = session.get("skills", [])
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    career     = session.get("career_fit", [])
    if isinstance(career, str):
        career = [c.strip() for c in career.split(",") if c.strip()]
    interview  = f"{BASE_URL}/interview/{session_id}"
    status     = session.get("status", "processing")

    # ── Try MongoDB first ─────────────────────────────────────────
    row = {}
    try:
        col = get_col()
        if col:
            found = col.find_one({"interview_link": {"$regex": session_id}}, {"_id": 0})
            row = found or {}
    except:
        row = {}

    def _s(val, default=""):
        """Safely convert any value to string."""
        if val is None:
            return default
        if isinstance(val, list):
            return ", ".join(str(v) for v in val if v)
        if isinstance(val, dict):
            return str(val)
        return str(val).strip() or default

    # ── Fallback to session memory (available much faster than DB) ─
    sess_resources = session.get("resources", {})
    sess_jobs      = session.get("jobs", [])

    # If jobs not in session yet, try to get from MongoDB
    if not sess_jobs and row:
        top_jobs_str = row.get("top_jobs","")
        if top_jobs_str:
            # Reconstruct basic job list from stored string for display
            sess_jobs = [
                {"title": part.split(" @ ")[0].strip(),
                 "company": part.split(" @ ")[1].split(" [")[0].strip() if " @ " in part else "",
                 "match": part.split("[")[1].rstrip("]").strip() if "[" in part else "?",
                 "url": f"https://www.google.com/search?q={part.split(' @ ')[0].replace(' ','+')}+jobs+India&ibp=htl;jobs",
                 "location": "India", "experience": "Fresher", "salary": "",
                 "description": "", "required_skills": [], "is_direct": False}
                for part in top_jobs_str.split(" | ") if part.strip()
            ]

    jobs_text     = _s(row.get("top_jobs")) or \
                    " | ".join(f"{j.get('title','')} @ {j.get('company','')} [{j.get('match','?')}]" for j in sess_jobs[:5]) or \
                    ""
    strengths     = _s(row.get("strengths")     or session.get("strengths", ""))
    weaknesses    = _s(row.get("weaknesses")    or session.get("weaknesses", ""))
    skill_gaps    = _s(row.get("skill_gaps")    or session.get("skill_gaps", ""))
    books         = _s(row.get("books")         or sess_resources.get("books", ""))
    courses       = _s(row.get("courses")       or sess_resources.get("courses", ""))
    youtube       = _s(row.get("youtube")       or sess_resources.get("youtube", ""))
    learning_path = _s(row.get("learning_path") or sess_resources.get("learning_path", ""))
    agi_feedback  = _s(row.get("agi_feedback",  ""))
    confidence    = _s(row.get("confidence")    or session.get("confidence", "Medium")) or "Medium"
    best_job      = _s(row.get("best_title",    ""))
    best_company  = _s(row.get("best_company",  ""))
    match_pct     = _s(row.get("match_pct",     ""))
    apply_url     = _s(row.get("apply_url",     "#")) or "#"

    # ── If still processing show animated loading with auto-refresh ─
    still_processing = (status == "processing") and not strengths
    auto_refresh = '<meta http-equiv="refresh" content="8">' if still_processing else ""
    processing_banner = ""
    if still_processing:
        processing_banner = """<div style="background:linear-gradient(135deg,#1a1a00,#1a0f00);border:1px solid rgba(245,166,35,0.3);border-radius:10px;padding:14px 18px;margin-bottom:18px;display:flex;align-items:center;gap:12px;">
  <div style="font-size:20px;animation:spin 2s linear infinite;display:inline-block;">⏳</div>
  <div>
    <div style="color:#f5a623;font-weight:700;font-size:14px;">AI is still processing your full report...</div>
    <div style="color:#8888aa;font-size:12px;margin-top:2px;">This page will auto-refresh every 8 seconds. Career Fit and Skills will appear shortly.</div>
  </div>
</div>
<style>@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}</style>"""

    conf_color = {"High":"#00d4aa","Medium":"#f5a623","Low":"#ff6b6b"}.get(confidence,"#6c63ff")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{auto_refresh}
<title>AGI Career Report — {name}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;600;700&display=swap');
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:'Space Grotesk',sans-serif;background:#0a0a0f;color:#e8e8f0;min-height:100vh;}}
  .hero{{background:linear-gradient(135deg,#12121a,#1a1a28);padding:40px 20px;text-align:center;border-bottom:1px solid rgba(108,99,255,0.2);}}
  .hero h1{{font-size:28px;font-weight:700;color:#6c63ff;margin-bottom:6px;}}
  .hero p{{color:#9999b3;font-size:15px;}}
  .badge{{display:inline-block;background:{conf_color}22;border:1px solid {conf_color};color:{conf_color};padding:4px 14px;border-radius:20px;font-size:13px;font-weight:600;margin-top:10px;}}
  .container{{max-width:800px;margin:0 auto;padding:24px 16px;}}
  .card{{background:#12121a;border:1px solid rgba(108,99,255,0.15);border-radius:12px;padding:20px 24px;margin-bottom:18px;}}
  .card h2{{font-size:15px;font-weight:700;color:#6c63ff;margin-bottom:12px;text-transform:uppercase;letter-spacing:0.5px;}}
  .tag{{display:inline-block;background:rgba(108,99,255,0.12);border:1px solid rgba(108,99,255,0.25);border-radius:6px;padding:3px 10px;font-size:12px;margin:3px;color:#a0a0c0;}}
  .job-card{{background:#1a1a28;border-radius:8px;padding:14px 16px;margin-bottom:10px;border-left:3px solid #6c63ff;}}
  .job-card h3{{font-size:15px;font-weight:600;color:#e8e8f0;}}
  .job-card p{{font-size:13px;color:#9999b3;margin-top:4px;}}
  .btn{{display:inline-block;background:linear-gradient(135deg,#6c63ff,#00d4aa);color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;margin:6px;}}
  .btn-outline{{background:transparent;border:2px solid #6c63ff;color:#6c63ff;}}
  .section-label{{font-size:12px;color:#6b6b85;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;}}
  .feedback-box{{background:#0f1a15;border:1px solid rgba(0,212,170,0.2);border-radius:8px;padding:16px;font-size:14px;line-height:1.7;color:#c8e6c9;}}
  .cta{{text-align:center;padding:30px 0 10px;}}
  .footer{{text-align:center;padding:20px;color:#4a4a65;font-size:12px;border-top:1px solid rgba(108,99,255,0.1);margin-top:20px;}}
</style>
</head>
<body>
<div class="hero">
  <h1>🎓 Your AGI Career Report</h1>
  <p>Hello, <strong>{name}</strong> — here's your personalised career analysis</p>
  <span class="badge">Confidence: {confidence}</span>
  {"<span class='badge' style='margin-left:8px;background:#6c63ff22;border-color:#6c63ff;color:#6c63ff;'>" + domain + "</span>" if domain else ""}
</div>
<div class="container">
  {processing_banner}

  <div class="card">
    <h2>🎯 Career Fit</h2>
    {"".join(f"<span class='tag'>{r}</span>" for r in (career if isinstance(career,list) and career else str(career).split(",") if career else ["Processing..."]))}
    {f"<p style='margin-top:12px;font-size:13px;color:#9999b3;'><strong>Top Match:</strong> {best_job} @ {best_company} — {match_pct}</p>" if best_job else ""}
  </div>

  <div class="card">
    <h2>🛠 Your Skills</h2>
    {"".join(f"<span class='tag'>{s.strip()}</span>" for s in (skills if isinstance(skills,list) else str(skills).split(",")) if s and str(s).strip()) or "<p style='color:#6b6b85;font-size:13px;'>Skills will appear shortly — refresh in a few seconds.</p>"}
  </div>

  {"<div class='card'><h2>💪 Strengths</h2><p style='font-size:14px;line-height:1.7;color:#c8e8f0;'>" + strengths + "</p></div>" if strengths else ""}
  {"<div class='card'><h2>📈 Areas to Grow</h2><p style='font-size:14px;line-height:1.7;color:#ffd580;'>" + weaknesses + "</p></div>" if weaknesses else ""}
  {"<div class='card'><h2>🔍 Skill Gaps</h2><p style='font-size:14px;color:#ff9999;'>" + skill_gaps + "</p></div>" if skill_gaps else ""}

  <div class="card">
    <h2>💼 Recommended Jobs</h2>
    {_render_jobs(sess_jobs, jobs_text, apply_url)}
  </div>

  <div class="card">
    <h2>📚 Learning Path</h2>
    {"<p style='font-size:14px;color:#a0c4ff;margin-bottom:12px;'>" + learning_path + "</p>" if learning_path else ""}
    {"<div class='section-label'>📖 Books</div><p style='font-size:13px;color:#9999b3;margin-bottom:10px;'>" + books + "</p>" if books else ""}
    {"<div class='section-label'>🎓 Courses</div><p style='font-size:13px;color:#9999b3;margin-bottom:10px;'>" + courses + "</p>" if courses else ""}
    {"<div class='section-label'>▶️ YouTube</div><p style='font-size:13px;color:#9999b3;'>" + youtube + "</p>" if youtube else ""}
  </div>

  {"<div class='card'><h2>🤖 AGI Mentor Feedback</h2><div class='feedback-box'>" + agi_feedback + "</div></div>" if agi_feedback else ""}

  <div class="cta">
    <a href="{interview}" class="btn">🎤 Start Mock Interview</a>
    <p style="color:#6b6b85;font-size:12px;margin-top:12px;">Interview link is valid for this session</p>
  </div>

  <!-- ── EMOTIONAL SUPPORT WIDGET ── -->
  <div class="card" style="border-color:rgba(255,107,107,0.25);background:linear-gradient(135deg,#12121a,#1a0f0f);">
    <h2 style="color:#ff6b6b;">💙 Feeling Rejected or Burned Out?</h2>
    <p style="font-size:14px;color:#9999b3;line-height:1.7;margin-bottom:16px;">
      Job rejections are painful. It's okay to feel exhausted, lost, or hopeless.
      Your AGI mentor is here — not to give career advice, but to <strong style="color:#ff9999;">listen and be with you</strong>.
    </p>
    <div id="supportChat" style="display:none;">
      <div id="chatMessages" style="background:#0a0a0f;border:1px solid rgba(255,107,107,0.15);border-radius:10px;padding:16px;min-height:120px;max-height:320px;overflow-y:auto;margin-bottom:12px;font-size:14px;line-height:1.7;"></div>
      <div style="display:flex;gap:8px;">
        <textarea id="supportInput" placeholder="Tell me how you're feeling right now..." rows="2"
          style="flex:1;background:#1a1a28;border:1px solid rgba(255,107,107,0.3);border-radius:8px;padding:10px 14px;color:#e8e8f0;font-family:inherit;font-size:13px;resize:none;outline:none;"></textarea>
        <button onclick="sendSupport()" id="sendBtn"
          style="background:#ff6b6b;color:#fff;border:none;border-radius:8px;padding:10px 18px;font-weight:700;cursor:pointer;font-size:13px;align-self:stretch;">Send</button>
      </div>
      <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;">
        <button onclick="quickMsg('I keep getting rejected and I feel like giving up')" class="quick-btn">😔 I want to give up</button>
        <button onclick="quickMsg('I feel like I am not good enough for any job')" class="quick-btn">💔 I feel worthless</button>
        <button onclick="quickMsg('I have been rejected 10+ times and I am completely exhausted')" class="quick-btn">😮‍💨 I am exhausted</button>
        <button onclick="quickMsg('Everyone around me got placed except me. I feel ashamed')" class="quick-btn">😶 I feel left behind</button>
      </div>
    </div>
    <button onclick="openSupport()" id="openSupportBtn"
      style="background:linear-gradient(135deg,#ff6b6b,#ff9966);color:#fff;border:none;padding:12px 28px;border-radius:8px;font-weight:700;font-size:14px;cursor:pointer;width:100%;margin-top:4px;">
      💙 Talk to Your AGI Mentor
    </button>
  </div>

</div>
<div class="footer">AGI Career System · Personalised Report for {name} · {datetime.datetime.now().strftime("%d %b %Y")}</div>

<style>
.quick-btn{{background:rgba(255,107,107,0.1);border:1px solid rgba(255,107,107,0.25);color:#ff9999;padding:6px 12px;border-radius:20px;font-size:12px;cursor:pointer;transition:all 0.2s;}}
.quick-btn:hover{{background:rgba(255,107,107,0.2);}}
.msg-ai{{background:rgba(108,99,255,0.1);border-left:3px solid #6c63ff;border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px;color:#c8c8f0;}}
.msg-user{{background:rgba(255,107,107,0.08);border-left:3px solid #ff6b6b;border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px;color:#ffc8c8;text-align:right;border-left:none;border-right:3px solid #ff6b6b;}}
.typing{{color:#6b6b85;font-style:italic;font-size:13px;padding:8px 14px;}}
</style>

<script>
const studentName = "{name}";
const studentDomain = "{domain}";
const chatHistory = [];

function openSupport() {{
  document.getElementById('supportChat').style.display = 'block';
  document.getElementById('openSupportBtn').style.display = 'none';
  // Opening message from AI
  appendAI(`Hi {name} 💙 I'm here with you. This isn't about your resume or your skills right now — it's about YOU. 
  
  Rejections hurt deeply, especially when you've worked so hard. You don't have to pretend you're okay. 
  
  Tell me honestly — how are you feeling right now?`);
}}

function quickMsg(text) {{
  document.getElementById('supportInput').value = text;
  sendSupport();
}}

function appendUser(msg) {{
  const div = document.createElement('div');
  div.className = 'msg-user';
  div.textContent = msg;
  document.getElementById('chatMessages').appendChild(div);
  scrollChat();
}}

function appendAI(msg) {{
  const div = document.createElement('div');
  div.className = 'msg-ai';
  div.innerHTML = msg.replace(/\\n/g,'<br>');
  document.getElementById('chatMessages').appendChild(div);
  scrollChat();
}}

function appendTyping() {{
  const div = document.createElement('div');
  div.className = 'typing';
  div.id = 'typingIndicator';
  div.textContent = '💙 Your mentor is thinking...';
  document.getElementById('chatMessages').appendChild(div);
  scrollChat();
}}

function removeTyping() {{
  const t = document.getElementById('typingIndicator');
  if(t) t.remove();
}}

function scrollChat() {{
  const c = document.getElementById('chatMessages');
  c.scrollTop = c.scrollHeight;
}}

async function sendSupport() {{
  const input = document.getElementById('supportInput');
  const msg = input.value.trim();
  if(!msg) return;
  input.value = '';
  document.getElementById('sendBtn').disabled = true;

  appendUser(msg);
  chatHistory.push({{"role":"user","content":msg}});
  appendTyping();

  try {{
    const res = await fetch('/emotional_support', {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{
        message: msg,
        name: studentName,
        domain: studentDomain,
        history: chatHistory.slice(-6)
      }})
    }});
    const data = await res.json();
    removeTyping();
    const reply = data.reply || "I'm here with you. Take a breath. You are not alone. 💙";
    appendAI(reply);
    chatHistory.push({{"role":"assistant","content":reply}});
  }} catch(e) {{
    removeTyping();
    appendAI("I'm here with you. Take a breath. You are seen, you are not alone. 💙");
  }}
  document.getElementById('sendBtn').disabled = false;
  document.getElementById('supportInput').focus();
}}

document.getElementById('supportInput')?.addEventListener('keydown', e => {{
  if(e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); sendSupport(); }}
}});
</script>
</body>
</html>"""
    from flask import Response
    return Response(html, mimetype="text/html")

@app.route("/fetch_indeed_jobs", methods=["POST"])
def fetch_indeed_jobs():
    """
    Proxy endpoint that calls Claude API with Indeed MCP to get real job listings.
    Called internally by fetch_jobs_from_indeed() during resume processing.
    """
    data     = request.get_json() or {}
    query    = data.get("query", "Software Engineer")
    location = data.get("location", "India")

    # Needs Anthropic API key for Claude + Indeed MCP
    api_key = ANTHROPIC_API_KEY
    if not api_key:
        print("  [Indeed] No ANTHROPIC_API_KEY set — skipping Indeed")
        return jsonify({"jobs": [], "error": "No Anthropic key"}), 200

    try:
        # Call Claude API with Indeed MCP server
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "mcp_servers": [
                    {
                        "type": "url",
                        "url":  "https://mcp.indeed.com/claude/mcp",
                        "name": "indeed"
                    }
                ],
                "messages": [{
                    "role":    "user",
                    "content": f"""Search Indeed for jobs matching: "{query}" in {location}.
Return results as a JSON array only, no other text:
[{{"title":"job title","company":"company name","location":"city","experience":"level","description":"brief description","url":"apply link","match":"0%"}}]
Get at least 8 jobs. Focus on fresher/entry level roles."""
                }]
            },
            timeout=30
        )

        if resp.status_code == 200:
            result = resp.json()
            # Extract text from response
            text = ""
            for block in result.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")

            # Parse JSON from response
            if text:
                s = text.find("["); e = text.rfind("]") + 1
                if s != -1 and e > s:
                    jobs = json.loads(text[s:e])
                    if isinstance(jobs, list) and jobs:
                        print(f"  [Indeed] ✅ {len(jobs)} real jobs from Indeed")
                        return jsonify({"jobs": jobs})

        print(f"  [Indeed] HTTP {resp.status_code} — no results")
        return jsonify({"jobs": []})

    except Exception as e:
        print(f"  [Indeed] Error: {e}")
        return jsonify({"jobs": []})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "AGI Career System Online"})


# ═══════════════════════════════════════════════════════
#  EMOTIONAL SUPPORT AI  →  /emotional_support (API)
# ═══════════════════════════════════════════════════════
@app.route("/emotional_support", methods=["POST"])
def emotional_support():
    """
    Deeply empathetic AI mentor — speaks to rejected, burned-out students.
    NOT a career bot. NOT a checklist. A human-feeling presence.
    """
    data     = request.get_json() or {}
    message  = data.get("message", "").strip()
    name     = data.get("name", "friend")
    domain   = data.get("domain", "")
    history  = data.get("history", [])

    if not message:
        return jsonify({"reply": "I'm here. Take your time. 💙"})

    system_prompt = f"""You are an emotionally intelligent AGI mentor named Arya.
You are talking to {name}, a student in the field of {domain or 'technology'} who is exhausted from job rejections.

Your ONLY job right now is to provide emotional support. NOT career advice. NOT to-do lists. NOT "here are 3 steps".

Your personality:
- Warm, gentle, deeply human
- You validate their pain without minimising it
- You speak like a wise, caring older sibling who has been through hard times
- You use their name naturally, not in every sentence
- You are honest — you don't give false hope or toxic positivity
- You ask ONE gentle question at a time to understand them better
- You never say "I understand how you feel" — you SHOW it through your words
- You use short paragraphs. Never bullet points. Never numbered lists.
- Sometimes you share a relatable truth about the job search journey
- You remind them of their worth as a PERSON, not just as a candidate
- You hold space for silence — it's okay if they just want to vent

Rules:
- Maximum 4 short paragraphs per response
- Never give resume or skill advice unless they explicitly ask
- Never say "as an AI" or "I am an AI"
- If they express thoughts of self-harm or extreme hopelessness, gently encourage them to speak to someone they trust and provide the iCall India helpline: 9152987821
- Always end with either a gentle question OR a single line of quiet encouragement — never both"""

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history for context
    for h in history[-8:]:
        role = h.get("role", "user")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Add current message
    messages.append({"role": "user", "content": message})

    try:
        reply = nvidia_client.call(
            messages=messages,
            temperature=0.85,   # warmer, more human
            max_tokens=400
        )
        if not reply:
            reply = f"I hear you, {name}. What you're feeling right now is real, and it matters. You don't have to explain yourself or justify your pain. I'm right here. 💙"
    except Exception as e:
        print(f"  [Emotional] Error: {e}")
        reply = f"I'm here with you, {name}. Rejections are genuinely painful — not a reflection of who you are. Take a breath. You are more than any job application. 💙"

    return jsonify({"reply": reply})


# ═══════════════════════════════════════════════════════
#  STANDALONE EMOTIONAL SUPPORT PAGE  →  /support
# ═══════════════════════════════════════════════════════
@app.route("/support")
def support_page():
    """Full-screen emotional support chat — shareable link for students."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AGI Mentor — Emotional Support</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',sans-serif;background:#0a0a0f;color:#e8e8f0;height:100vh;display:flex;flex-direction:column;}
  .topbar{background:linear-gradient(135deg,#1a0f1a,#0f1a1a);padding:16px 24px;border-bottom:1px solid rgba(255,107,107,0.15);display:flex;align-items:center;gap:12px;}
  .avatar{width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#ff6b6b,#6c63ff);display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0;}
  .mentor-info h2{font-size:15px;color:#fff;font-weight:600;}
  .mentor-info p{font-size:12px;color:#9999b3;}
  .online-dot{width:8px;height:8px;background:#00d4aa;border-radius:50%;display:inline-block;margin-right:4px;animation:pulse 2s infinite;}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
  .messages{flex:1;overflow-y:auto;padding:20px 16px;display:flex;flex-direction:column;gap:12px;max-width:700px;width:100%;margin:0 auto;}
  .msg{max-width:82%;padding:12px 16px;border-radius:12px;font-size:14px;line-height:1.7;}
  .msg-ai{background:rgba(108,99,255,0.1);border:1px solid rgba(108,99,255,0.2);border-radius:4px 12px 12px 12px;align-self:flex-start;color:#d0d0f0;}
  .msg-user{background:rgba(255,107,107,0.1);border:1px solid rgba(255,107,107,0.2);border-radius:12px 4px 12px 12px;align-self:flex-end;color:#ffd0d0;text-align:right;}
  .typing-msg{background:rgba(108,99,255,0.06);border:1px solid rgba(108,99,255,0.12);border-radius:4px 12px 12px 12px;align-self:flex-start;padding:12px 16px;color:#6b6b85;font-style:italic;font-size:13px;}
  .bottom{background:#0f0f1a;border-top:1px solid rgba(255,255,255,0.06);padding:16px;max-width:700px;width:100%;margin:0 auto;}
  .quick-row{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;}
  .quick{background:rgba(255,107,107,0.08);border:1px solid rgba(255,107,107,0.2);color:#ff9999;padding:5px 12px;border-radius:20px;font-size:11px;cursor:pointer;transition:all 0.2s;}
  .quick:hover{background:rgba(255,107,107,0.18);}
  .input-row{display:flex;gap:8px;}
  textarea{flex:1;background:#1a1a28;border:1px solid rgba(255,107,107,0.25);border-radius:10px;padding:10px 14px;color:#e8e8f0;font-family:inherit;font-size:14px;resize:none;outline:none;line-height:1.5;}
  textarea:focus{border-color:rgba(255,107,107,0.5);}
  .send-btn{background:linear-gradient(135deg,#ff6b6b,#ff9966);color:#fff;border:none;border-radius:10px;padding:10px 20px;font-weight:700;font-size:14px;cursor:pointer;align-self:stretch;min-width:72px;}
  .send-btn:disabled{opacity:0.4;cursor:not-allowed;}
  .name-modal{position:fixed;inset:0;background:rgba(0,0,0,0.85);display:flex;align-items:center;justify-content:center;z-index:100;padding:20px;}
  .name-card{background:#12121a;border:1px solid rgba(255,107,107,0.3);border-radius:16px;padding:32px;max-width:400px;width:100%;text-align:center;}
  .name-card h2{color:#ff9999;margin-bottom:8px;font-size:20px;}
  .name-card p{color:#9999b3;font-size:13px;margin-bottom:20px;line-height:1.6;}
  .name-input{width:100%;background:#1a1a28;border:1px solid rgba(255,107,107,0.3);border-radius:8px;padding:12px 16px;color:#fff;font-size:15px;outline:none;text-align:center;margin-bottom:14px;}
  .start-btn{width:100%;background:linear-gradient(135deg,#ff6b6b,#6c63ff);color:#fff;border:none;padding:12px;border-radius:8px;font-weight:700;font-size:15px;cursor:pointer;}
</style>
</head>
<body>

<!-- Name modal -->
<div class="name-modal" id="nameModal">
  <div class="name-card">
    <div style="font-size:40px;margin-bottom:12px;">💙</div>
    <h2>You are not alone.</h2>
    <p>Job rejections are painful. This is a safe space — no judgement, no advice unless you want it. Just someone to talk to.</p>
    <input class="name-input" id="nameInput" placeholder="What's your name?" maxlength="40">
    <button class="start-btn" onclick="startChat()">I'm ready to talk →</button>
  </div>
</div>

<div class="topbar">
  <div class="avatar">🤝</div>
  <div class="mentor-info">
    <h2>Arya — Your AGI Mentor</h2>
    <p><span class="online-dot"></span>Here for you, right now</p>
  </div>
</div>

<div class="messages" id="messages"></div>

<div class="bottom" style="display:none;" id="bottomBar">
  <div class="quick-row">
    <button class="quick" onclick="quick('I keep getting rejected and I want to give up')">😔 Want to give up</button>
    <button class="quick" onclick="quick('I feel like I am not smart enough')">💔 Feel not enough</button>
    <button class="quick" onclick="quick('Everyone got placed except me. I feel so ashamed')">😶 Left behind</button>
    <button class="quick" onclick="quick('I am completely exhausted from job hunting')">😮‍💨 Exhausted</button>
    <button class="quick" onclick="quick('I just need someone to talk to right now')">🤝 Just talk</button>
  </div>
  <div class="input-row">
    <textarea id="msgInput" rows="2" placeholder="Tell me how you're really feeling..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send();}"></textarea>
    <button class="send-btn" id="sendBtn" onclick="send()">Send</button>
  </div>
</div>

<script>
let userName = '';
const history = [];

function startChat() {
  const n = document.getElementById('nameInput').value.trim();
  userName = n || 'friend';
  document.getElementById('nameModal').style.display = 'none';
  document.getElementById('bottomBar').style.display = 'block';
  appendAI(`Hi ${userName} 💙 Thank you for being here and being honest with yourself — that takes courage.

This isn't about your resume right now. It's about you — the person behind all those applications, all that effort, all that hoping.

Tell me... what's been the hardest part of this journey for you?`);
}

document.getElementById('nameInput').addEventListener('keydown', e => {
  if(e.key === 'Enter') startChat();
});

function appendAI(msg) {
  const div = document.createElement('div');
  div.className = 'msg msg-ai';
  div.innerHTML = msg.replace(/\\n/g,'<br>');
  document.getElementById('messages').appendChild(div);
  scroll();
}
function appendUser(msg) {
  const div = document.createElement('div');
  div.className = 'msg msg-user';
  div.textContent = msg;
  document.getElementById('messages').appendChild(div);
  scroll();
}
function appendTyping() {
  const div = document.createElement('div');
  div.className = 'typing-msg';
  div.id = 'typing';
  div.textContent = 'Arya is with you...';
  document.getElementById('messages').appendChild(div);
  scroll();
}
function removeTyping() {
  const t = document.getElementById('typing');
  if(t) t.remove();
}
function scroll() {
  const m = document.getElementById('messages');
  m.scrollTop = m.scrollHeight;
}
function quick(text) {
  document.getElementById('msgInput').value = text;
  send();
}

async function send() {
  const input = document.getElementById('msgInput');
  const msg = input.value.trim();
  if(!msg) return;
  input.value = '';
  document.getElementById('sendBtn').disabled = true;

  appendUser(msg);
  history.push({role:'user', content:msg});
  appendTyping();

  try {
    const res = await fetch('/emotional_support', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message:msg, name:userName, domain:'', history:history.slice(-8)})
    });
    const data = await res.json();
    removeTyping();
    const reply = data.reply || `I'm right here with you, ${userName}. You are not alone in this. 💙`;
    appendAI(reply);
    history.push({role:'assistant', content:reply});
  } catch(e) {
    removeTyping();
    appendAI(`I'm here, ${userName}. Take a breath. You are seen. 💙`);
  }
  document.getElementById('sendBtn').disabled = false;
  document.getElementById('msgInput').focus();
}
</script>
</body>
</html>"""
    from flask import Response
    return Response(html, mimetype="text/html")

# ================= DEBUG ROUTE =====================
@app.route("/debug/<session_id>", methods=["GET"])
def debug_session(session_id):
    """Debug endpoint to check session question structure."""
    session = INTERVIEW_SESSIONS.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    qs = session.get("questions", {})
    technical = qs.get("technical", [])
    # Get unique topics
    topics = {}
    for q in technical:
        t = q.get("topic", "NO_TOPIC")
        topics[t] = topics.get(t, 0) + 1
    return jsonify({
        "name": session.get("name"),
        "skills": session.get("skills"),
        "total_technical": len(technical),
        "topics_found": topics,
        "aptitude": len(qs.get("aptitude", [])),
        "hr": len(qs.get("hr", [])),
        "logical": len(qs.get("logical", [])),
        "coding": len(qs.get("coding", [])),
        "sample_question": technical[0] if technical else None
    })




# ═══════════════════════════════════════════════════════
#  DRAG & DROP UPLOAD PAGE  →  /upload
# ═══════════════════════════════════════════════════════
@app.route("/upload")
@app.route("/")
def upload_page():
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AGI Career System — Upload Resume</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#0f0f1a 0%,#1a1a2e 50%,#16213e 100%);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
  .container{max-width:560px;width:100%;text-align:center}
  .logo{font-size:48px;margin-bottom:8px}
  h1{color:#fff;font-size:28px;font-weight:700;margin-bottom:6px}
  .sub{color:#8888aa;font-size:14px;margin-bottom:36px}
  .drop-zone{border:2px dashed #6c63ff;border-radius:16px;padding:48px 24px;background:rgba(108,99,255,0.05);cursor:pointer;transition:all 0.3s;position:relative}
  .drop-zone:hover,.drop-zone.dragover{border-color:#00d4aa;background:rgba(0,212,170,0.08)}
  .drop-zone input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
  .drop-icon{font-size:48px;margin-bottom:12px}
  .drop-text{color:#aaa;font-size:15px}
  .drop-text strong{color:#6c63ff}
  .file-name{margin-top:10px;color:#00d4aa;font-size:13px;font-weight:600}
  .btn{display:inline-block;margin-top:24px;background:linear-gradient(135deg,#6c63ff,#00d4aa);color:#fff;border:none;padding:14px 40px;border-radius:10px;font-size:16px;font-weight:700;cursor:pointer;width:100%;transition:opacity 0.2s}
  .btn:hover{opacity:0.9}
  .btn:disabled{opacity:0.4;cursor:not-allowed}
  .progress{display:none;margin-top:20px}
  .progress-bar{height:6px;background:#222;border-radius:3px;overflow:hidden}
  .progress-fill{height:100%;background:linear-gradient(90deg,#6c63ff,#00d4aa);width:0%;transition:width 0.4s;border-radius:3px}
  .status{color:#8888aa;font-size:13px;margin-top:10px}
  .result{display:none;margin-top:24px;background:rgba(0,212,170,0.08);border:1px solid rgba(0,212,170,0.3);border-radius:12px;padding:20px}
  .result h3{color:#00d4aa;margin-bottom:12px;font-size:16px}
  .link-btn{display:block;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:700;font-size:14px;margin-bottom:10px;transition:opacity 0.2s}
  .link-btn:hover{opacity:0.85}
  .report-btn{background:#6c63ff;color:#fff}
  .interview-btn{background:#00d4aa;color:#111}
  .features{display:flex;gap:12px;margin-top:24px;flex-wrap:wrap;justify-content:center}
  .feat{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:12px 16px;font-size:12px;color:#8888aa;flex:1;min-width:120px}
  .feat .icon{font-size:20px;margin-bottom:4px}
</style>
</head>
<body>
<div class="container">
  <div class="logo">🎓</div>
  <h1>AGI Career System</h1>
  <p class="sub">Upload your resume and get a personalised career report + mock interview in 60 seconds</p>

  <div class="drop-zone" id="dropZone">
    <input type="file" id="fileInput" accept=".pdf,.docx" onchange="fileSelected(this)">
    <div class="drop-icon">📄</div>
    <div class="drop-text">Drag & drop your resume here<br><strong>or click to browse</strong></div>
    <div class="file-name" id="fileName"></div>
  </div>

  <button class="btn" id="uploadBtn" onclick="uploadResume()" disabled>
    🚀 Analyse My Resume
  </button>

  <div class="progress" id="progressDiv">
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    <div class="status" id="statusText">Uploading...</div>
  </div>

  <div class="result" id="resultDiv">
    <h3>✅ Your links are ready!</h3>
    <a id="reportLink" class="link-btn report-btn" href="#" target="_blank">📋 View Career Report</a>
    <a id="interviewLink" class="link-btn interview-btn" href="#" target="_blank">🎤 Start Mock Interview</a>
    <p style="color:#666;font-size:11px;margin-top:8px;">⏳ Full analysis completes in ~60 seconds. Refresh the report if it shows loading.</p>
  </div>

  <div class="features">
    <div class="feat"><div class="icon">🤖</div>Gemini + Groq AI</div>
    <div class="feat"><div class="icon">💼</div>Real Job Matches</div>
    <div class="feat"><div class="icon">🎤</div>200 Questions</div>
    <div class="feat"><div class="icon">📊</div>Confidence Meter</div>
  </div>
</div>

<script>
const dropZone = document.getElementById('dropZone');
let selectedFile = null;

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
});

function fileSelected(input) { if (input.files[0]) setFile(input.files[0]); }

function setFile(f) {
  selectedFile = f;
  document.getElementById('fileName').textContent = '📎 ' + f.name;
  document.getElementById('uploadBtn').disabled = false;
}

async function uploadResume() {
  if (!selectedFile) return;
  const btn = document.getElementById('uploadBtn');
  btn.disabled = true;
  btn.textContent = '⏳ Uploading...';

  const prog = document.getElementById('progressDiv');
  const fill = document.getElementById('progressFill');
  const status = document.getElementById('statusText');
  prog.style.display = 'block';

  // Animate progress
  let pct = 0;
  const steps = [
    [10, 'Uploading resume...'],
    [30, 'Extracting text & skills...'],
    [60, 'AI analysis in progress...'],
    [85, 'Generating interview questions...'],
    [95, 'Almost done...']
  ];
  let si = 0;
  const interval = setInterval(() => {
    if (si < steps.length) {
      pct = steps[si][0]; status.textContent = steps[si][1]; si++;
    }
    fill.style.width = pct + '%';
  }, 1200);

  try {
    const form = new FormData();
    form.append('resume', selectedFile);
    const res = await fetch('/uploadresume', { method: 'POST', body: form });
    const data = await res.json();
    clearInterval(interval);
    fill.style.width = '100%';
    status.textContent = '✅ Done!';

    if (data.interview_link) {
      const report = data.interview_link.replace('/interview/', '/report/');
      document.getElementById('reportLink').href = report;
      document.getElementById('interviewLink').href = data.interview_link;
      document.getElementById('resultDiv').style.display = 'block';
      btn.textContent = '✅ Upload another resume';
      btn.disabled = false;
    } else {
      status.textContent = '❌ Error: ' + (data.error || 'Upload failed');
      btn.textContent = '🚀 Try Again'; btn.disabled = false;
    }
  } catch(e) {
    clearInterval(interval);
    status.textContent = '❌ Connection error — is Flask running?';
    btn.textContent = '🚀 Try Again'; btn.disabled = false;
  }
}
</script>
</body>
</html>"""
    from flask import Response
    return Response(html, mimetype="text/html")


# ═══════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    os.makedirs("interview_app", exist_ok=True)
    init_db()

    print("  [Upload] Resume upload → http://localhost:5000/upload")
    app.run(debug=True, port=5000)