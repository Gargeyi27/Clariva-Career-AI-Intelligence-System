"""
patch_learning_ollama.py
Run in your project folder: python patch_learning_ollama.py

Fixes:
1. Learning path now domain-specific (Medical/Law/Finance/Engineering)
2. Ollama auto-reconnects after 30s instead of staying disabled
"""

with open("app.py", encoding="utf-8") as f:
    content = f.read()

fixes = 0

# ══════════════════════════════════════════════
# FIX 1: OLLAMA AUTO-RECONNECT
# ══════════════════════════════════════════════

# Stop Ollama from staying disabled permanently after one connection error
old_ollama_err = '''        except requests.exceptions.ConnectionError:
            print("  [Ollama] \u274c Connection refused - is ollama running?")
            self.ollama_ok = False'''

new_ollama_err = '''        except requests.exceptions.ConnectionError:
            print("  [Ollama] Not running - switching to Groq (will retry in 30s)")
            self.ollama_ok = False
            self._ollama_retry_at = __import__('time').time() + 30'''

if old_ollama_err in content:
    content = content.replace(old_ollama_err, new_ollama_err, 1)
    print("✅ Fix 1a: Ollama retry timer set to 30s")
    fixes += 1
else:
    print("⚠️  Fix 1a: Ollama ConnectionError block not found")

# Auto-recheck Ollama after cooldown
old_tier1 = "        if OLLAMA_ENABLED and self.ollama_ok:"
new_tier1 = """        # Auto-retry Ollama after 30s cooldown
        import time as _t
        if OLLAMA_ENABLED and not self.ollama_ok:
            if _t.time() > getattr(self, '_ollama_retry_at', 0):
                self.ollama_ok = self._check_ollama()
                if self.ollama_ok:
                    print("  [Ollama] Back online!")
        if OLLAMA_ENABLED and self.ollama_ok:"""

if old_tier1 in content and "Auto-retry Ollama" not in content:
    content = content.replace(old_tier1, new_tier1, 1)
    print("✅ Fix 1b: Ollama auto-reconnect logic added")
    fixes += 1
else:
    print("⚠️  Fix 1b: Already applied or not found")

# ══════════════════════════════════════════════
# FIX 2: DOMAIN-SPECIFIC LEARNING PATH
# ══════════════════════════════════════════════

old_resources = '''def learning_resources_agent(analysis):
    print("  [C] Generating learning resources...")
    skills = safe_cell(analysis.get("skills", [])); skill_gaps = analysis.get("skill_gaps", ""); career_fit = safe_cell(analysis.get("career_fit", []))
    prompt = f"""Create a learning plan. Return ONLY valid JSON:
{{"books":["Book Title by Author","Book2 by Author2","Book3 by Author3"],"courses":["Course Name on Platform - URL","Course2 on Platform2"],"youtube":["Channel Name - topic","Channel2 - topic2"],"websites":["sitename.com - purpose","site2.com - purpose2"],"learning_path":"Week 1: Topic. Week 2: Topic. Week 3: Topic. Week 4: Topic.","mindmap":"Core Skill -> Sub1, Sub2, Sub3 | Related -> A, B, C"}}
Skills: {skills}
Gaps: {skill_gaps}
Career: {career_fit}\""""'''

new_resources = '''def learning_resources_agent(analysis):
    print("  [C] Generating learning resources...")
    skills     = safe_cell(analysis.get("skills", []))
    skill_gaps = analysis.get("skill_gaps", "")
    career_fit = safe_cell(analysis.get("career_fit", []))
    domain     = analysis.get("domain", "General")
    domain_cat = get_domain_category(domain)

    hints = {
        "medical":    "Gray's Anatomy, UpToDate.com, Armando Hasudungan YouTube, TeachMeMedicine.org",
        "nursing":    "Nursing textbooks, RegisteredNurseRN YouTube, NursingCenter.com",
        "pharmacy":   "Katzung Pharmacology, PharmaFactz YouTube, PharmacyTimes.com",
        "law":        "Bare Acts, SCC Online, Legal Bites YouTube, IndianKanoon.org",
        "finance":    "Security Analysis by Graham, CA Rachana Ranade YouTube, Zerodha Varsity",
        "marketing":  "Kotler Marketing, Neil Patel YouTube, HubSpot Academy",
        "hr":         "Armstrong HR Practice, HR Cabin YouTube, SHRM Learning",
        "mechanical": "Shigley Machine Design, NPTEL Mechanical, Lesics YouTube",
        "civil":      "IS Codes, NPTEL Civil, Civil Tutor YouTube, AutoCAD guides",
        "electrical": "Chapman Electric Machinery, NPTEL EE, Engineering Mindset YouTube",
        "electronics":"Sedra Smith, NPTEL ECE, EEVblog YouTube, Electronics Hub",
        "education":  "Teaching to Transgress, Edutopia YouTube, Coursera Education",
        "psychology": "DSM-5, Psych2Go YouTube, SimplyPsychology.org",
        "architecture":"Francis Ching Architecture, 30X40 Design YouTube, ArchDaily",
        "agriculture": "Principles of Agronomy, ICAR e-courses, Kisan Suvidha YouTube",
        "biotechnology":"Molecular Biology of Cell, Shomu Biology YouTube, NCBI",
        "mathematics": "3Blue1Brown YouTube, Khan Academy, MIT OpenCourseWare",
    }.get(domain_cat, f"top books, courses, and YouTube channels for {domain}")

    prompt = f"""Create a personalised learning roadmap for a {domain} student.
Return ONLY valid JSON:
{{"books":["Book specific to {domain} by Author","Book2","Book3"],"courses":["Course for {domain} on Platform","Course2"],"youtube":["Channel - {domain} topics","Channel2"],"websites":["site.com - how it helps {domain} students","site2.com"],"learning_path":"Week 1: {domain} foundation. Week 2: Core concepts. Week 3: Practice. Week 4: Projects.","mindmap":"Core {domain} -> Sub1, Sub2, Sub3 | Career -> {career_fit}"}}
Profile: Field={domain} | Skills={skills} | Gaps={skill_gaps} | Goal={career_fit}
Use these resources: {hints}
Make ALL recommendations specific to {domain}. Do NOT suggest coding/programming unless domain is tech.\""""'''

if old_resources in content:
    content = content.replace(old_resources, new_resources, 1)
    print("✅ Fix 2: Learning resources now domain-specific")
    fixes += 1
else:
    print("⚠️  Fix 2: learning_resources_agent pattern not found")
    print("   Trying alternate match...")
    # Try finding just the function start
    if 'def learning_resources_agent' in content:
        idx = content.find('def learning_resources_agent')
        print(f"   Function found at line {content[:idx].count(chr(10))+1}")
        print(f"   First 200 chars: {repr(content[idx:idx+200])}")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print(f"\n{'='*50}")
print(f"✅ Done! {fixes} fixes applied.")
print("Restart: python app.py")