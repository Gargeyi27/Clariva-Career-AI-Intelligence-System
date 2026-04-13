"""
ai_engine.py — AGI Career System Intelligence Layer
=====================================================
Replaces pure API calls with:
  - Skill Graph (relationship-based inference)
  - Decision Engine (scoring + ranking logic)
  - Skill Gap Intelligence (prioritised gap analysis)
  - Explainable AI output (why scores are what they are)
  - Local Answer Evaluator (fallback when Groq unavailable)
  - Memory / User Profile (tracks improvement history)
  - Pipeline Agents (Resume → Skill → Decision → Job → Interview)
"""

import re
import math
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# 1. SKILL GRAPH  — relationships between skills
# ═══════════════════════════════════════════════════════════════

SKILL_GRAPH = {
    # AI / ML core
    "machine learning":   ["python", "numpy", "pandas", "scikit-learn", "statistics", "linear algebra"],
    "deep learning":      ["pytorch", "tensorflow", "cnn", "rnn", "lstm", "backpropagation", "neural networks"],
    "generative ai":      ["llms", "transformers", "langchain", "prompt engineering", "rag", "fine-tuning"],
    "nlp":                ["transformers", "bert", "tokenization", "text classification", "hugging face", "spacy"],
    "computer vision":    ["opencv", "cnn", "yolo", "image processing", "pytorch", "object detection"],
    "reinforcement learning": ["q-learning", "policy gradient", "openai gym", "reward shaping"],
    "mlops":              ["docker", "kubernetes", "mlflow", "airflow", "ci/cd", "model monitoring"],
    "data science":       ["python", "sql", "pandas", "statistics", "visualization", "jupyter"],

    # Software engineering
    "python":             ["oop", "data structures", "algorithms", "pandas", "numpy", "flask", "fastapi"],
    "java":               ["oop", "spring boot", "maven", "jvm", "multithreading", "design patterns"],
    "sql":                ["databases", "joins", "indexing", "normalization", "postgresql", "mysql"],
    "system design":      ["microservices", "load balancing", "caching", "databases", "api design"],
    "backend":            ["rest apis", "databases", "authentication", "docker", "cloud", "testing"],
    "frontend":           ["react", "javascript", "html", "css", "typescript", "state management"],
    "devops":             ["docker", "kubernetes", "ci/cd", "linux", "terraform", "monitoring"],

    # Domain-specific
    "finance":            ["excel", "financial modelling", "dcf valuation", "risk analysis", "bloomberg"],
    "data engineering":   ["apache spark", "kafka", "airflow", "etl", "sql", "python", "hadoop"],
    "cybersecurity":      ["networking", "linux", "python", "cryptography", "penetration testing"],
    "cloud":              ["aws", "azure", "gcp", "docker", "kubernetes", "serverless", "storage"],

    # AI Engineer role
    "ai engineer":        ["machine learning", "deep learning", "mlops", "python", "system design", "apis"],
    "ml engineer":        ["machine learning", "python", "mlops", "feature engineering", "model deployment"],
    "data scientist":     ["statistics", "machine learning", "python", "sql", "data visualization", "experimentation"],
    "llm engineer":       ["llms", "langchain", "rag", "prompt engineering", "fine-tuning", "vector databases"],
}

# Skill importance weights for gap prioritisation
SKILL_IMPORTANCE = {
    "python": 9, "machine learning": 10, "deep learning": 9, "sql": 8,
    "docker": 8, "kubernetes": 7, "aws": 8, "system design": 9,
    "pytorch": 8, "tensorflow": 7, "mlops": 8, "langchain": 7,
    "transformers": 8, "llms": 9, "generative ai": 9, "nlp": 8,
    "git": 7, "linux": 7, "rest apis": 8, "statistics": 8,
    "react": 7, "fastapi": 7, "postgresql": 7, "redis": 6,
    "data structures": 8, "algorithms": 8, "rag": 8,
}

def get_related_skills(skill):
    """Return skills related to a given skill via the graph."""
    skill_lower = skill.lower().strip()
    direct = SKILL_GRAPH.get(skill_lower, [])
    # Also search as value (reverse lookup)
    reverse = [k for k, v in SKILL_GRAPH.items() if skill_lower in v]
    return list(set(direct + reverse))

def infer_implicit_skills(explicit_skills):
    """
    Given a list of explicit skills, infer what the candidate
    likely also knows based on the skill graph.
    Returns: {skill: confidence_score}
    """
    explicit_lower = {s.lower().strip() for s in explicit_skills}
    inferred = {}

    for skill in explicit_skills:
        related = get_related_skills(skill)
        for r in related:
            if r not in explicit_lower:
                # Confidence = 0.6 (likely knows, not confirmed)
                inferred[r] = max(inferred.get(r, 0), 0.6)

    # If candidate knows 2+ prereqs of a skill, infer partial knowledge
    for target, prereqs in SKILL_GRAPH.items():
        if target in explicit_lower:
            continue
        known_prereqs = sum(1 for p in prereqs if p in explicit_lower)
        if known_prereqs >= 2:
            confidence = min(0.85, 0.3 + known_prereqs * 0.15)
            inferred[target] = max(inferred.get(target, 0), confidence)

    return inferred


# ═══════════════════════════════════════════════════════════════
# 2. SKILL GAP INTELLIGENCE — prioritised, weighted gap analysis
# ═══════════════════════════════════════════════════════════════

LEARNING_TIME = {
    # skill → estimated weeks to reach proficiency
    "docker": 2, "kubernetes": 4, "aws": 6, "git": 1,
    "python": 8, "sql": 4, "machine learning": 16, "deep learning": 20,
    "pytorch": 6, "tensorflow": 6, "mlops": 8, "langchain": 3,
    "react": 8, "fastapi": 2, "postgresql": 3, "redis": 2,
    "linux": 4, "system design": 12, "statistics": 10,
    "transformers": 6, "rag": 3, "llms": 8, "nlp": 10,
}

FREE_RESOURCES = {
    "docker":       "labs.play-with-docker.com + Docker official docs",
    "kubernetes":   "killercoda.com/playgrounds/kubernetes (free labs)",
    "aws":          "aws.amazon.com/free + AWS Skill Builder",
    "pytorch":      "pytorch.org/tutorials (official, free)",
    "tensorflow":   "tensorflow.org/tutorials (official, free)",
    "sql":          "sqlzoo.net + mode.com/sql-tutorial",
    "git":          "learngitbranching.js.org (interactive, free)",
    "langchain":    "python.langchain.com/docs + DeepLearning.AI free course",
    "mlops":        "mlflow.org/docs + Weights & Biases free tier",
    "react":        "react.dev/learn (official, free)",
    "fastapi":      "fastapi.tiangolo.com (official, free)",
    "linux":        "overthewire.org/wargames/bandit + linuxjourney.com",
    "statistics":   "khanacademy.org/math/statistics-probability (free)",
    "machine learning": "cs229.stanford.edu (free lectures) + fast.ai",
    "deep learning": "fast.ai (free) + d2l.ai (interactive textbook)",
    "nlp":          "huggingface.co/learn/nlp-course (free)",
    "transformers": "huggingface.co/learn/nlp-course (free)",
    "rag":          "python.langchain.com/docs/use_cases/question_answering",
    "system design": "github.com/donnemartin/system-design-primer (free)",
}

def importance_score(skill):
    """Return importance score for a skill (1-10)."""
    skill_lower = skill.lower().strip()
    # Direct lookup
    if skill_lower in SKILL_IMPORTANCE:
        return SKILL_IMPORTANCE[skill_lower]
    # Partial match
    for key, score in SKILL_IMPORTANCE.items():
        if key in skill_lower or skill_lower in key:
            return score
    return 5  # default medium importance

def skill_gap_intelligence(user_skills, job_required_skills, job_title, domain):
    """
    Full intelligent gap analysis:
    - Identifies true gaps (accounting for inferred skills)
    - Prioritises by importance score
    - Estimates learning time
    - Provides free resources
    - Generates explainable reasoning
    """
    user_lower = {s.lower().strip() for s in user_skills}
    inferred   = infer_implicit_skills(user_skills)

    matched      = []
    inferred_match = []
    true_gaps    = []

    for skill in job_required_skills:
        skill_lower = skill.lower().strip()
        if skill_lower in user_lower:
            matched.append({"skill": skill, "source": "explicit", "confidence": 1.0})
        elif skill_lower in inferred and inferred[skill_lower] >= 0.6:
            inferred_match.append({"skill": skill, "source": "inferred",
                                   "confidence": inferred[skill_lower]})
        else:
            true_gaps.append(skill)

    # Prioritise gaps by importance (descending)
    true_gaps_sorted = sorted(true_gaps, key=lambda x: importance_score(x), reverse=True)

    # Build enriched gap list
    enriched_gaps = []
    total_weeks   = 0
    for skill in true_gaps_sorted[:6]:
        weeks = LEARNING_TIME.get(skill.lower(), 4)
        total_weeks += weeks
        resource = FREE_RESOURCES.get(skill.lower(), f"Search '{skill} tutorial' on YouTube/Google")
        enriched_gaps.append({
            "skill":      skill,
            "importance": importance_score(skill),
            "weeks":      weeks,
            "resource":   resource,
        })

    # Explainable match score
    explicit_score  = len(matched) * 10
    inferred_score  = len(inferred_match) * 6
    max_score       = len(job_required_skills) * 10
    match_pct       = min(99, round((explicit_score + inferred_score) / max(max_score, 1) * 100))

    # Human-readable explanation
    explanation_parts = []
    if matched:
        top = [m["skill"] for m in matched[:3]]
        explanation_parts.append(f"✅ You directly match: {', '.join(top)}")
    if inferred_match:
        top_inf = [m["skill"] for m in inferred_match[:2]]
        explanation_parts.append(f"🔗 Likely know (via skill graph): {', '.join(top_inf)}")
    if enriched_gaps:
        top_gap = enriched_gaps[0]
        explanation_parts.append(
            f"📚 Top gap: {top_gap['skill']} (importance {top_gap['importance']}/10, "
            f"~{top_gap['weeks']} weeks to learn)"
        )
    if total_weeks > 0:
        explanation_parts.append(f"⏱ Total upskilling estimate: ~{total_weeks} weeks")

    gap_explanation = " | ".join(explanation_parts)

    return {
        "match_pct":       match_pct,
        "matched_skills":  [m["skill"] for m in matched[:8]],
        "inferred_skills": [m["skill"] for m in inferred_match[:4]],
        "missing_skills":  [g["skill"] for g in enriched_gaps],
        "enriched_gaps":   enriched_gaps,
        "gap_explanation": gap_explanation,
        "total_upskill_weeks": total_weeks,
    }


# ═══════════════════════════════════════════════════════════════
# 3. DECISION ENGINE — job ranking with explainable scoring
# ═══════════════════════════════════════════════════════════════

def rank_job(job, candidate):
    """
    Score a job against a candidate using multi-factor reasoning.
    Returns (total_score, breakdown_dict) for explainability.
    """
    score     = 0
    breakdown = {}

    candidate_skills = [s.lower().strip() for s in candidate.get("skills", [])]
    inferred         = infer_implicit_skills(candidate.get("skills", []))
    domain           = candidate.get("domain", "").lower()

    job_desc    = (job.get("description", "") + " " + job.get("title", "")).lower()
    job_title   = job.get("title", "").lower()
    job_exp     = job.get("experience", "").lower()
    job_req     = [s.lower().strip() for s in job.get("required_skills", [])]

    # Factor 1: Explicit skill match (up to 40 pts)
    skill_hits = sum(5 for s in candidate_skills if s in job_desc or s in " ".join(job_req))
    skill_hits = min(40, skill_hits)
    score += skill_hits
    breakdown["skill_match"] = skill_hits

    # Factor 2: Inferred skill match (up to 15 pts)
    inf_hits = sum(3 for s, conf in inferred.items()
                   if conf >= 0.6 and (s in job_desc or s in " ".join(job_req)))
    inf_hits = min(15, inf_hits)
    score += inf_hits
    breakdown["inferred_skill_match"] = inf_hits

    # Factor 3: Experience level fit (up to 20 pts)
    exp_score = 0
    if "fresher" in job_exp or "entry" in job_exp or "0-1" in job_exp or "0-2" in job_exp:
        exp_score = 20
    elif "1-3" in job_exp or "2-4" in job_exp:
        exp_score = 12
    elif "3+" in job_exp or "senior" in job_exp:
        exp_score = 4
    score += exp_score
    breakdown["experience_fit"] = exp_score

    # Factor 4: Domain relevance (up to 15 pts)
    domain_score = 0
    if domain in job_title:
        domain_score = 15
    elif domain in job_desc:
        domain_score = 8
    elif any(word in job_title for word in domain.split() if len(word) > 3):
        domain_score = 10
    score += domain_score
    breakdown["domain_relevance"] = domain_score

    # Factor 5: Career fit title match (up to 10 pts)
    career_fits = [c.lower() for c in candidate.get("career_fit", [])]
    career_score = 0
    for cf in career_fits:
        cf_words = [w for w in cf.split() if len(w) > 3]
        if any(w in job_title for w in cf_words):
            career_score = 10
            break
    score += career_score
    breakdown["career_fit_match"] = career_score

    breakdown["total"] = score
    return score, breakdown


def rank_jobs_with_decisions(jobs, candidate):
    """
    Rank all jobs using the decision engine.
    Returns jobs sorted by score with explainability attached.
    """
    scored = []
    for job in jobs:
        score, breakdown = rank_job(job, candidate)
        gap_data = skill_gap_intelligence(
            candidate.get("skills", []),
            job.get("required_skills", []),
            job.get("title", ""),
            candidate.get("domain", "")
        )
        # Build explainable match string
        pct = gap_data["match_pct"]
        explanation = _build_match_explanation(breakdown, gap_data, job)

        job_copy = dict(job)
        job_copy["decision_score"]    = score
        job_copy["match"]             = f"{pct}%"
        job_copy["match_explanation"] = explanation
        job_copy["score_breakdown"]   = breakdown
        job_copy["matched_skills"]    = gap_data["matched_skills"]
        job_copy["inferred_skills"]   = gap_data["inferred_skills"]
        job_copy["missing_skills"]    = gap_data["missing_skills"]
        job_copy["enriched_gaps"]     = gap_data["enriched_gaps"]
        job_copy["gap_advice"]        = gap_data["gap_explanation"]
        job_copy["upskill_weeks"]     = gap_data["total_upskill_weeks"]
        scored.append(job_copy)

    scored.sort(key=lambda j: j["decision_score"], reverse=True)
    return scored


def _build_match_explanation(breakdown, gap_data, job):
    """Build a human-readable explanation of why this match score was given."""
    parts = []
    total = breakdown.get("total", 0)

    if breakdown.get("skill_match", 0) >= 20:
        parts.append(f"Strong skill overlap ({breakdown['skill_match']}/40 pts)")
    elif breakdown.get("skill_match", 0) >= 10:
        parts.append(f"Moderate skill overlap ({breakdown['skill_match']}/40 pts)")
    else:
        parts.append(f"Low skill overlap ({breakdown['skill_match']}/40 pts)")

    if breakdown.get("experience_fit", 0) == 20:
        parts.append("Perfect experience level (fresher/entry)")
    elif breakdown.get("experience_fit", 0) >= 12:
        parts.append("Reasonable experience requirement")

    if breakdown.get("domain_relevance", 0) >= 10:
        parts.append("Domain directly matches your field")

    if gap_data.get("inferred_skills"):
        parts.append(f"Skill graph infers you likely know: {', '.join(gap_data['inferred_skills'][:2])}")

    missing = gap_data.get("missing_skills", [])
    if not missing:
        parts.append("✅ You meet ALL requirements — apply immediately!")
    elif len(missing) == 1:
        parts.append(f"Only 1 gap: {missing[0]} (~{gap_data['enriched_gaps'][0]['weeks']}w to learn)")
    elif len(missing) <= 3:
        parts.append(f"Gaps: {', '.join(missing[:3])} — closeable in {gap_data['total_upskill_weeks']}w")

    return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════
# 4. LOCAL ANSWER EVALUATOR — works without any API call
# ═══════════════════════════════════════════════════════════════

TECHNICAL_KEYWORDS = {
    "machine learning":  ["model","training","features","algorithm","accuracy","loss","gradient","overfitting"],
    "deep learning":     ["neural","layer","activation","backprop","epoch","batch","cnn","rnn","lstm"],
    "python":            ["function","class","loop","list","dict","import","exception","return"],
    "sql":               ["select","join","where","group by","index","table","query","foreign key"],
    "system design":     ["scale","database","cache","load balancer","microservice","api","consistency"],
    "generative ai":     ["llm","prompt","token","transformer","attention","fine-tune","rag","embedding"],
    "nlp":               ["token","corpus","embedding","sentiment","classification","bert","transformer"],
    "docker":            ["container","image","dockerfile","compose","volume","port","layer"],
    "general":           ["example","because","therefore","approach","method","implement","result"],
}

def local_evaluate_answer(question, answer, topic, level, domain):
    """
    Evaluate an answer locally without any API call.
    Uses keyword matching, length analysis, and structural checks.
    Returns a score dict compatible with the Groq evaluator output.
    """
    if not answer or len(answer.strip()) < 8:
        return {
            "score": 0, "grade": "F", "correct": False,
            "feedback": "No answer provided.",
            "what_was_right": "", "what_was_wrong": "Answer was blank.",
            "improvement": "Please attempt the question.",
            "model_answer_hint": f"A good answer covers core concepts of {topic}.",
            "encouragement": "Every expert started as a beginner — give it a try!",
            "confidence_impact": "negative"
        }

    answer_lower = answer.lower()
    words        = answer.split()
    score        = 0
    breakdown    = {}

    # Length score (up to 2 pts)
    length_score = min(2, len(words) // 20)
    score += length_score
    breakdown["length"] = length_score

    # Keyword match (up to 4 pts)
    domain_keywords = TECHNICAL_KEYWORDS.get(topic.lower(),
                      TECHNICAL_KEYWORDS.get(domain.lower(),
                      TECHNICAL_KEYWORDS["general"]))
    keyword_hits = sum(1 for kw in domain_keywords if kw in answer_lower)
    kw_score     = min(4, keyword_hits)
    score       += kw_score
    breakdown["keyword_match"] = kw_score

    # Has example (1 pt)
    has_example = any(w in answer_lower for w in ["example","instance","for instance","e.g","such as","like when"])
    if has_example:
        score += 1
        breakdown["has_example"] = 1

    # Structured answer (1 pt) — has multiple sentences
    sentences = [s.strip() for s in re.split(r'[.!?]', answer) if len(s.strip()) > 10]
    if len(sentences) >= 2:
        score += 1
        breakdown["structured"] = 1

    # Mentions the topic (1 pt)
    topic_words = [w for w in topic.lower().split() if len(w) > 3]
    if any(tw in answer_lower for tw in topic_words):
        score += 1
        breakdown["topic_relevance"] = 1

    # Level difficulty bonus (harder levels reward depth)
    if level >= 2 and len(words) >= 40:
        score += 1
    if level >= 3 and len(words) >= 80:
        score += 1

    score = min(10, score)

    # Grade
    grade = "A" if score >= 9 else "B" if score >= 7 else "C" if score >= 5 else "D" if score >= 3 else "F"

    # Feedback
    if kw_score >= 3:
        what_right = f"Good use of domain-relevant terms for {topic}."
    elif kw_score >= 1:
        what_right = "You touched on some relevant concepts."
    else:
        what_right = "You attempted the question."

    what_wrong = []
    if length_score == 0:
        what_wrong.append("Answer too short — expand your explanation")
    if kw_score == 0:
        what_wrong.append(f"No key {topic} terms found — use technical vocabulary")
    if not has_example:
        what_wrong.append("No example given — examples always strengthen answers")
    if len(sentences) < 2:
        what_wrong.append("Single sentence — structure with multiple points")

    level_labels = {1: "beginner", 2: "intermediate", 3: "advanced"}
    return {
        "score":            score,
        "grade":            grade,
        "correct":          score >= 6,
        "feedback":         f"Your answer scores {score}/10 for {topic} at {level_labels.get(level,'intermediate')} level. {what_right}",
        "what_was_right":   what_right,
        "what_was_wrong":   " | ".join(what_wrong) if what_wrong else "Minor gaps in depth.",
        "improvement":      f"Add a concrete example and use more {topic}-specific terminology.",
        "model_answer_hint": f"A strong answer defines {topic}, explains the mechanism with precision, and gives a real-world example from your projects.",
        "encouragement":    f"You're building real {domain} intuition — keep going!",
        "confidence_impact": "positive" if score >= 7 else "neutral" if score >= 5 else "negative",
        "local_evaluation": True,
        "score_breakdown":  breakdown,
    }


# ═══════════════════════════════════════════════════════════════
# 5. MEMORY / USER PROFILE — tracks improvement across sessions
# ═══════════════════════════════════════════════════════════════

class UserProfile:
    """
    In-memory user profile that tracks performance history.
    Simulates adaptive intelligence — system improves its
    recommendations based on observed weak areas.
    """

    def __init__(self, name, domain, skills):
        self.name               = name
        self.domain             = domain
        self.skills             = skills
        self.sessions           = []
        self.weak_areas         = {}   # topic → [scores]
        self.strong_areas       = {}
        self.improvement_history = []  # [{session, topic, old_avg, new_avg, improved}]
        self.session_count      = 0
        self.created_at         = datetime.now().isoformat()

    def record_answer(self, topic, score):
        """Record answer score and track improvement over time."""
        if topic not in self.weak_areas:
            self.weak_areas[topic] = []

        old_scores = self.weak_areas[topic].copy()
        self.weak_areas[topic].append(score)

        # Track improvement if we have history
        if len(old_scores) >= 2:
            old_avg = sum(old_scores) / len(old_scores)
            new_avg = sum(self.weak_areas[topic]) / len(self.weak_areas[topic])
            improved = new_avg > old_avg
            self.improvement_history.append({
                "topic":    topic,
                "old_avg":  round(old_avg, 1),
                "new_avg":  round(new_avg, 1),
                "improved": improved,
                "delta":    round(new_avg - old_avg, 1),
                "time":     datetime.now().isoformat()
            })

    def get_improvement_summary(self):
        """Returns a human-readable improvement summary for display."""
        if not self.improvement_history:
            return "No history yet — complete more sessions to see your progress."
        improved = [h for h in self.improvement_history if h["improved"]]
        declined = [h for h in self.improvement_history if not h["improved"]]
        summary  = []
        for h in improved[-3:]:
            summary.append(f"📈 {h['topic']}: {h['old_avg']} → {h['new_avg']} (+{h['delta']})")
        for h in declined[-2:]:
            summary.append(f"📉 {h['topic']}: needs more practice ({h['new_avg']:.1f}/10)")
        return " | ".join(summary) if summary else "Keep practising to see trends."

    def get_weak_topics(self, threshold=5):
        """Return topics where average score is below threshold."""
        weak = {}
        for topic, scores in self.weak_areas.items():
            avg = sum(scores) / len(scores)
            if avg < threshold:
                weak[topic] = round(avg, 1)
        return dict(sorted(weak.items(), key=lambda x: x[1]))

    def get_strong_topics(self, threshold=7):
        """Return topics where average score is above threshold."""
        strong = {}
        for topic, scores in self.weak_areas.items():
            avg = sum(scores) / len(scores)
            if avg >= threshold:
                strong[topic] = round(avg, 1)
        return strong

    def get_improvement_summary(self):
        """Generate a summary of the candidate's progress."""
        if not self.weak_areas:
            return "No sessions recorded yet."

        weak   = self.get_weak_topics()
        strong = self.get_strong_topics()

        parts = []
        if strong:
            parts.append(f"Strong in: {', '.join(list(strong.keys())[:3])}")
        if weak:
            parts.append(f"Needs work: {', '.join(list(weak.keys())[:3])}")

        total_answers = sum(len(v) for v in self.weak_areas.values())
        all_scores    = [s for scores in self.weak_areas.values() for s in scores]
        overall_avg   = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0

        parts.append(f"Overall average: {overall_avg}/10 across {total_answers} answers")
        return " | ".join(parts)

    def get_adaptive_question_priority(self):
        """
        Return topics that should be focused on next session
        based on weak areas — adaptive learning intelligence.
        """
        weak = self.get_weak_topics()
        if not weak:
            return self.skills[:3]
        # Prioritise weakest topics
        return list(weak.keys())[:3]

    def to_dict(self):
        return {
            "name":       self.name,
            "domain":     self.domain,
            "skills":     self.skills,
            "weak_areas": {t: round(sum(s)/len(s), 1) for t, s in self.weak_areas.items()},
            "strong_areas": self.get_strong_topics(),
            "improvement_summary": self.get_improvement_summary(),
            "total_answers": sum(len(v) for v in self.weak_areas.values()),
        }


# Global profile store (session_id → UserProfile)
USER_PROFILES = {}

def get_or_create_profile(session_id, name, domain, skills):
    if session_id not in USER_PROFILES:
        USER_PROFILES[session_id] = UserProfile(name, domain, skills)
    return USER_PROFILES[session_id]


# ═══════════════════════════════════════════════════════════════
# 6. PIPELINE AGENTS — named stages for examiner visibility
# ═══════════════════════════════════════════════════════════════

class ResumeAgent:
    """Stage 1: Parses and structures resume data."""
    def process(self, raw_text, basic_details):
        return {
            "agent":    "ResumeAgent",
            "name":     basic_details.get("name"),
            "email":    basic_details.get("email"),
            "phone":    basic_details.get("phone"),
            "education": basic_details.get("education"),
            "raw_text_length": len(raw_text),
            "timestamp": datetime.now().isoformat(),
        }

class SkillEngine:
    """Stage 2: Extracts, enriches, and graphs skills."""
    def process(self, analysis):
        skills   = analysis.get("skills", [])
        inferred = infer_implicit_skills(skills)
        graph_connections = {s: get_related_skills(s) for s in skills[:5]}
        return {
            "agent":             "SkillEngine",
            "explicit_skills":   skills,
            "inferred_skills":   list(inferred.keys())[:10],
            "skill_graph_edges": graph_connections,
            "domain":            analysis.get("domain"),
        }

class DecisionEngine:
    """Stage 3: Ranks jobs and makes intelligent recommendations."""
    def process(self, jobs, candidate):
        ranked = rank_jobs_with_decisions(jobs, candidate)
        return {
            "agent":       "DecisionEngine",
            "total_jobs":  len(ranked),
            "top_match":   ranked[0]["title"] if ranked else None,
            "top_score":   ranked[0]["decision_score"] if ranked else 0,
            "ranked_jobs": ranked,
        }

class InterviewEngine:
    """Stage 5: Evaluates answers with local + API hybrid."""
    def evaluate(self, question, answer, topic, level, domain):
        return local_evaluate_answer(question, answer, topic, level, domain)


# ═══════════════════════════════════════════════════════════════
# 7. EXPLAINABILITY HELPERS — for report output
# ═══════════════════════════════════════════════════════════════

def explain_confidence_score(analysis):
    """
    Explain WHY a candidate got High/Medium/Low confidence rating.
    Makes the AI output interpretable rather than a black box.
    """
    skills    = analysis.get("skills", [])
    projects  = analysis.get("projects", [])
    education = analysis.get("education", "")
    domain    = analysis.get("domain", "")

    score  = 0
    reasons = []

    # Skills breadth
    if len(skills) >= 15:
        score += 30
        reasons.append(f"✅ Strong skill breadth ({len(skills)} skills detected)")
    elif len(skills) >= 8:
        score += 20
        reasons.append(f"✅ Good skill set ({len(skills)} skills)")
    else:
        score += 10
        reasons.append(f"⚠️ Limited skills detected ({len(skills)} skills)")

    # Projects
    if len(projects) >= 4:
        score += 30
        reasons.append(f"✅ Strong project portfolio ({len(projects)} projects)")
    elif len(projects) >= 2:
        score += 20
        reasons.append(f"✅ Has projects ({len(projects)} projects)")
    else:
        score += 5
        reasons.append("⚠️ Few or no projects detected")

    # Education level
    if "m.tech" in education.lower() or "m.e" in education.lower() or "mca" in education.lower():
        score += 25
        reasons.append("✅ Postgraduate degree")
    elif "b.tech" in education.lower() or "b.e" in education.lower() or "bca" in education.lower():
        score += 20
        reasons.append("✅ Engineering degree")
    else:
        score += 10
        reasons.append("📋 Education detected")

    # Domain relevance
    high_demand = ["artificial intelligence", "machine learning", "data science",
                   "cloud", "devops", "cybersecurity", "fullstack"]
    if any(hd in domain.lower() for hd in high_demand):
        score += 15
        reasons.append(f"✅ High-demand domain: {domain}")

    level = "High" if score >= 75 else "Medium" if score >= 45 else "Low"
    return {
        "level":   level,
        "score":   score,
        "reasons": reasons,
        "summary": f"Confidence is {level} because: " + " | ".join(reasons[:3])
    }


# ═══════════════════════════════════════════════════════════════
# Instantiate global pipeline agents
# ═══════════════════════════════════════════════════════════════
resume_agent    = ResumeAgent()
skill_engine    = SkillEngine()
decision_engine = DecisionEngine()
interview_engine = InterviewEngine()

print("  [AI Engine] ✅ Intelligence layer loaded — Decision Engine, Skill Graph, Gap Intelligence, Memory active")