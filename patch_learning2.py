"""
patch_learning2.py
Run: python patch_learning2.py

Fixes:
1. Learning path domain-specific (Medical/Law/Finance/Mechanical etc.)
2. Ollama ConnectionError retry (alternate pattern match)
"""
import re

with open("app.py", encoding="utf-8") as f:
    content = f.read()

fixes = 0

# ══════════════════════════════════════════════
# FIX 1: OLLAMA CONNECTION ERROR - find exact pattern
# ══════════════════════════════════════════════
# Find the ConnectionError handler in _ollama_call
patterns_to_try = [
    "self.ollama_ok = False\n        except requests.exceptions.Timeout:",
    "self.ollama_ok = False\n            return None\n        except requests.exceptions.Timeout:",
]

for p in patterns_to_try:
    if p in content:
        new_p = p.replace(
            "self.ollama_ok = False",
            "self.ollama_ok = False\n            self._ollama_retry_at = __import__('time').time() + 30"
        )
        content = content.replace(p, new_p, 1)
        print("✅ Fix 1: Ollama ConnectionError now sets 30s retry timer")
        fixes += 1
        break
else:
    # Try finding by searching for ollama_ok = False inside _ollama_call
    idx_fn = content.find("def _ollama_call")
    idx_end = content.find("\n    def _groq_call", idx_fn)
    fn_block = content[idx_fn:idx_end]
    if "self.ollama_ok = False" in fn_block:
        old_line = "self.ollama_ok = False"
        new_line = "self.ollama_ok = False\n            self._ollama_retry_at = __import__('time').time() + 30"
        # Only replace inside the function
        new_block = fn_block.replace(old_line, new_line, 1)
        content = content[:idx_fn] + new_block + content[idx_end:]
        print("✅ Fix 1: Ollama retry timer added (via function search)")
        fixes += 1
    else:
        print("⚠️  Fix 1: Already applied or not found")

# ══════════════════════════════════════════════
# FIX 2: LEARNING RESOURCES - replace entire function body
# ══════════════════════════════════════════════
idx = content.find("def learning_resources_agent(analysis):")
if idx < 0:
    print("❌ Fix 2: learning_resources_agent not found")
else:
    # Find the end of the function (next def at same indent level)
    end_idx = content.find("\n\ndef ", idx + 10)
    if end_idx < 0:
        end_idx = content.find("\n@app.route", idx + 10)
    
    old_fn = content[idx:end_idx]
    
    new_fn = '''def learning_resources_agent(analysis):
    print("  [C] Generating learning resources...")
    skills     = safe_cell(analysis.get("skills", []))
    skill_gaps = analysis.get("skill_gaps", "")
    career_fit = safe_cell(analysis.get("career_fit", []))
    domain     = analysis.get("domain", "General")
    domain_cat = get_domain_category(domain)

    # Domain-specific resource hints
    hints = {
        "medical":      "Gray's Anatomy, Harrison's Principles, UpToDate.com, TeachMeMedicine.org, Armando Hasudungan YouTube, Ninja Nerd Science YouTube",
        "nursing":      "Kozier and Erb's Nursing, RegisteredNurseRN YouTube, NursingCenter.com, NCLEX prep resources",
        "pharmacy":     "Katzung Basic and Clinical Pharmacology, PharmaFactz YouTube, PharmacyTimes.com, GPAT prep",
        "law":          "Constitution of India, IPC Bare Act, Contract Law by Pollock, SCC Online, Legal Bites YouTube, IndianKanoon.org",
        "finance":      "Security Analysis by Graham, CA Rachana Ranade YouTube, Zerodha Varsity free course, NSEIndia.com",
        "marketing":    "Marketing Management by Kotler, Neil Patel YouTube, HubSpot Academy free courses, Google Digital Garage",
        "hr":           "Armstrong's Handbook of HRM, HR Cabin YouTube, SHRM Learning, LinkedIn Learning HR courses",
        "business":     "The Lean Startup, Josh Kaufman Personal MBA, Harvard Business Review, Coursera Business courses",
        "mechanical":   "Shigley's Mechanical Engineering Design, NPTEL Mechanical YouTube, Lesics YouTube, EngineeringToolBox.com",
        "civil":        "IS Codes, Structural Analysis by Bhavikatti, NPTEL Civil YouTube, Civil Tutor YouTube, StaadPro tutorials",
        "electrical":   "Chapman Electric Machinery, NPTEL EE YouTube, The Engineering Mindset YouTube, CircuitDigest.com",
        "electronics":  "Sedra Smith Microelectronics, NPTEL ECE YouTube, EEVblog YouTube, Electronics Hub",
        "education":    "Teaching to Transgress by bell hooks, Edutopia YouTube, Coursera Education courses, TED-Ed",
        "psychology":   "DSM-5, Abnormal Psychology by Kring, Psych2Go YouTube, Coursera Psychology, SimplyPsychology.org",
        "journalism":   "AP Stylebook, Poynter.org, Reuters Journalism training, Coursera Journalism courses",
        "architecture": "Architecture Form Space Order by Ching, 30X40 Design YouTube, ArchDaily.com, AutoCAD tutorials",
        "agriculture":  "Principles of Agronomy, ICAR e-courses, Kisan Suvidha YouTube, AgriHunt.com",
        "biotechnology":"Molecular Biology of the Cell, Shomu Biology YouTube, CSIR NET prep, NCBI resources",
        "mathematics":  "3Blue1Brown YouTube, Khan Academy, MIT OpenCourseWare, Paul's Online Math Notes",
        "chemistry":    "Clayden Organic Chemistry, Organic Chemistry Tutor YouTube, NPTEL Chemistry, ChemLibreTexts",
        "physics":      "Halliday Resnick, MIT OCW Physics, Eugene Khutoryansky YouTube, Physics Classroom",
    }.get(domain_cat, f"top books, courses, and YouTube channels for {domain} professionals in India")

    prompt = f"""Create a personalised learning roadmap for a {domain} student targeting {career_fit}.
Return ONLY valid JSON (no extra text):
{{"books":["Specific book for {domain} by Author - why it helps","Book2 by Author","Book3 by Author"],"courses":["Specific {domain} course on Platform - what you learn","Course2 on Platform2","Course3"],"youtube":["Channel Name - specific {domain} topics it covers","Channel2 - topics","Channel3"],"websites":["sitename.com - exactly how it helps {domain} students","site2.com - what it offers","site3.com"],"learning_path":"Week 1: Specific {domain} foundation topic. Week 2: Core concept from {domain}. Week 3: Practical application. Week 4: Project or certification.","mindmap":"Core {domain} -> Topic1, Topic2, Topic3 | Advanced -> A1, A2 | Career -> {career_fit}"}}

Student profile:
- Field: {domain}
- Current skills: {skills}
- Skill gaps to address: {skill_gaps}
- Career target: {career_fit}

Recommended {domain} resources to reference: {hints}

CRITICAL: ALL recommendations must be specific to {domain}.
Do NOT suggest Python, machine learning, or programming courses unless domain is CS/tech."""

    result = groq_json(prompt, max_tokens=1500, use_ollama=False)
    if not result:
        # Local domain-specific fallback when API unavailable
        fallback = {
            "medical":    {"books":["Gray's Anatomy","Harrison's Principles of Internal Medicine","Kumar & Clark's Clinical Medicine"],"courses":["Clinical Medicine on Coursera","USMLE prep on Amboss"],"youtube":["Armando Hasudungan","Ninja Nerd Science","Dr. Najeeb Lectures"],"websites":["UpToDate.com","TeachMeMedicine.org","MedScape.com"]},
            "law":        {"books":["Constitution of India","IPC Bare Act","Introduction to Jurisprudence by Dias"],"courses":["Legal Reasoning on Coursera","Bar Exam prep on Unacademy"],"youtube":["Legal Bites","Law Guru India","LexBites"],"websites":["IndianKanoon.org","SCC Online","LatestLaws.com"]},
            "finance":    {"books":["Security Analysis by Graham","Intelligent Investor","CA Study Material"],"courses":["Financial Modeling on Coursera","CFA prep on Kaplan"],"youtube":["CA Rachana Ranade","Pranjal Kamra","Zerodha Varsity"],"websites":["Zerodha.com/varsity","MoneyControl.com","NSEIndia.com"]},
            "mechanical": {"books":["Shigley's Mechanical Engineering Design","Engineering Thermodynamics by PK Nag"],"courses":["NPTEL Mechanical Engineering","AutoCAD on Coursera"],"youtube":["Lesics","NPTEL Mechanical","Engineering Explained"],"websites":["NPTEL.ac.in","EngineeringToolBox.com","GrabCAD.com"]},
            "civil":      {"books":["Structural Analysis by Bhavikatti","IS 456 Code","Soil Mechanics by Arora"],"courses":["NPTEL Civil Engineering","STAAD Pro tutorials"],"youtube":["Civil Tutor","NPTEL Civil","Structural Engineering YouTube"],"websites":["NPTEL.ac.in","IStructE.org","IS-Codes.com"]},
            "law":        {"books":["Constitution of India","IPC Bare Act","Contract Law by Anson"],"courses":["Legal Reasoning on Unacademy","Bar prep on iProledge"],"youtube":["Legal Bites","LexBites","Law Simplified"],"websites":["IndianKanoon.org","SCC Online","Manupatra.com"]},
        }
        domain_res = fallback.get(domain_cat, {
            "books": [f"Introduction to {domain}", f"Professional {domain} Guide", f"Advanced {domain} Concepts"],
            "courses": [f"{domain} fundamentals on Coursera", f"Professional {domain} certification on Udemy"],
            "youtube": [f"{domain} tutorials channel", "NPTEL lectures"],
            "websites": [f"Professional {domain} association", "NPTEL.ac.in"],
        })
        result = {
            **domain_res,
            "learning_path": f"Week 1: {domain} foundations. Week 2: Core concepts. Week 3: Practical application. Week 4: Projects and certifications.",
            "mindmap": f"{domain} -> Core Skills, Theory, Practice | Career -> {career_fit}"
        }
        print(f"  [C] Using local {domain_cat} resource fallback")
    print("  [C] Resources generated.")
    return result'''

    content = content[:idx] + new_fn + content[end_idx:]
    print("✅ Fix 2: learning_resources_agent fully replaced with domain-specific version")
    fixes += 1

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print(f"\n{'='*50}")
print(f"✅ Done! {fixes} fixes applied.")
print("Restart: python app.py")