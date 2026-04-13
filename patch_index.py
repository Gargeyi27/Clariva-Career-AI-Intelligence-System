#!/usr/bin/env python3
"""
Run this script from your career-agi-backend folder:
  python patch_index.py
It fixes the showFeedback function in interview_app/index.html
so ALL feedback sections always show (not just when API returns full data).
"""
import os, re, sys

index_path = os.path.join("interview_app", "index.html")
if not os.path.exists(index_path):
    print(f"ERROR: {index_path} not found. Run from career-agi-backend folder.")
    sys.exit(1)

content = open(index_path, encoding="utf-8").read()

# Find and replace the showFeedback function
pattern = r'function showFeedback\(data, q\) \{.*?
\}'
replacement = 'function showFeedback(data, q) {\n  const card = document.getElementById(\'feedbackCard\');\n  const score = Math.max(0, Math.min(10, data.score ?? 5));\n  const grade = data.grade || (score >= 9 ? \'A\' : score >= 7 ? \'B\' : score >= 5 ? \'C\' : score >= 3 ? \'D\' : \'F\');\n  const scoreClass = score >= 7 ? \'high\' : score >= 5 ? \'mid\' : \'low\';\n  const gradeColor = score >= 7 ? \'var(--accent2)\' : score >= 5 ? \'#f5a623\' : \'var(--accent3)\';\n  const impact = data.confidence_impact || \'neutral\';\n  const impactIcon = impact === \'positive\' ? \'📈\' : impact === \'negative\' ? \'📉\' : \'➡️\';\n\n  // Always show all sections — even for blank/short answers\n  const rightText = data.what_was_right || \'Nothing yet — but attempting is the first step.\';\n  const wrongText = data.what_was_wrong || \'No specific gaps identified.\';\n  const hintText  = data.model_answer_hint || `A strong answer defines ${q.topic || \'this concept\'}, explains the mechanism, and gives a real example.`;\n  const tipText   = data.improvement || \'Add a concrete example and use domain-specific terminology.\';\n  const encourage = data.encouragement || \'Keep going — every answer makes you sharper!\';\n\n  const rightHtml = `\n    <div style="background:rgba(0,212,170,0.08);border-left:3px solid var(--accent2);padding:10px 14px;border-radius:0 8px 8px 0;margin-bottom:10px;">\n      <div style="font-size:11px;color:var(--accent2);font-weight:700;margin-bottom:4px;letter-spacing:1px;">✅ WHAT YOU GOT RIGHT</div>\n      <div style="font-size:13px;color:var(--text);">${rightText}</div>\n    </div>`;\n\n  const wrongHtml = `\n    <div style="background:rgba(255,107,107,0.08);border-left:3px solid var(--accent3);padding:10px 14px;border-radius:0 8px 8px 0;margin-bottom:10px;">\n      <div style="font-size:11px;color:var(--accent3);font-weight:700;margin-bottom:4px;letter-spacing:1px;">⚠️ GAPS IN YOUR ANSWER</div>\n      <div style="font-size:13px;color:var(--text);">${wrongText}</div>\n    </div>`;\n\n  const hintHtml = `\n    <div style="background:rgba(108,99,255,0.08);border-left:3px solid var(--accent);padding:10px 14px;border-radius:0 8px 8px 0;margin-bottom:10px;">\n      <div style="font-size:11px;color:var(--accent);font-weight:700;margin-bottom:4px;letter-spacing:1px;">🎯 WHAT A GREAT ANSWER INCLUDES</div>\n      <div style="font-size:13px;color:var(--text);">${hintText}</div>\n    </div>`;\n\n  card.innerHTML = `\n    <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;flex-wrap:wrap;">\n      <div class="feedback-score ${scoreClass}" style="font-size:22px;min-width:70px;">${score}/10</div>\n      <div style="background:${gradeColor}22;border:1px solid ${gradeColor};border-radius:8px;padding:4px 14px;font-size:20px;font-weight:800;color:${gradeColor};">${grade}</div>\n      <div style="flex:1;min-width:120px;">\n        <div style="font-size:14px;font-weight:600;color:var(--text);">AGI Deep Evaluation</div>\n        <div style="font-size:12px;color:var(--muted);margin-top:2px;">\n          ${data.correct ? \'✅ Answer accepted\' : \'📝 Needs improvement\'}\n          &nbsp;${impactIcon} Confidence ${impact}\n        </div>\n      </div>\n    </div>\n    <div class="feedback-text" style="margin-bottom:14px;font-size:14px;line-height:1.6;">${data.feedback || \'\'}</div>\n    ${rightHtml}${wrongHtml}${hintHtml}\n    <div class="feedback-tip" style="margin-bottom:10px;">💡 <strong>Tip:</strong> ${tipText}</div>\n    <div class="encouragement" style="margin-bottom:16px;">${encourage}</div>\n    <button class="btn btn-primary" onclick="nextQuestion()" style="margin-top:16px;">\n      ${STATE.currentIndex + 1 >= STATE.questions.length ? \'🏁 View Final Results\' : \'Next Question →\'}\n    </button>\n  `;\n  card.classList.add(\'show\');\n}'

match = re.search(pattern, content, re.DOTALL)
if not match:
    print("ERROR: showFeedback function not found in index.html")
    print("Looking for 'function showFeedback(data, q)'...")
    if "function showFeedback" in content:
        print("  Found the function but pattern didn't match — file may differ")
    sys.exit(1)

# Backup original
backup_path = index_path + ".bak"
open(backup_path, "w", encoding="utf-8").write(content)
print(f"Backup saved: {backup_path}")

# Apply patch
new_content = content[:match.start()] + replacement + content[match.end():]
open(index_path, "w", encoding="utf-8").write(new_content)
print(f"✅ showFeedback patched in {index_path}")
print("Restart Flask and test the interview — all feedback sections will now always show.")