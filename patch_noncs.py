"""
patch_noncs.py — Run this in your project folder:
    python patch_noncs.py

Fixes inaccurate output for non-CS students (Medical, Law, Finance, Engineering etc.)
"""
import re

print("Reading app.py...")
with open("app.py", encoding="utf-8") as f:
    content = f.read()

fixes = 0

# ── FIX 1: Domain-aware question generation ──
old1 = '''def questions_for_skill(skill, resume_context, career, domain, level):
    level_label = {1: "beginner — definitions, basic concepts, fundamentals", 2: "intermediate — practical application, real scenarios", 3: "advanced — deep expertise, edge cases, design decisions"}
    prompt = f"""Expert interviewer generating interview questions.

CANDIDATE BACKGROUND:
{resume_context}

Generate exactly 10 interview questions about: {skill}
Difficulty: Level {level} — {level_label[level]}
Field: {domain} | Role: {career}

Rules:
1. Questions must be specific to "{skill}" for THIS candidate's background
2'''

if old1 in content:
    new1 = '''def questions_for_skill(skill, resume_context, career, domain, level):
    level_label = {1: "beginner — definitions, basic concepts, fundamentals", 2: "intermediate — practical application, real scenarios", 3: "advanced — deep expertise, edge cases, design decisions"}
    # Domain-aware question style
    domain_lower = domain.lower()
    is_tech = any(w in domain_lower for w in ["computer","software","data","ai","machine","deep","nlp","cyber","cloud","web","devops","electronics","programming"])
    q_style = "technical coding and implementation questions" if is_tech else f"conceptual, scenario-based, case-study questions relevant to real {domain} interviews — NOT software or coding questions"
    prompt = f"""You are a senior interviewer in the field of {domain}. Generate interview questions.

CANDIDATE BACKGROUND:
{resume_context}

Generate exactly 10 interview questions about: {skill}
Difficulty: Level {level} — {level_label[level]}
Field: {domain} | Role: {career}
Question style: {q_style}

Rules:
1. Questions must be specific to "{skill}" as used in {domain}
2. Do NOT ask Python/coding questions unless domain is tech/CS
3'''
    content = content.replace(old1, new1, 1)
    print("✅ Fix 1: questions_for_skill is now domain-aware")
    fixes += 1
else:
    print("⚠️  Fix 1: questions_for_skill pattern not found — may already be applied")

# ── FIX 2: Domain-specific aptitude questions ──
old2 = 'Candidate: {career}. Level 1=easy 2=medium 3=hard."""'
new2 = '''Candidate: {career} in {domain}. Level 1=easy 2=medium 3=hard.
Make aptitude questions relevant to {domain} field — not generic."""'''

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("✅ Fix 2: Aptitude questions now domain-specific")
    fixes += 1
else:
    print("⚠️  Fix 2: Aptitude pattern not found — may already be applied")

# ── FIX 3: Skills extraction — support non-CS domains ──
old3 = '"skills": ["ONLY real technical skills/tools/languages/frameworks — e.g. Python, TensorFlow, SQL, React, Git. STRICTLY EXCLUDE: degree names, school names, education qualifications, board names, 10th, 12th, Intermediate, MPC, B.Tech, M.Tech, college names, CGPA, percentages"],'
new3 = '"skills": ["Extract ALL professional skills for this candidate\'s field. CS/Tech: Python, TensorFlow, SQL. Medical: Anatomy, Pharmacology, Patient Care. Law: Contract Law, IPC, Legal Research. Finance: Financial Modeling, Tally, GST. Mechanical: AutoCAD, SolidWorks, Thermodynamics. STRICTLY EXCLUDE: degree names, school names, 10th, 12th, Intermediate, B.Tech, college names, CGPA"],'

if old3 in content:
    content = content.replace(old3, new3, 1)
    print("✅ Fix 3: Skills extraction works for all domains")
    fixes += 1
else:
    print("⚠️  Fix 3: Skills extraction pattern not found — may already be applied")

# ── FIX 4: Domain field in ai_analyze ──
old4 = '"domain": "Primary technical field — e.g. \'Machine Learning\', \'Data Science\', \'Computer Science\', \'Web Development\'",'
new4 = '"domain": "The candidate\'s primary professional field — e.g. \'Machine Learning\', \'Civil Engineering\', \'Medicine\', \'Finance\', \'Law\', \'Education\', \'Mechanical Engineering\', \'Pharmacy\'. Be specific to their actual background.",'

if old4 in content:
    content = content.replace(old4, new4, 1)
    print("✅ Fix 4: Domain detection improved for non-CS")
    fixes += 1
else:
    print("⚠️  Fix 4: Domain field not found — may already be applied")

# ── FIX 5: has_coding — non-CS students don't get coding questions ──
old5 = "has_coding = any(kw in resume_lower for kw in coding_kw)"
new5 = """# Only generate coding questions for tech/CS domains
    domain_lower_check = domain.lower()
    is_tech_domain = any(w in domain_lower_check for w in ["computer","software","data","ai","machine","deep","nlp","cyber","cloud","web","devops","electronics","programming","information technology"])
    has_coding = is_tech_domain and any(kw in resume_lower for kw in coding_kw)"""

if old5 in content:
    content = content.replace(old5, new5, 1)
    print("✅ Fix 5: Coding questions only for tech domains")
    fixes += 1
else:
    print("⚠️  Fix 5: has_coding pattern not found — may already be applied")

# Write fixed file
with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print(f"\n✅ Done! {fixes} fixes applied to app.py")
print("Restart Flask: python app.py")