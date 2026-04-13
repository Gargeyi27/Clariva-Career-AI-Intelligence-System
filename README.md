#  Clariva — AI-Powered Career Intelligence Platform

> **Upload your resume. Get an ATS score, personalised job matches, 145 mock interview questions, skill-gap analysis, and emotional support — all in under 30 seconds.**

---

##  What Makes This Different

Most career tools are just wrappers around a single LLM API. Clariva is **offline-first** with a 3-tier AI chain that never fully goes down:

| Priority | Provider | Role |
|---|---|---|
| **1st** | Ollama (local) | Primary — free, offline, zero latency |
| **2nd** | Groq (5-key rotation) | Cloud fallback — fast, handles rate limits |
| **3rd** | `ai_engine.py` | Zero-API fallback — pure Python, always works |

---

##  Features

| Feature | Description |
|---|---|
|  **ATS Resume Scorer** | Scores across 7 parameters: contact info, action verbs, quantified impact, skills density, education, projects, keyword match |
|  **AI Resume Modifier** | Rewrites bullets with role-specific keywords for any job description |
|  **Mock Interview** | 145 personalised questions across ML, DL, GenAI, HR, aptitude, and coding with voice recording + playback |
|  **Company-Specific Mode** | Tailored prep for Google, Amazon, TCS, Sarvam AI, Quantiphi, Razorpay, Fractal, and more |
|  **Weak Area Retry** | Tracks topics scored below 5/10 and drills only those |
|  **AI Decision Engine** | 5-factor job ranking: skill overlap, inferred skills, experience fit, domain relevance, career-fit title match |
|  **Emotional Support Chatbot** | Career counsellor persona for placement stress and burnout |
|  **Career Report** | Full report: ATS score + job matches + skill gaps + learning path + mentor feedback letter |
|  **Batch Upload** | Process 500 student resumes concurrently (for college placements) |

---

##  Architecture

```
Resume PDF
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              3-Tier AI Chain                         │
│  Ollama (local) → Groq (cloud) → ai_engine (local)  │
└─────────────────────────────────────────────────────┘
    │
    ├── ResumeAgent     → Parses name, skills, domain, projects
    ├── SkillEngine     → Skill Graph inference (implicit skills)
    ├── DecisionEngine  → 5-factor job ranking + explainability
    ├── InterviewEngine → 145 questions + local answer evaluation
    └── GapIntelligence → Priority gaps + free learning resources
```

---

##  Getting Started

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) installed locally (recommended)
- At least one [Groq API key](https://console.groq.com) (free)

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/career-agi-backend.git
cd career-agi-backend
```

### 2. Create a virtual environment
```bash
python -m venv venv
venv\Scripts\activate   # Windows
# or
source venv/bin/activate  # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
# Edit .env and fill in your keys
```

### 5. Pull the Ollama model (recommended)
```bash
ollama pull qwen2.5:3b
ollama serve
```

### 6. Run the app
```bash
python app.py
```
Visit `http://localhost:5000`

---

## Environment Variables

Copy `.env.example` → `.env` and fill in your keys.

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY_1` to `_5` | Recommended | Groq API keys — up to 5 for rotation. Free at [console.groq.com](https://console.groq.com) |
| `OLLAMA_BASE_URL` | Optional | Default: `http://localhost:11434` |
| `OLLAMA_MODEL` | Optional | Default: `qwen2.5:3b` |
| `MONGODB_URI` | Optional | For persistent storage. Free at [MongoDB Atlas](https://mongodb.com/atlas) |
| `GEMINI_API_KEY` | Optional | 1500 free requests/day at [aistudio.google.com](https://aistudio.google.com) |
| `JSEARCH_API_KEY` | Optional | For live job listings via RapidAPI |

>  The app works **without any API keys** — `ai_engine.py` handles everything locally.

---

## Project Structure

```
career-agi-backend/
├── app.py              # Main Flask app — all routes and HTML pages
├── ai_engine.py        # Offline AI layer: Skill Graph, Decision Engine, Gap Intelligence
├── dashboard.py        # College dashboard for batch results
├── batch_upload.py     # Bulk resume processing (500 concurrent)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── interview_app/      # Static assets
```

---

##  Tech Stack

- **Backend:** Python, Flask, pdfplumber, pymongo
- **AI (Primary):** Ollama — `qwen2.5:3b` (local, offline)
- **AI (Fallback):** Groq — `llama-3.3-70b`, `llama-3.1-8b`
- **Custom AI:** `ai_engine.py` — Skill Graph, Decision Engine, Local Evaluator
- **Database:** MongoDB Atlas (optional), SQLite (local fallback)
- **Frontend:** Vanilla HTML/CSS/JS (embedded in Flask)

---

##  Key Numbers

- **145** personalised interview questions generated per resume
- **7** ATS scoring parameters
- **5-factor** job ranking algorithm
- **10+** company-specific interview profiles
- **500** resumes processable concurrently (batch mode)
- **30 seconds** end-to-end analysis time
- **3-tier** AI fallback chain — zero single point of failure

---

##  Contributing

PRs welcome! Please:
1. Never commit `.env` or any file with real API keys
2. Run `python app.py` locally and verify your changes
3. Keep `ai_engine.py` API-free (pure Python only)
 
  website link: https://future-forge-clariva.lovable.app
---





*Built by Gargeyi — Clariva © 2026*
