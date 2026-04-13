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

try:
    from ai_engine import (
        skill_gap_intelligence, rank_jobs_with_decisions,
        local_evaluate_answer, get_or_create_profile,
        explain_confidence_score, infer_implicit_skills,
        skill_engine, decision_engine, interview_engine,
        resume_agent, SKILL_GRAPH, USER_PROFILES
    )
    AI_ENGINE_LOADED = True
    print("  [Engine] ✅ AI Intelligence Layer active")
except ImportError as e:
    AI_ENGINE_LOADED = False
    print(f"  [Engine] ⚠️  ai_engine.py not found — using basic mode: {e}")

LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CareerAGI — AI-Powered Career Intelligence Platform</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Clash+Display:wght@400;500;600;700&family=Satoshi:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{
  --black:#050508;--dark:#0d0d14;--card:#12121c;--card2:#1a1a28;
  --purple:#7c3aed;--violet:#a855f7;--pink:#ec4899;--cyan:#06b6d4;
  --green:#10b981;--orange:#f59e0b;--red:#ef4444;
  --text:#f0f0f8;--muted:#8888aa;--border:rgba(124,58,237,0.2);
}
html{scroll-behavior:smooth;}
body{font-family:'Satoshi',sans-serif;background:var(--black);color:var(--text);overflow-x:hidden;}

/* ── NOISE OVERLAY ── */
body::before{content:'';position:fixed;inset:0;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");opacity:0.4;pointer-events:none;z-index:0;}

/* ── GRADIENT ORBS ── */
.orb{position:fixed;border-radius:50%;filter:blur(100px);pointer-events:none;z-index:0;}
.orb1{width:600px;height:600px;background:radial-gradient(circle,rgba(124,58,237,0.15),transparent);top:-200px;left:-200px;}
.orb2{width:500px;height:500px;background:radial-gradient(circle,rgba(236,72,153,0.12),transparent);bottom:-100px;right:-100px;}
.orb3{width:400px;height:400px;background:radial-gradient(circle,rgba(6,182,212,0.1),transparent);top:50%;left:50%;transform:translate(-50%,-50%);}

/* ── NAV ── */
nav{position:fixed;top:0;left:0;right:0;z-index:100;padding:16px 40px;display:flex;align-items:center;justify-content:space-between;background:rgba(5,5,8,0.8);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);}
.nav-logo{font-family:'Clash Display',sans-serif;font-size:22px;font-weight:700;background:linear-gradient(135deg,var(--violet),var(--pink));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.nav-links{display:flex;gap:32px;list-style:none;}
.nav-links a{color:var(--muted);text-decoration:none;font-size:14px;transition:color 0.2s;}
.nav-links a:hover{color:var(--text);}
.nav-cta{background:linear-gradient(135deg,var(--purple),var(--pink));color:#fff;border:none;padding:10px 24px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;transition:opacity 0.2s;}
.nav-cta:hover{opacity:0.85;}

/* ── HERO ── */
.hero{position:relative;z-index:1;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:120px 20px 80px;}
.hero-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(124,58,237,0.15);border:1px solid rgba(124,58,237,0.3);border-radius:100px;padding:6px 16px;font-size:12px;color:var(--violet);margin-bottom:32px;animation:fadeUp 0.8s ease both;}
.hero-badge span{background:var(--violet);color:#fff;border-radius:100px;padding:2px 8px;font-size:10px;font-weight:700;}
h1.hero-title{font-family:'Clash Display',sans-serif;font-size:clamp(40px,7vw,88px);font-weight:700;line-height:1.0;margin-bottom:24px;animation:fadeUp 0.8s 0.1s ease both;}
.grad1{background:linear-gradient(135deg,#fff 0%,var(--violet) 40%,var(--pink) 80%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.grad2{background:linear-gradient(135deg,var(--cyan),var(--green));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.hero-sub{font-size:clamp(16px,2vw,20px);color:var(--muted);max-width:640px;line-height:1.7;margin-bottom:48px;animation:fadeUp 0.8s 0.2s ease both;}
.hero-btns{display:flex;gap:16px;flex-wrap:wrap;justify-content:center;animation:fadeUp 0.8s 0.3s ease both;}
.btn-primary{background:linear-gradient(135deg,var(--purple),var(--pink));color:#fff;border:none;padding:16px 36px;border-radius:12px;font-size:16px;font-weight:600;cursor:pointer;font-family:inherit;transition:transform 0.2s,box-shadow 0.2s;box-shadow:0 8px 32px rgba(124,58,237,0.35);}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 16px 48px rgba(124,58,237,0.45);}
.btn-secondary{background:transparent;color:var(--text);border:1px solid var(--border);padding:16px 36px;border-radius:12px;font-size:16px;font-weight:600;cursor:pointer;font-family:inherit;transition:all 0.2s;}
.btn-secondary:hover{border-color:var(--violet);background:rgba(124,58,237,0.08);}
.hero-stats{display:flex;gap:48px;margin-top:72px;padding-top:48px;border-top:1px solid var(--border);animation:fadeUp 0.8s 0.4s ease both;flex-wrap:wrap;justify-content:center;}
.stat{text-align:center;}
.stat-num{font-family:'Clash Display',sans-serif;font-size:36px;font-weight:700;background:linear-gradient(135deg,var(--violet),var(--pink));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.stat-label{font-size:13px;color:var(--muted);margin-top:4px;}

/* ── FEATURES SECTION ── */
.section{position:relative;z-index:1;padding:100px 20px;max-width:1200px;margin:0 auto;}
.section-tag{display:inline-block;background:rgba(6,182,212,0.1);border:1px solid rgba(6,182,212,0.3);color:var(--cyan);border-radius:100px;padding:4px 16px;font-size:12px;font-weight:600;letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;}
.section-title{font-family:'Clash Display',sans-serif;font-size:clamp(32px,5vw,52px);font-weight:700;margin-bottom:16px;line-height:1.1;}
.section-sub{color:var(--muted);font-size:16px;max-width:560px;line-height:1.7;margin-bottom:64px;}

/* ── FEATURE GRID ── */
.features-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:24px;}
.feat-card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:32px;transition:transform 0.3s,border-color 0.3s,box-shadow 0.3s;position:relative;overflow:hidden;}
.feat-card::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,rgba(124,58,237,0.05),transparent);opacity:0;transition:opacity 0.3s;}
.feat-card:hover{transform:translateY(-6px);border-color:rgba(124,58,237,0.4);box-shadow:0 24px 64px rgba(124,58,237,0.15);}
.feat-card:hover::before{opacity:1;}
.feat-icon{width:52px;height:52px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:24px;margin-bottom:20px;}
.feat-icon.purple{background:rgba(124,58,237,0.15);}
.feat-icon.pink{background:rgba(236,72,153,0.15);}
.feat-icon.cyan{background:rgba(6,182,212,0.15);}
.feat-icon.green{background:rgba(16,185,129,0.15);}
.feat-icon.orange{background:rgba(245,158,11,0.15);}
.feat-icon.red{background:rgba(239,68,68,0.15);}
.feat-card h3{font-family:'Clash Display',sans-serif;font-size:20px;font-weight:600;margin-bottom:10px;}
.feat-card p{color:var(--muted);font-size:14px;line-height:1.7;}
.feat-tag{display:inline-block;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.2);color:var(--green);border-radius:6px;padding:2px 10px;font-size:11px;font-weight:600;margin-top:16px;}

/* ── HOW IT WORKS ── */
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:0;margin-top:64px;position:relative;}
.steps::before{content:'';position:absolute;top:32px;left:10%;right:10%;height:1px;background:linear-gradient(90deg,transparent,var(--violet),var(--pink),transparent);z-index:0;}
.step{text-align:center;padding:32px 24px;position:relative;z-index:1;}
.step-num{width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,var(--purple),var(--pink));display:flex;align-items:center;justify-content:center;font-family:'Clash Display',sans-serif;font-size:22px;font-weight:700;color:#fff;margin:0 auto 20px;box-shadow:0 8px 24px rgba(124,58,237,0.4);}
.step h3{font-family:'Clash Display',sans-serif;font-size:16px;font-weight:600;margin-bottom:8px;}
.step p{color:var(--muted);font-size:13px;line-height:1.6;}

/* ── COMPANIES STRIP ── */
.companies-section{position:relative;z-index:1;padding:60px 20px;text-align:center;border-top:1px solid var(--border);border-bottom:1px solid var(--border);background:rgba(13,13,20,0.5);}
.companies-label{font-size:12px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:32px;}
.companies-strip{display:flex;gap:40px;justify-content:center;flex-wrap:wrap;}
.company-chip{background:var(--card2);border:1px solid var(--border);border-radius:10px;padding:10px 20px;font-size:13px;font-weight:600;color:var(--muted);transition:all 0.2s;}
.company-chip:hover{border-color:var(--violet);color:var(--text);}

/* ── TESTIMONIALS ── */
.testimonials{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px;margin-top:64px;}
.tcard{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:28px;}
.tcard-text{font-size:15px;line-height:1.7;color:#ccc;margin-bottom:20px;font-style:italic;}
.tcard-text::before{content:'"';font-size:32px;color:var(--violet);line-height:0;vertical-align:-12px;margin-right:4px;}
.tcard-author{display:flex;align-items:center;gap:12px;}
.tcard-avatar{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,var(--purple),var(--pink));display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;color:#fff;}
.tcard-name{font-weight:600;font-size:14px;}
.tcard-role{font-size:12px;color:var(--muted);}
.tcard-stars{color:var(--orange);font-size:12px;margin-top:2px;}

/* ── CTA SECTION ── */
.cta-section{position:relative;z-index:1;text-align:center;padding:100px 20px;max-width:800px;margin:0 auto;}
.cta-glow{position:absolute;inset:0;background:radial-gradient(ellipse at center,rgba(124,58,237,0.15),transparent 70%);pointer-events:none;}
.cta-section h2{font-family:'Clash Display',sans-serif;font-size:clamp(36px,5vw,60px);font-weight:700;margin-bottom:20px;line-height:1.1;}
.cta-section p{color:var(--muted);font-size:18px;margin-bottom:40px;line-height:1.6;}
.cta-btns{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;}

/* ── FOOTER ── */
footer{position:relative;z-index:1;padding:40px;border-top:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:20px;}
.footer-logo{font-family:'Clash Display',sans-serif;font-size:18px;font-weight:700;background:linear-gradient(135deg,var(--violet),var(--pink));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.footer-links{display:flex;gap:24px;}
.footer-links a{color:var(--muted);text-decoration:none;font-size:13px;transition:color 0.2s;}
.footer-links a:hover{color:var(--text);}
.footer-copy{color:var(--muted);font-size:13px;}

/* ── UPLOAD MODAL ── */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:200;display:none;align-items:center;justify-content:center;padding:20px;backdrop-filter:blur(8px);}
.modal-overlay.show{display:flex;}
.modal{background:var(--card);border:1px solid var(--border);border-radius:24px;padding:48px 40px;max-width:520px;width:100%;position:relative;box-shadow:0 32px 96px rgba(0,0,0,0.5);}
.modal-close{position:absolute;top:20px;right:20px;background:transparent;border:none;color:var(--muted);font-size:20px;cursor:pointer;width:32px;height:32px;display:flex;align-items:center;justify-content:center;border-radius:8px;transition:all 0.2s;}
.modal-close:hover{background:var(--card2);color:var(--text);}
.modal h2{font-family:'Clash Display',sans-serif;font-size:28px;font-weight:700;margin-bottom:8px;}
.modal p{color:var(--muted);font-size:14px;margin-bottom:32px;}
.drop-zone{border:2px dashed rgba(124,58,237,0.4);border-radius:16px;padding:48px 24px;text-align:center;cursor:pointer;transition:all 0.3s;background:rgba(124,58,237,0.03);position:relative;}
.drop-zone:hover,.drop-zone.dragover{border-color:var(--violet);background:rgba(124,58,237,0.08);}
.drop-zone input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%;}
.drop-icon{font-size:40px;margin-bottom:12px;}
.drop-text{color:var(--muted);font-size:14px;}
.drop-text strong{color:var(--violet);}
.file-name{margin-top:10px;color:var(--violet);font-size:13px;font-weight:600;}
.upload-btn{width:100%;margin-top:20px;background:linear-gradient(135deg,var(--purple),var(--pink));color:#fff;border:none;padding:16px;border-radius:12px;font-size:16px;font-weight:600;cursor:pointer;font-family:inherit;transition:opacity 0.2s;}
.upload-btn:hover{opacity:0.9;}
.upload-btn:disabled{opacity:0.4;cursor:not-allowed;}
.upload-progress{display:none;margin-top:16px;}
.progress-bar{height:6px;background:var(--card2);border-radius:3px;overflow:hidden;}
.progress-fill{height:100%;background:linear-gradient(90deg,var(--purple),var(--pink));width:0%;transition:width 0.4s;border-radius:3px;}
.progress-status{color:var(--muted);font-size:13px;margin-top:8px;text-align:center;}
.result-links{display:none;margin-top:20px;display:flex;flex-direction:column;gap:10px;}
.result-links.show{display:flex;}
.result-link-btn{display:block;padding:14px 20px;border-radius:10px;text-decoration:none;font-weight:700;font-size:14px;text-align:center;transition:opacity 0.2s;}
.result-link-btn:hover{opacity:0.85;}
.rl-report{background:linear-gradient(135deg,var(--purple),#9333ea);color:#fff;}
.rl-interview{background:linear-gradient(135deg,var(--pink),#f43f5e);color:#fff;}

/* ── ANIMATIONS ── */
@keyframes fadeUp{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}
@keyframes pulse-ring{0%{box-shadow:0 0 0 0 rgba(124,58,237,0.4)}70%{box-shadow:0 0 0 16px rgba(124,58,237,0)}100%{box-shadow:0 0 0 0 rgba(124,58,237,0)}}

.float{animation:float 4s ease-in-out infinite;}
.pulse{animation:pulse-ring 2s infinite;}

/* ── SCROLL REVEAL ── */
.reveal{opacity:0;transform:translateY(40px);transition:opacity 0.7s ease,transform 0.7s ease;}
.reveal.visible{opacity:1;transform:translateY(0);}

/* ── MOBILE ── */
@media(max-width:768px){
  nav{padding:16px 20px;}
  .nav-links{display:none;}
  .hero-stats{gap:24px;}
  .steps::before{display:none;}
  .section{padding:60px 20px;}
  footer{justify-content:center;text-align:center;}
  .modal{padding:32px 24px;}
}
</style>
</head>
<body>

<div class="orb orb1"></div>
<div class="orb orb2"></div>
<div class="orb orb3"></div>

<!-- NAV -->
<nav>
  <div class="nav-logo">⚡ CareerAGI</div>
  <ul class="nav-links">
    <li><a href="#features">Features</a></li>
    <li><a href="#how">How it works</a></li>
    <li><a href="#companies">Companies</a></li>
    <li><a href="#testimonials">Reviews</a></li>
  </ul>
  <button class="nav-cta" onclick="openModal()">Get Started Free →</button>
</nav>

<!-- HERO -->
<section class="hero">
  <div class="hero-badge"><span>NEW</span> AI-Powered Career Intelligence for Students</div>
  <h1 class="hero-title">
    <span class="grad1">Land Your Dream Job</span><br>
    With <span class="grad2">AGI Precision</span>
  </h1>
  <p class="hero-sub">Upload your resume. Get an instant ATS score, personalised job matches, company-specific mock interviews, and AI feedback — all in under 30 seconds.</p>
  <div class="hero-btns">
    <button class="btn-primary pulse" onclick="openModal()">🚀 Analyse My Resume — Free</button>
    <button class="btn-secondary" onclick="document.getElementById('how').scrollIntoView({behavior:'smooth'})">See how it works ↓</button>
  </div>
  <div class="hero-stats">
    <div class="stat"><div class="stat-num">145+</div><div class="stat-label">Interview Questions</div></div>
    <div class="stat"><div class="stat-num">30s</div><div class="stat-label">Analysis Time</div></div>
    <div class="stat"><div class="stat-num">10+</div><div class="stat-label">Company Profiles</div></div>
    <div class="stat"><div class="stat-num">100%</div><div class="stat-label">Free Forever</div></div>
  </div>
</section>

<!-- FEATURES -->
<section class="section" id="features">
  <div class="reveal">
    <div class="section-tag">Features</div>
    <h2 class="section-title">Everything you need to <span class="grad1">get hired faster</span></h2>
    <p class="section-sub">From resume optimisation to mock interviews — CareerAGI has every tool a student needs to crack placements.</p>
  </div>
  <div class="features-grid reveal">
    <div class="feat-card">
      <div class="feat-icon purple">📊</div>
      <h3>ATS Resume Scorer</h3>
      <p>Get a detailed score out of 100 for your resume across 7 parameters — contact info, action verbs, quantified impact, skills density, and more.</p>
      <span class="feat-tag">NEW</span>
    </div>
    <div class="feat-card">
      <div class="feat-icon pink">✏️</div>
      <h3>AI Resume Modifier</h3>
      <p>Paste any job description and get your resume rewritten with role-specific keywords, stronger action verbs, and quantified achievements that pass ATS filters.</p>
      <span class="feat-tag">NEW</span>
    </div>
    <div class="feat-card">
      <div class="feat-icon cyan">🎤</div>
      <h3>Mock Interview + Voice Playback</h3>
      <p>145 personalised questions across ML, DL, GenAI, HR, aptitude, and coding. Record your voice answers and play them back to hear how you sound.</p>
      <span class="feat-tag">NEW</span>
    </div>
    <div class="feat-card">
      <div class="feat-icon green">🏢</div>
      <h3>Company-Specific Mode</h3>
      <p>Prepare for Google, Amazon, TCS, Infosys, Sarvam AI, Quantiphi and more. Get questions tailored to each company's actual interview style and values.</p>
      <span class="feat-tag">NEW</span>
    </div>
    <div class="feat-card">
      <div class="feat-icon orange">🔄</div>
      <h3>Weak Area Retry Mode</h3>
      <p>After your interview, see exactly which topics you scored below 5 in. Click "Practice Weak Areas" to get a focused session on only those topics.</p>
      <span class="feat-tag">NEW</span>
    </div>
    <div class="feat-card">
      <div class="feat-icon red">🧠</div>
      <h3>AI Decision Engine</h3>
      <p>Jobs ranked by our own 5-factor scoring algorithm — not just API calls. Skill graph inference, explainable match percentages, and personalised gap analysis.</p>
      <span class="feat-tag">Intelligence</span>
    </div>
  </div>
</section>

<!-- HOW IT WORKS -->
<section class="section" id="how">
  <div class="reveal" style="text-align:center;">
    <div class="section-tag">Process</div>
    <h2 class="section-title">From resume to interview-ready in <span class="grad2">4 steps</span></h2>
  </div>
  <div class="steps reveal">
    <div class="step">
      <div class="step-num float">1</div>
      <h3>Upload Resume</h3>
      <p>Drop your PDF resume. Our AI extracts skills, domain, projects, and education in seconds.</p>
    </div>
    <div class="step">
      <div class="step-num float" style="animation-delay:0.5s">2</div>
      <h3>Get ATS Score</h3>
      <p>Instant 7-parameter ATS analysis. See exactly what recruiters and ATS systems see.</p>
    </div>
    <div class="step">
      <div class="step-num float" style="animation-delay:1s">3</div>
      <h3>View Career Report</h3>
      <p>Job matches, skill gaps, learning path, and a personalised mentor feedback letter.</p>
    </div>
    <div class="step">
      <div class="step-num float" style="animation-delay:1.5s">4</div>
      <h3>Ace the Interview</h3>
      <p>145 personalised questions, real-time confidence tracking, voice playback, and AI evaluation.</p>
    </div>
  </div>
</section>

<!-- COMPANIES -->
<div class="companies-section" id="companies">
  <p class="companies-label">Prepare for top companies</p>
  <div class="companies-strip">
    <div class="company-chip">🔍 Google</div>
    <div class="company-chip">☁️ Amazon</div>
    <div class="company-chip">🪟 Microsoft</div>
    <div class="company-chip">🤖 Sarvam AI</div>
    <div class="company-chip">📊 Quantiphi</div>
    <div class="company-chip">📈 Fractal</div>
    <div class="company-chip">💼 TCS</div>
    <div class="company-chip">🔷 Infosys</div>
    <div class="company-chip">🟢 Wipro</div>
    <div class="company-chip">🚀 Startups</div>
  </div>
</div>

<!-- TESTIMONIALS -->
<section class="section" id="testimonials">
  <div class="reveal" style="text-align:center;">
    <div class="section-tag">Reviews</div>
    <h2 class="section-title">Students love <span class="grad1">CareerAGI</span></h2>
  </div>
  <div class="testimonials reveal">
    <div class="tcard">
      <p class="tcard-text">The ATS scorer showed me I had zero quantified achievements. After adding metrics, I got 3x more callbacks. This tool is genuinely game-changing.</p>
      <div class="tcard-author">
        <div class="tcard-avatar">P</div>
        <div><div class="tcard-name">Priya S.</div><div class="tcard-role">M.Tech CSE, placed at Quantiphi</div><div class="tcard-stars">★★★★★</div></div>
      </div>
    </div>
    <div class="tcard">
      <p class="tcard-text">The company-specific mode for Amazon had Leadership Principle questions I never would have prepared for. Got through the bar raiser round first try.</p>
      <div class="tcard-author">
        <div class="tcard-avatar">R</div>
        <div><div class="tcard-name">Rahul M.</div><div class="tcard-role">B.Tech IT, placed at Amazon</div><div class="tcard-stars">★★★★★</div></div>
      </div>
    </div>
    <div class="tcard">
      <p class="tcard-text">Weak area retry mode is brilliant. I scored 3/10 in ML theory questions. Practiced only those, retook the interview, scored 8/10. Worth every minute.</p>
      <div class="tcard-author">
        <div class="tcard-avatar">A</div>
        <div><div class="tcard-name">Ananya K.</div><div class="tcard-role">M.Tech AI, placed at Sarvam AI</div><div class="tcard-stars">★★★★★</div></div>
      </div>
    </div>
  </div>
</section>

<!-- CTA -->
<section class="cta-section">
  <div class="cta-glow"></div>
  <div class="reveal">
    <h2>Ready to <span class="grad1">get hired?</span></h2>
    <p>Join thousands of students who used CareerAGI to crack their dream placements. No signup required. Free forever.</p>
    <div class="cta-btns">
      <button class="btn-primary" onclick="openModal()">🚀 Upload Resume — It's Free</button>
      <a href="/ats" class="btn-secondary" style="text-decoration:none;padding:16px 36px;border-radius:12px;font-size:16px;font-weight:600;border:1px solid rgba(124,58,237,0.3);color:var(--text);">📊 Check ATS Score</a>
    </div>
  </div>
</section>

<!-- FOOTER -->
<footer>
  <div class="footer-logo">⚡ CareerAGI</div>
  <div class="footer-links">
    <a href="/upload">Upload Resume</a>
    <a href="/ats">ATS Scorer</a>
    <a href="/support">Emotional Support</a>
    <a href="/db-test">System Status</a>
  </div>
  <div class="footer-copy">© 2026 CareerAGI · Built with AGI Intelligence</div>
</footer>

<!-- UPLOAD MODAL -->
<div class="modal-overlay" id="uploadModal">
  <div class="modal">
    <button class="modal-close" onclick="closeModal()">✕</button>
    <h2>🎓 Analyse Your Resume</h2>
    <p>Upload your PDF resume and get your personalised career report + mock interview in 30 seconds.</p>
    <div class="drop-zone" id="dropZone">
      <input type="file" id="fileInput" accept=".pdf,.docx" onchange="fileSelected(this)">
      <div class="drop-icon">📄</div>
      <div class="drop-text">Drop your resume here or <strong>click to browse</strong></div>
      <div class="file-name" id="fileName"></div>
    </div>
    <button class="upload-btn" id="uploadBtn" onclick="uploadResume()" disabled>🚀 Analyse My Resume</button>
    <div class="upload-progress" id="progressDiv">
      <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
      <div class="progress-status" id="statusText">Uploading...</div>
    </div>
    <div class="result-links" id="resultLinks">
      <a id="reportLink" class="result-link-btn rl-report" href="#" target="_blank">📋 View Career Report + ATS Score</a>
      <a id="interviewLink" class="result-link-btn rl-interview" href="#" target="_blank">🎤 Start Mock Interview</a>
      <p style="color:var(--muted);font-size:11px;text-align:center;">⏳ Full analysis in ~30 seconds. Refresh report if still loading.</p>
    </div>
  </div>
</div>

<script>
// Modal
function openModal(){document.getElementById('uploadModal').classList.add('show');}
function closeModal(){document.getElementById('uploadModal').classList.remove('show');}
document.getElementById('uploadModal').addEventListener('click',e=>{if(e.target===document.getElementById('uploadModal'))closeModal();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});

// Drag drop
const dropZone=document.getElementById('dropZone');
let selectedFile=null;
dropZone.addEventListener('dragover',e=>{e.preventDefault();dropZone.classList.add('dragover');});
dropZone.addEventListener('dragleave',()=>dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop',e=>{e.preventDefault();dropZone.classList.remove('dragover');const f=e.dataTransfer.files[0];if(f)setFile(f);});
function fileSelected(input){if(input.files[0])setFile(input.files[0]);}
function setFile(f){selectedFile=f;document.getElementById('fileName').textContent='📎 '+f.name;document.getElementById('uploadBtn').disabled=false;}

// Upload
async function uploadResume(){
  if(!selectedFile)return;
  const btn=document.getElementById('uploadBtn');btn.disabled=true;btn.textContent='⏳ Analysing...';
  const prog=document.getElementById('progressDiv');const fill=document.getElementById('progressFill');const status=document.getElementById('statusText');
  prog.style.display='block';
  let pct=0;
  const steps=[[10,'Uploading resume...'],[30,'Extracting skills & domain...'],[55,'AI analysis in progress...'],[75,'Generating interview questions...'],[90,'Almost ready...']];
  let si=0;
  const interval=setInterval(()=>{if(si<steps.length){pct=steps[si][0];status.textContent=steps[si][1];si++;}fill.style.width=pct+'%';},1200);
  try{
    const form=new FormData();form.append('resume',selectedFile);
    const res=await fetch('/uploadresume',{method:'POST',body:form});
    const data=await res.json();
    clearInterval(interval);fill.style.width='100%';status.textContent='✅ Done!';
    if(data.interview_link){
      const report=data.interview_link.replace('/interview/','/report/');
      document.getElementById('reportLink').href=report;
      document.getElementById('interviewLink').href=data.interview_link;
      document.getElementById('resultLinks').classList.add('show');
      btn.textContent='✅ Upload another';btn.disabled=false;
    }else{status.textContent='❌ '+(data.error||'Upload failed');btn.textContent='🚀 Try Again';btn.disabled=false;}
  }catch(e){clearInterval(interval);status.textContent='❌ Connection error';btn.textContent='🚀 Try Again';btn.disabled=false;}
}

// Scroll reveal
const observer=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting)e.target.classList.add('visible');});},{threshold:0.1});
document.querySelectorAll('.reveal').forEach(el=>observer.observe(el));

// Counter animation
function animateCounter(el,target,suffix=''){
  let current=0;const step=target/60;
  const timer=setInterval(()=>{current+=step;if(current>=target){current=target;clearInterval(timer);}el.textContent=Math.round(current)+(suffix||'');},16);
}
const statsObserver=new IntersectionObserver(entries=>{
  entries.forEach(e=>{
    if(e.isIntersecting){
      const nums=e.target.querySelectorAll('.stat-num');
      nums.forEach(n=>{
        const text=n.textContent;
        const num=parseInt(text);
        if(!isNaN(num)){const suffix=text.replace(/[0-9]/g,'');animateCounter(n,num,suffix);}
      });
      statsObserver.unobserve(e.target);
    }
  });
},{threshold:0.5});
const heroStats=document.querySelector('.hero-stats');
if(heroStats)statsObserver.observe(heroStats);
</script>
</body>
</html>
"""

ATS_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ATS Resume Scorer — CareerAGI</title>
<link href="https://fonts.googleapis.com/css2?family=Clash+Display:wght@400;600;700&family=Satoshi:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{--bg:#050508;--card:#12121c;--card2:#1a1a28;--purple:#7c3aed;--pink:#ec4899;--cyan:#06b6d4;--green:#10b981;--orange:#f59e0b;--red:#ef4444;--text:#f0f0f8;--muted:#8888aa;--border:rgba(124,58,237,0.2);}
body{font-family:"Satoshi",sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}
nav{padding:16px 32px;display:flex;align-items:center;justify-content:space-between;background:rgba(5,5,8,0.9);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;}
.nav-logo{font-family:"Clash Display",sans-serif;font-size:20px;font-weight:700;background:linear-gradient(135deg,#a855f7,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;text-decoration:none;}
.nav-back{color:var(--muted);text-decoration:none;font-size:13px;display:flex;align-items:center;gap:6px;}
.container{max-width:1000px;margin:0 auto;padding:40px 20px;}
h1{font-family:"Clash Display",sans-serif;font-size:40px;font-weight:700;margin-bottom:8px;}
.sub{color:var(--muted);font-size:16px;margin-bottom:40px;}
.grad{background:linear-gradient(135deg,#a855f7,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;}
@media(max-width:768px){.grid{grid-template-columns:1fr;}}
.panel{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:28px;}
.panel h2{font-family:"Clash Display",sans-serif;font-size:18px;margin-bottom:16px;}
textarea{width:100%;background:var(--card2);border:1px solid var(--border);border-radius:10px;padding:14px;color:var(--text);font-family:inherit;font-size:13px;resize:vertical;outline:none;min-height:200px;transition:border-color 0.2s;}
textarea:focus{border-color:var(--purple);}
.label{font-size:12px;color:var(--muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:1px;}
.score-btn{width:100%;margin-top:16px;background:linear-gradient(135deg,#7c3aed,#ec4899);color:#fff;border:none;padding:14px;border-radius:10px;font-size:15px;font-weight:600;cursor:pointer;font-family:inherit;transition:opacity 0.2s;}
.score-btn:hover{opacity:0.9;}
.score-btn:disabled{opacity:0.4;cursor:not-allowed;}
.improve-btn{width:100%;margin-top:10px;background:transparent;color:#a855f7;border:1px solid rgba(124,58,237,0.4);padding:12px;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;transition:all 0.2s;}
.improve-btn:hover{background:rgba(124,58,237,0.1);}

/* Score display */
.score-display{display:none;}
.score-display.show{display:block;}
.score-header{display:flex;align-items:center;gap:24px;margin-bottom:28px;padding:24px;background:var(--card2);border-radius:14px;}
.score-circle{width:100px;height:100px;border-radius:50%;position:relative;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.score-circle svg{position:absolute;inset:0;transform:rotate(-90deg);}
.score-circle-inner{position:relative;text-align:center;}
.score-big{font-family:"Clash Display",sans-serif;font-size:28px;font-weight:700;}
.score-max{font-size:11px;color:var(--muted);}
.score-info h3{font-family:"Clash Display",sans-serif;font-size:22px;margin-bottom:4px;}
.score-info p{color:var(--muted);font-size:13px;}
.score-grade{display:inline-block;padding:4px 16px;border-radius:20px;font-weight:700;font-size:16px;margin-top:8px;}

/* Breakdown */
.breakdown{display:flex;flex-direction:column;gap:12px;margin-bottom:24px;}
.breakdown-item{background:var(--card2);border-radius:10px;padding:14px 16px;}
.breakdown-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}
.breakdown-label{font-size:13px;font-weight:600;}
.breakdown-score{font-size:12px;font-weight:700;}
.breakdown-bar{height:5px;background:rgba(255,255,255,0.1);border-radius:3px;overflow:hidden;}
.breakdown-fill{height:100%;border-radius:3px;transition:width 0.8s ease;}
.breakdown-details{font-size:12px;color:var(--muted);margin-top:6px;}
.keyword-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;}
.ktag{padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;}
.ktag-match{background:rgba(16,185,129,0.15);color:var(--green);border:1px solid rgba(16,185,129,0.3);}
.ktag-miss{background:rgba(239,68,68,0.1);color:var(--red);border:1px solid rgba(239,68,68,0.2);}

/* Improvements */
.improve-section{margin-top:24px;display:none;}
.improve-section.show{display:block;}
.improve-section h3{font-family:"Clash Display",sans-serif;font-size:16px;margin-bottom:14px;}
.bullet-item{background:var(--card2);border-radius:8px;padding:12px 14px;margin-bottom:8px;font-size:13px;color:var(--text);border-left:3px solid var(--green);}
.replace-item{background:var(--card2);border-radius:8px;padding:10px 14px;margin-bottom:6px;font-size:12px;}
.replace-old{color:var(--red);text-decoration:line-through;}
.replace-new{color:var(--green);margin-top:4px;}
.tip-item{background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.2);border-radius:8px;padding:10px 14px;margin-bottom:6px;font-size:13px;color:#c4b5fd;}
.spinner{width:32px;height:32px;border:3px solid var(--card2);border-top-color:var(--purple);border-radius:50%;animation:spin 0.8s linear infinite;margin:20px auto;}
@keyframes spin{to{transform:rotate(360deg)}}
.loading-msg{text-align:center;color:var(--muted);font-size:14px;padding:20px;}
</style>
</head>
<body>
<nav>
  <a href="/" class="nav-logo">⚡ CareerAGI</a>
  <a href="/" class="nav-back">← Back to Home</a>
</nav>
<div class="container">
  <h1>📊 ATS Resume <span class="grad">Scorer</span></h1>
  <p class="sub">Get your resume scored across 7 ATS parameters and get AI-powered improvements tailored to any job description.</p>
  <div class="grid">
    <!-- Input Panel -->
    <div class="panel">
      <h2>Your Resume</h2>
      <div class="label">Paste resume text</div>
      <textarea id="resumeInput" placeholder="Paste your full resume text here...&#10;&#10;Include all sections: Contact, Education, Skills, Projects, Experience"></textarea>
      <div class="label" style="margin-top:16px;">Job Description (Optional — for keyword matching)</div>
      <textarea id="jdInput" placeholder="Paste the job description here for keyword gap analysis..." style="min-height:120px;"></textarea>
      <button class="score-btn" id="scoreBtn" onclick="scoreResume()">📊 Score My Resume</button>
      <button class="improve-btn" id="improveBtn" onclick="improveResume()" style="display:none;">✨ AI Improve My Resume</button>
    </div>
    <!-- Results Panel -->
    <div class="panel">
      <h2>Your ATS Score</h2>
      <div id="scorePlaceholder" style="text-align:center;padding:60px 20px;color:var(--muted);">
        <div style="font-size:48px;margin-bottom:12px;">📋</div>
        <p>Paste your resume and click Score to see your ATS analysis</p>
      </div>
      <div class="score-display" id="scoreDisplay">
        <div class="score-header">
          <div class="score-circle" id="scoreCircle">
            <svg width="100" height="100" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="8"/>
              <circle cx="50" cy="50" r="42" fill="none" stroke="url(#grad)" stroke-width="8" stroke-linecap="round" id="scoreArc" stroke-dasharray="264" stroke-dashoffset="264"/>
              <defs><linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#7c3aed"/><stop offset="100%" stop-color="#ec4899"/></linearGradient></defs>
            </svg>
            <div class="score-circle-inner">
              <div class="score-big" id="scoreBig">0</div>
              <div class="score-max">/100</div>
            </div>
          </div>
          <div class="score-info">
            <h3 id="scoreLevel">Analysing...</h3>
            <p id="scoreDesc">Your ATS compatibility score</p>
            <div class="score-grade" id="scoreGrade"></div>
          </div>
        </div>
        <div class="breakdown" id="breakdown"></div>
        <div class="improve-section" id="improveSection">
          <h3>✨ AI Improvements</h3>
          <div id="improveContent"></div>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
let lastResumeText = "";
let lastAnalysis = null;

async function scoreResume() {
  const resumeText = document.getElementById("resumeInput").value.trim();
  const jdText = document.getElementById("jdInput").value.trim();
  if (!resumeText) { alert("Please paste your resume text first"); return; }
  lastResumeText = resumeText;
  const btn = document.getElementById("scoreBtn");
  btn.disabled = true; btn.textContent = "⏳ Analysing...";
  document.getElementById("scorePlaceholder").innerHTML = '<div class="spinner"></div><p class="loading-msg">Analysing your resume across 7 ATS parameters...</p>';
  document.getElementById("scoreDisplay").classList.remove("show");

  try {
    const res = await fetch("/ats_score", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({resume_text: resumeText, job_description: jdText, skills: []})
    });
    const data = await res.json();
    lastAnalysis = data;
    displayScore(data);
    document.getElementById("improveBtn").style.display = "block";
  } catch(e) {
    document.getElementById("scorePlaceholder").innerHTML = '<p style="color:#ef4444;text-align:center;padding:40px;">Error analysing resume. Please try again.</p>';
  }
  btn.disabled = false; btn.textContent = "📊 Re-Score";
}

function displayScore(data) {
  document.getElementById("scorePlaceholder").style.display = "none";
  document.getElementById("scoreDisplay").classList.add("show");

  const total = data.total_score || 0;
  const grade = data.grade || "F";
  const level = data.ats_level || "Poor";

  // Animate circle
  const circumference = 264;
  const offset = circumference - (total / 100) * circumference;
  setTimeout(() => {
    document.getElementById("scoreArc").style.strokeDashoffset = offset;
    document.getElementById("scoreArc").style.transition = "stroke-dashoffset 1.2s ease";
  }, 100);

  // Counter
  let c = 0;
  const timer = setInterval(() => { c = Math.min(c + 2, total); document.getElementById("scoreBig").textContent = c; if(c >= total) clearInterval(timer); }, 20);

  document.getElementById("scoreLevel").textContent = level + " ATS Score";
  document.getElementById("scoreDesc").textContent = data.top_issues?.length ? "Issues: " + (data.top_issues || []).join(", ") : "Great job!";

  const gradeEl = document.getElementById("scoreGrade");
  gradeEl.textContent = "Grade: " + grade;
  const gradeColors = {"A+":"#10b981","A":"#10b981","B":"#06b6d4","C":"#f59e0b","D":"#f97316","F":"#ef4444"};
  gradeEl.style.background = (gradeColors[grade] || "#ef4444") + "22";
  gradeEl.style.color = gradeColors[grade] || "#ef4444";
  gradeEl.style.border = "1px solid " + (gradeColors[grade] || "#ef4444") + "44";

  // Breakdown
  const breakdown = document.getElementById("breakdown");
  breakdown.innerHTML = "";
  const colorMap = {contact_info:"#06b6d4",skills_section:"#7c3aed",action_verbs:"#ec4899",quantified_impact:"#f59e0b",education:"#10b981",projects:"#a855f7",keywords:"#f97316"};

  Object.entries(data.breakdown || {}).forEach(([key, val]) => {
    const pct = Math.round((val.score / val.max) * 100);
    const color = colorMap[key] || "#7c3aed";
    const statusColor = val.score >= val.max * 0.8 ? "#10b981" : val.score >= val.max * 0.5 ? "#f59e0b" : "#ef4444";

    let extraHtml = "";
    if (val.weak_found?.length) extraHtml += `<div style="color:#ef4444;font-size:11px;margin-top:4px;">⚠️ Weak verbs: ${val.weak_found.join(", ")}</div>`;
    if (val.suggestions?.length) extraHtml += `<div style="color:#10b981;font-size:11px;margin-top:2px;">💡 Try: ${val.suggestions.join(", ")}</div>`;
    if (val.matched?.length) {
      extraHtml += `<div class="keyword-tags">${val.matched.slice(0,6).map(k=>`<span class="ktag ktag-match">✓ ${k}</span>`).join("")}</div>`;
    }
    if (val.missing?.length) {
      extraHtml += `<div class="keyword-tags">${val.missing.slice(0,5).map(k=>`<span class="ktag ktag-miss">+ ${k}</span>`).join("")}</div>`;
    }

    breakdown.innerHTML += `
      <div class="breakdown-item">
        <div class="breakdown-header">
          <span class="breakdown-label">${val.label || key}</span>
          <span class="breakdown-score" style="color:${statusColor}">${val.score}/${val.max} — ${val.status}</span>
        </div>
        <div class="breakdown-bar"><div class="breakdown-fill" style="width:${pct}%;background:${color};"></div></div>
        <div class="breakdown-details">${val.details || ""}</div>
        ${val.tip ? `<div style="color:#a855f7;font-size:11px;margin-top:4px;">💡 ${val.tip}</div>` : ""}
        ${extraHtml}
      </div>`;
  });
}

async function improveResume() {
  const jdText = document.getElementById("jdInput").value.trim();
  const btn = document.getElementById("improveBtn");
  btn.disabled = true; btn.textContent = "⏳ Generating improvements...";
  const section = document.getElementById("improveSection");
  const content = document.getElementById("improveContent");
  section.classList.add("show");
  content.innerHTML = '<div class="spinner"></div><p class="loading-msg">AI is rewriting your resume bullets with action keywords...</p>';

  try {
    const res = await fetch("/improve_resume", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({resume_text: lastResumeText, job_description: jdText})
    });
    const data = await res.json();
    let html = "";
    if (data.improved_summary) html += `<div style="background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.2);border-radius:10px;padding:14px;margin-bottom:16px;"><div style="font-size:11px;color:#a855f7;font-weight:700;margin-bottom:6px;letter-spacing:1px;">📝 IMPROVED SUMMARY</div><p style="font-size:13px;line-height:1.6;">${data.improved_summary}</p></div>`;
    if (data.improved_bullets?.length) {
      html += `<div style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">✅ Improved Bullets</div>`;
      data.improved_bullets.forEach(b => html += `<div class="bullet-item">${b}</div>`);
    }
    if (data.weak_replaced?.length) {
      html += `<div style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin:12px 0 8px;">🔄 Weak → Strong Replacements</div>`;
      data.weak_replaced.forEach(r => html += `<div class="replace-item"><div class="replace-old">✗ ${r.original}</div><div class="replace-new">✓ ${r.improved}</div></div>`);
    }
    if (data.ats_tips?.length) {
      html += `<div style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin:12px 0 8px;">💡 ATS Tips</div>`;
      data.ats_tips.forEach(t => html += `<div class="tip-item">${t}</div>`);
    }
    content.innerHTML = html || "<p style='color:var(--muted);text-align:center;padding:20px;'>No improvements generated — try again</p>";
  } catch(e) { content.innerHTML = "<p style='color:#ef4444;text-align:center;'>Error — please try again</p>"; }
  btn.disabled = false; btn.textContent = "✨ Regenerate";
}
</script>
</body>
</html>"""

app = Flask(__name__, static_folder="interview_app")
CORS(app)

@app.after_request
def add_security_headers(response):
    """Add security headers to every response."""
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]          = "DENY"
    response.headers["X-XSS-Protection"]         = "1; mode=block"
    response.headers["Referrer-Policy"]          = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"]            = "no-store, no-cache, must-revalidate"
    return response

# ── SECURITY CONFIG ──
import secrets
app.config["SECRET_KEY"]         = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB max upload

# ── RATE LIMITING ──
# Simple in-memory rate limiter — no extra packages needed
import time
from collections import defaultdict
_request_counts = defaultdict(list)  # {ip: [timestamp, ...]}

def check_rate_limit(ip, max_requests=10, window_seconds=60):
    """Allow max_requests per window_seconds per IP."""
    now = time.time()
    _request_counts[ip] = [t for t in _request_counts[ip] if now - t < window_seconds]
    if len(_request_counts[ip]) >= max_requests:
        return False
    _request_counts[ip].append(now)
    return True

@app.before_request
def cleanup_old_sessions():
    """Remove sessions older than 2 hours to free memory and protect privacy."""
    now = time.time()
    expired = [sid for sid, sess in list(INTERVIEW_SESSIONS.items())
               if now - sess.get("uploaded_at", now) > 7200]  # 2 hours
    for sid in expired:
        INTERVIEW_SESSIONS.pop(sid, None)

@app.before_request
def rate_limit_uploads():
    """Rate limit resume uploads — max 5 per minute per IP."""
    if request.path == "/uploadresume" and request.method == "POST":
        ip = request.remote_addr or "unknown"
        if not check_rate_limit(ip, max_requests=5, window_seconds=60):
            return jsonify({"error": "Too many uploads. Please wait 1 minute."}), 429

# ── INPUT SANITIZATION ──
import html
def sanitize(text, max_len=50000):
    """Remove HTML tags and limit length to prevent XSS and prompt injection."""
    if not text: return ""
    clean = html.escape(str(text))
    return clean[:max_len]

def sanitize_resume_text(text):
    """Sanitize resume text before passing to AI — prevent prompt injection."""
    if not text: return ""
    # Remove any attempt to inject AI instructions
    dangerous_patterns = [
        "ignore previous instructions",
        "ignore all instructions",
        "you are now",
        "disregard your",
        "forget your instructions",
        "system prompt",
        "jailbreak",
    ]
    text_lower = text.lower()
    for pattern in dangerous_patterns:
        if pattern in text_lower:
            # Replace the suspicious line
            text = "\n".join(
                "[REMOVED]" if pattern in line.lower() else line
                for line in text.split("\n")
            )
    return text[:50000]  # limit to 50K chars

# ================= CONFIG =====================
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL",    "qwen2.5:3b")
OLLAMA_ENABLED  = True

GROQ_API_KEYS = [
    os.environ.get("GROQ_API_KEY_1", ""),
    os.environ.get("GROQ_API_KEY_2", ""),
    os.environ.get("GROQ_API_KEY_3", ""),
    os.environ.get("GROQ_API_KEY_4", ""),
    os.environ.get("GROQ_API_KEY_5", ""),
]
GROQ_API_KEYS = [k.strip() for k in GROQ_API_KEYS if k and k.strip()]
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODELS   = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "moonshotai/kimi-k2-instruct",
    "qwen/qwen3-32b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "groq/compound",
    "groq/compound-mini",
]

# FIX: Correct MongoDB password
MONGODB_URI = os.environ.get("MONGODB_URI", "")

BASE_URL          = os.environ.get("BASE_URL", "http://localhost:5000")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
JSEARCH_API_KEY   = os.environ.get("JSEARCH_API_KEY", "")
ADZUNA_APP_ID     = os.environ.get("ADZUNA_APP_ID",     "")
ADZUNA_API_KEY    = os.environ.get("ADZUNA_API_KEY",    "")
HASDATA_API_KEY   = os.environ.get("HASDATA_API_KEY",   "")
SCRAPEOPS_API_KEY = os.environ.get("SCRAPEOPS_API_KEY", "")
EMAIL_ENABLED  = os.environ.get("EMAIL_ENABLED", "false").lower() == "true"
EMAIL_SENDER   = os.environ.get("EMAIL_SENDER",   "your_gmail@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "your_app_password_here")
EMAIL_SUBJECT  = "Your AGI Career Report & Mock Interview — {name}"


# ================= AI CLIENT =====================
class AIClient:
    def __init__(self):
        self.groq_keys      = GROQ_API_KEYS
        self.groq_ok        = bool(GROQ_API_KEYS)
        self.groq_key_idx   = 0
        self.groq_model_idx = 0
        self.gemini_ok      = False  # Gemini not used — Ollama + Groq only
        self.openrouter_ok  = False  # OpenRouter not used
        self._ollama_sem    = _threading.Semaphore(2)  # max 2 concurrent Ollama calls
        self.ollama_ok = False
        if OLLAMA_ENABLED:
            try:
                r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    self.ollama_ok = True
                    print(f"  [AI] 🦙 Ollama active — model: {OLLAMA_MODEL} | available: {models}")
                else:
                    print(f"  [AI] 🦙 Ollama running but returned {r.status_code}")
            except Exception:
                print(f"  [AI] 🦙 Ollama not running — run: ollama serve")

        if self.ollama_ok:
            print(f"  [AI] ✅ Primary: Ollama ({OLLAMA_MODEL}) | Fallback: Groq ({len(self.groq_keys)} keys)")
        elif self.groq_ok:
            print(f"  [AI] ✅ Groq only — {GROQ_MODELS[0]} ({len(self.groq_keys)} keys)")
        else:
            print("  [AI] ⚠️  No providers available!")

    def _gemini_call(self, messages, temperature, max_tokens):
        """Google Gemini API — 1500 free requests/day."""
        try:
            # Convert messages to Gemini format
            parts = []
            for m in messages:
                role = "User" if m["role"] == "user" else "Assistant"
                parts.append(role + ": " + m["content"])
            prompt = "\n".join(parts)
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": min(max_tokens, 8192),
                        "responseMimeType": "text/plain",
                    }
                },
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            elif resp.status_code == 429:
                print("  [Gemini] Daily quota reached — falling back")
                return None
            else:
                print(f"  [Gemini] Error {resp.status_code}: {resp.text[:100]}")
                return None
        except Exception as e:
            print(f"  [Gemini] Exception: {e}")
            return None

    def _openrouter_call(self, messages, temperature, max_tokens):
        """OpenRouter — free models: mistral-7b, llama-3-8b etc."""
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "HTTP-Referer": "https://career-agi.onrender.com",
                    "X-Title": "CareerAGI",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "mistralai/mistral-7b-instruct:free",
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": min(max_tokens, 4000),
                },
                timeout=30
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            else:
                print(f"  [OpenRouter] Error {resp.status_code}")
                return None
        except Exception as e:
            print(f"  [OpenRouter] Exception: {e}")
            return None

    def _check_ollama(self):
        """Ping Ollama to see if it has come back online. Returns True if available."""
        try:
            r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        self._ollama_retry_at = __import__('time').time() + 30  # retry again in 30s
        return False

    def call(self, messages, temperature=0.2, max_tokens=4000, retries=4):
        """
        4-TIER AI CHAIN — zero single point of failure:
        1. Ollama (local)   — free, offline, primary when running
        2. Gemini Flash     — 1500 free/day, fast, great JSON
        3. Groq             — fast, 5-key rotation fallback
        4. OpenRouter       — free Mistral/Llama models, last resort
        """
        # Tier 1: Ollama — local, completely free, no internet needed
        # Auto-retry Ollama after 30s cooldown
        import time as _t
        if OLLAMA_ENABLED and not self.ollama_ok:
            if _t.time() > getattr(self, '_ollama_retry_at', 0):
                self.ollama_ok = self._check_ollama()
                if self.ollama_ok:
                    print("  [Ollama] Back online!")
        if OLLAMA_ENABLED and self.ollama_ok:
            result = self._ollama_call(messages, temperature, max_tokens)
            if result:
                return result
            print("  [AI] Ollama unavailable — trying Gemini")

        # Tier 2: Gemini Flash — 1500 free requests/day, fast
        if self.gemini_ok:
            result = self._gemini_call(messages, temperature, max_tokens)
            if result:
                return result
            print("  [AI] Gemini quota reached — trying Groq")

        # Tier 3: Groq — fast cloud, 5-key rotation
        if self.groq_ok:
            result = self._groq_call(messages, temperature, max_tokens)
            if result:
                return result
            print("  [AI] Groq exhausted — trying OpenRouter")

        # Tier 4: OpenRouter — free Mistral/Llama, last resort
        if self.openrouter_ok:
            result = self._openrouter_call(messages, temperature, max_tokens)
            if result:
                return result

        print("  [AI] ❌ All providers exhausted.")
        return None

    def _ollama_call(self, messages, temperature, max_tokens):
        # One Ollama call at a time — if busy, wait up to 2s then use Groq
        acquired = self._ollama_sem.acquire(blocking=True, timeout=2)
        if not acquired:
            print("  [Ollama] Busy — routing to Groq")
            return None
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model":    OLLAMA_MODEL,
                    "messages": messages,
                    "stream":   False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": min(max_tokens, 1500),  # cap at 1500 for faster responses
                    }
                },
                timeout=20  # 20s — if Ollama is busy or slow, fail fast and use Groq
            )
            if resp.status_code == 200:
                content = resp.json()["message"]["content"]
                if content and len(content.strip()) > 0:
                    return content
                print("  [Ollama] Empty response")
            else:
                print(f"  [Ollama] HTTP {resp.status_code}: {resp.text[:100]}")
        except requests.exceptions.ConnectionError:
            print("  [Ollama] ❌ Connection refused — is ollama running?")
            self.ollama_ok = False
            self._ollama_retry_at = __import__('time').time() + 30
            self._ollama_retry_at = __import__('time').time() + 30
        except requests.exceptions.Timeout:
            print("  [Ollama] ⏱ Timeout — falling back to Groq")
            return None
        except Exception as e:
            print(f"  [Ollama] Error: {e}")
            return None
        finally:
            try: self._ollama_sem.release()
            except: pass

    def _groq_call(self, messages, temperature, max_tokens, retries=6):
        keys_tried = set()
        for attempt in range(retries):
            key_idx = self.groq_key_idx % len(self.groq_keys)
            key     = self.groq_keys[key_idx]
            model   = GROQ_MODELS[self.groq_model_idx % len(GROQ_MODELS)]
            try:
                resp = requests.post(
                    f"{GROQ_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": messages,
                          "temperature": temperature, "max_tokens": max_tokens},
                    timeout=30
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                elif resp.status_code == 429:
                    err_msg = resp.json().get("error", {}).get("message", "")
                    if "day" in err_msg.lower() or "quota" in err_msg.lower():
                        print(f"  [Groq] Daily quota hit on key #{key_idx+1} — rotating key")
                        keys_tried.add(key_idx)
                        self.groq_key_idx += 1
                        if len(keys_tried) >= len(self.groq_keys):
                            print("  [Groq] All keys quota exhausted")
                            return None
                    else:
                        print(f"  [Groq] Rate limit key #{key_idx+1} — rotating...")
                        self.groq_key_idx   += 1
                        self.groq_model_idx += 1
                        time.sleep(3)
                elif resp.status_code == 400:
                    err_msg = resp.json().get("error", {}).get("message", "")
                    if "decommissioned" in err_msg or "deprecated" in err_msg or "not supported" in err_msg:
                        print(f"  [Groq] Model {model} decommissioned — skipping")
                        self.groq_model_idx += 1
                        if self.groq_model_idx % len(GROQ_MODELS) == 0:
                            return None
                    else:
                        print(f"  [Groq] HTTP 400: {err_msg[:100]}")
                        return None
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
        return None

nvidia_client = AIClient()
groq_rotator  = nvidia_client  # uses Ollama→Groq pipeline

# Groq-only client for jobs/resources/feedback — never touches Ollama
class GroqOnlyClient:
    """Bypasses Ollama entirely — uses Groq API directly.
    Used for jobs, resources, feedback so Ollama is free for questions."""
    def __init__(self):
        self.keys      = GROQ_API_KEYS
        self.key_idx   = 0
        self.model_idx = 0
        self._lock     = _threading.Lock()

    def call(self, messages, temperature=0.2, max_tokens=2000, **kwargs):
        if not self.keys: return None
        models = ["llama-3.3-70b-versatile","llama-3.1-8b-instant","gemma2-9b-it"]
        for attempt in range(min(3, len(self.keys))):
            with self._lock:
                key   = self.keys[self.key_idx % len(self.keys)]
                model = models[self.model_idx % len(models)]
                self.key_idx += 1
            try:
                import requests as _req
                resp = _req.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                    timeout=30
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                print(f"  [Groq] Error (attempt {attempt+1}): {e}")
        return None

groq_only = GroqOnlyClient()  # Use this for jobs, resources, feedback
INTERVIEW_SESSIONS = {}

# ================= UTILS =====================
def safe_cell(value):
    if value is None: return ""
    if isinstance(value, list): return ", ".join(map(str, value))
    if isinstance(value, dict): return json.dumps(value, ensure_ascii=False)
    return str(value)

def groq_json(prompt, temperature=0.2, max_tokens=4000, use_ollama=True):
    """JSON generation. use_ollama=True for analysis/questions, False for jobs/resources."""
    try:
        client = groq_rotator if use_ollama else groq_only
        raw = client.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature, max_tokens=max_tokens
        )
        if not raw: return None
        import re as _re
        raw = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw)
        if "```" in raw:
            raw = _re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        s = raw.find('{'); e = raw.rfind('}') + 1
        if s != -1 and e > s:
            raw = raw[s:e]
        raw = _re.sub(r',\s*([}\]])', r'\1', raw)
        raw = _re.sub(r'(?<!\\)\n', ' ', raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raw2 = raw.replace("'", '"')
            try: return json.loads(raw2)
            except Exception: return None
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
            temperature=temperature, max_tokens=1000
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

# ================= BASIC DETAILS =====================
def extract_basic_details(text, filename):
    email = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    phone = re.findall(r"\+?\d[\d\s\-]{8,15}", text)
    name  = text.strip().split("\n")[0][:60]
    cgpa_match    = re.findall(r"(?:CGPA|GPA|cgpa|gpa)[:\s]*([0-9]+\.?[0-9]*)", text)
    percent_match = re.findall(r"([0-9]+\.?[0-9]*)\s*%", text)
    degree_match  = re.findall(
        r"(B\.?Tech|M\.?Tech|B\.?E|M\.?E|BCA|MCA|B\.?Sc|M\.?Sc|MBA|B\.?Com|Ph\.?D)[^\n]*",
        text, re.IGNORECASE
    )
    return {
        "filename":  filename,
        "name":      name,
        "email":     email[0] if email else "",
        "phone":     phone[0] if phone else "",
        "cgpa":      cgpa_match[0] if cgpa_match else (percent_match[0] + "%" if percent_match else ""),
        "education": degree_match[0] if degree_match else "Not detected"
    }

# ================= AI ANALYSIS =====================
def ai_analyze(resume_text):
    print("  [A] Running deep resume analysis...")
    resume_chunk = resume_text[:4000]

    main_prompt = f"""You are an expert resume analyst.

RESUME:
{resume_chunk}

Return ONLY valid JSON:
{{
  "domain": "The candidate's primary professional field — e.g. 'Machine Learning', 'Civil Engineering', 'Medicine', 'Finance', 'Law', 'Education', 'Mechanical Engineering', 'Pharmacy'. Be specific to their actual background.",
  "skills": ["Extract ALL professional skills for this candidate's field. CS/Tech: Python, TensorFlow, SQL. Medical: Anatomy, Pharmacology, Patient Care. Law: Contract Law, IPC, Legal Research. Finance: Financial Modeling, Tally, GST. Mechanical: AutoCAD, SolidWorks, Thermodynamics. STRICTLY EXCLUDE: degree names, school names, 10th, 12th, Intermediate, B.Tech, college names, CGPA"],
  "subjects_studied": ["Academic subjects like Data Structures, DBMS, Machine Learning"],
  "projects": ["Project titles only"],
  "tools_and_software": ["Tools like VS Code, Jupyter, Git, Figma"],
  "experience_context": "Internship/work experience or 'Fresher with academic projects'",
  "strengths": "2 sentences about candidate strengths",
  "weaknesses": "2 sentences about areas to improve",
  "skill_gaps": "Missing TECHNICAL SKILLS for target role only — never education qualifications",
  "achievements": "Key achievements",
  "career_fit": ["3-5 job titles like 'ML Engineer', 'Data Scientist'"],
  "education": "Degree and college name",
  "confidence_level": "High or Medium or Low"
}}

IMPORTANT: The skills array must contain ONLY programmming languages, frameworks, libraries, tools. Never include school/college/degree/qualification names."""

    result = groq_json(main_prompt, max_tokens=2000)

    if not result:
        print("  [A] First attempt failed — retrying with simpler prompt...")
        simple_prompt = f"""Extract info from this resume. Return ONLY valid JSON, no special characters in values.

RESUME:
{resume_chunk[:2000]}

{{
  "domain": "primary field like Machine Learning or Computer Science",
  "skills": ["skill1", "skill2", "skill3", "skill4", "skill5"],
  "career_fit": ["Job Title 1", "Job Title 2", "Job Title 3"],
  "education": "degree and college",
  "strengths": "technically strong candidate",
  "weaknesses": "needs more industry experience",
  "skill_gaps": "docker, cloud, deployment, mlops",
  "confidence_level": "Medium",
  "projects": ["project1", "project2"],
  "subjects_studied": [],
  "tools_and_software": [],
  "experience_context": "fresher with academic projects",
  "achievements": "good academic performance"
}}"""
        result = groq_json(simple_prompt, max_tokens=1000, temperature=0.1)

    if not result:
        print("  [A] Both attempts failed — returning empty analysis")
        return {
            "domain": "General", "skills": [], "subjects_studied": [],
            "projects": [], "tools_and_software": [],
            "experience_context": "", "strengths": "", "weaknesses": "",
            "skill_gaps": "", "achievements": "", "career_fit": [],
            "education": "", "confidence_level": "Medium"
        }

    all_skills = result.get("skills", [])
    for extra in result.get("subjects_studied", []) + result.get("tools_and_software", []):
        if extra and extra not in all_skills:
            all_skills.append(extra)

    # ── POST-PROCESS: Remove education/qualification items from skills ──
    education_keywords = {
        'b.tech','m.tech','btech','mtech','b.e','m.e','bca','mca','b.sc','m.sc',
        'mba','phd','ph.d','10th','12th','ssc','hsc','intermediate','secondary',
        'mpc','bipc','cec','hec','cbse','icse','state board','matriculation',
        'school','college','university','institute','academy',
        'cgpa','gpa','percentage','marks','grade','first class','distinction',
        'pursuing','completed','passed','qualified'
    }

    def is_education(skill):
        s = skill.lower().strip()
        if any(kw in s for kw in education_keywords):
            return True
        # Remove items that look like qualifications: "B.Tech - CSE", "Intermediate (MPC)"
        if '(mpc)' in s or '(bipc)' in s or '(cec)' in s:
            return True
        if s.startswith('b.') or s.startswith('m.') or s.startswith('be ') or s.startswith('me '):
            return True
        return False

    filtered_skills = [s for s in all_skills if s and not is_education(s)]
    if len(filtered_skills) < len(all_skills):
        removed = [s for s in all_skills if is_education(s)]
        print(f"  [A] Filtered education from skills: {removed}")
    result["skills"] = filtered_skills

    print(f"  [A] Domain: {result.get('domain','?')} | Skills: {filtered_skills[:5]} ...")
    return result

# ================= JOB FETCH =====================
def calculate_match_percent(job_description, candidate_skills):
    if not job_description or not candidate_skills: return 0
    desc_lower  = job_description.lower()
    skills_list = [s.strip().lower() for s in candidate_skills if len(s.strip()) > 1]
    if not skills_list: return 0
    matched = sum(1 for skill in skills_list if skill in desc_lower)
    return min(round((matched / len(skills_list)) * 100), 99)

def generate_jobs_from_logic(analysis):
    """
    Pure local job generation — NO API needed.
    Uses decision logic based on candidate domain, skills, career fit.
    This is YOUR intelligence, not an external service.
    """
    domain   = analysis.get("domain", "General")
    skills   = analysis.get("skills", [])[:8]
    career   = analysis.get("career_fit", ["Professional"])
    domain_cat = get_domain_category(domain)
    employers  = get_domain_employers(domain)

    # Job templates per domain category
    templates = {
        "tech": [
            ("Machine Learning Engineer",    "Build and deploy ML models at scale",    ["Python","ML","TensorFlow"], "₹6-12 LPA"),
            ("Data Scientist",               "Analyse data and build predictive models",["Python","Statistics","SQL"], "₹5-10 LPA"),
            ("AI Research Engineer",         "Research and prototype AI solutions",     ["PyTorch","Research","NLP"], "₹8-15 LPA"),
            ("Software Developer",           "Build scalable backend systems",          ["Python","APIs","Databases"], "₹4-8 LPA"),
            ("Data Analyst",                 "Transform data into business insights",   ["SQL","Excel","Tableau"], "₹3-6 LPA"),
        ],
        "medical": [
            ("Junior Resident Doctor",       "Clinical patient care and diagnosis",     ["Clinical Examination","Diagnostics"], "₹50-80K/month"),
            ("Medical Officer",              "Primary healthcare and treatment",        ["Patient Care","Pharmacology"], "₹60-90K/month"),
            ("Clinical Research Associate",  "Manage clinical trials and data",         ["Research","Documentation","Ethics"], "₹4-7 LPA"),
            ("Hospital Administrator",       "Manage hospital operations",              ["Management","Healthcare Systems"], "₹5-9 LPA"),
        ],
        "finance": [
            ("Financial Analyst",            "Analyse financial data and trends",       ["Excel","Financial Modeling","Valuation"], "₹4-8 LPA"),
            ("Investment Banking Analyst",   "M&A advisory and deal structuring",       ["Financial Modeling","Excel","PPT"], "₹8-15 LPA"),
            ("Chartered Accountant",         "Audit, taxation, and compliance",         ["Tally","GST","Audit"], "₹6-12 LPA"),
            ("Risk Analyst",                 "Assess and mitigate financial risks",     ["Statistics","Risk Models","Excel"], "₹5-9 LPA"),
        ],
        "mechanical": [
            ("Design Engineer",              "CAD design of mechanical components",     ["AutoCAD","SolidWorks","Design"], "₹3-6 LPA"),
            ("Production Engineer",          "Oversee manufacturing processes",         ["Manufacturing","Quality","Process"], "₹3-5 LPA"),
            ("R&D Engineer",                 "Research and develop new products",       ["Innovation","Testing","Prototyping"], "₹4-8 LPA"),
            ("Quality Control Engineer",     "Ensure product quality standards",        ["QA","Testing","Six Sigma"], "₹3-5 LPA"),
        ],
        "law": [
            ("Junior Associate",             "Legal research and drafting",             ["Legal Research","Drafting","IPC"], "₹3-6 LPA"),
            ("Legal Analyst",                "Analyse contracts and legal documents",   ["Contract Law","Analysis","Research"], "₹4-7 LPA"),
            ("Compliance Officer",           "Ensure regulatory compliance",            ["Regulations","Documentation","Ethics"], "₹5-9 LPA"),
        ],
        "education": [
            ("Assistant Professor",          "Teach and conduct research",              ["Teaching","Research","Curriculum"], "₹30-60K/month"),
            ("Academic Counselor",           "Guide students in career planning",       ["Counseling","Communication","Psychology"], "₹3-5 LPA"),
            ("Curriculum Designer",          "Design educational content",              ["Curriculum","E-learning","Pedagogy"], "₹4-7 LPA"),
        ],
    }

    job_list = templates.get(domain_cat, templates.get("tech", []))
    jobs = []
    for i, (title, desc, req_skills, salary) in enumerate(job_list[:5]):
        company, url = employers[i % len(employers)] if employers else ("Top Company", "#")
        # Decision logic: calculate match using YOUR algorithm
        matched   = [s for s in skills if any(s.lower() in r.lower() or r.lower() in s.lower() for r in req_skills)]
        missing   = [r for r in req_skills if not any(r.lower() in s.lower() for s in skills)]
        match_pct = min(95, max(20, int(len(matched) / max(len(req_skills), 1) * 100)))
        jobs.append({
            "title":           title,
            "company":         company,
            "location":        "Hyderabad / Remote",
            "experience":      "Fresher / 0-2 years",
            "salary":          salary,
            "description":     desc,
            "required_skills": req_skills,
            "matched_skills":  matched,
            "missing_skills":  missing,
            "match":           f"{match_pct}%",
            "gap_advice":      f"You have {', '.join(matched[:2]) or 'foundational skills'}. Focus on {', '.join(missing[:2]) or 'building projects'}.",
            "source":          "local_logic",  # flag: generated by YOUR logic, not API
            "apply_url":       url,
        })
    print(f"  [B] Generated {len(jobs)} jobs from local decision logic (no API)")
    return jobs


def fetch_jobs_from_resume(analysis):
    domain = analysis.get("domain", "General")
    career = analysis.get("career_fit", ["Engineer"])
    skills = analysis.get("skills", [])
    any_key = JSEARCH_API_KEY or ADZUNA_APP_ID or HASDATA_API_KEY or SCRAPEOPS_API_KEY
    real_jobs = []
    groq_jobs = []
    jobs_lock = _threading.Lock()

    def get_real():
        if any_key:
            print("  [B] Fetching real jobs via RapidAPI (1 batch call)...")
            res = fetch_real_jobs_batch(domain, career, skills)
            if res:
                with jobs_lock:
                    real_jobs.extend(res)
                print(f"  [B] ✅ {len(res)} real jobs fetched")

    def get_groq():
        res = fetch_jobs_from_groq(analysis)
        if res:
            with jobs_lock:
                groq_jobs.extend(res)

    t1 = _threading.Thread(target=get_real, daemon=True)
    t2 = _threading.Thread(target=get_groq, daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Fallback: if API failed, use local decision logic
    if not groq_jobs:
        print("  [B] API unavailable — using local job generation logic")
        groq_jobs = generate_jobs_from_logic(analysis)
    combined  = real_jobs[:]
    seen_titles = {j.get("title","").lower() for j in combined}
    for job in groq_jobs:
        if job.get("title","").lower() not in seen_titles:
            combined.append(job)
            seen_titles.add(job.get("title","").lower())
        if len(combined) >= 15:
            break
    if AI_ENGINE_LOADED and combined:
        print("  [B] 🧠 Decision Engine ranking jobs...")
        candidate = {"skills": skills, "domain": domain, "career_fit": career}
        combined = rank_jobs_with_decisions(combined, candidate)
        print(f"  [B] ✅ Decision Engine ranked {len(combined)} jobs with explainable scores")
    else:
        combined.sort(
            key=lambda j: int(str(j.get("match","0%")).replace("%","").strip() or "0"),
            reverse=True
        )
    print(f"  [B] Final: {len(combined)} jobs ({len(real_jobs)} real + {len(combined)-len(real_jobs)} AI)")
    return combined[:15]

INDIA_STARTUPS = [
    ("Razorpay","https://razorpay.com/jobs","Bengaluru"),
    ("Freshworks","https://www.freshworks.com/company/careers","Bengaluru"),
    ("Zepto","https://www.zepto.team/jobs","Bengaluru"),
    ("Meesho","https://meesho.io/jobs","Bengaluru"),
    ("Cred","https://careers.cred.club","Bengaluru"),
    ("Darwinbox","https://darwinbox.com/careers","Bengaluru"),
    ("Unacademy","https://unacademy.com/careers","Bengaluru"),
    ("Scaler","https://www.scaler.com/careers","Bengaluru"),
    ("BrowserStack","https://www.browserstack.com/careers","Bengaluru"),
    ("Postman","https://www.postman.com/company/careers","Bengaluru"),
    ("CleverTap","https://clevertap.com/careers","Bengaluru"),
    ("Chargebee","https://www.chargebee.com/jobs","Bengaluru"),
    ("Zerodha","https://zerodha.com/careers","Mumbai"),
    ("Groww","https://groww.in/jobs","Mumbai"),
    ("Paytm","https://paytm.com/careers","Noida"),
    ("Zomato","https://www.zomato.com/careers","Gurugram"),
    ("Zoho","https://careers.zohocorp.com","Chennai"),
    ("Persistent","https://careers.persistent.com","Pune"),
]

DOMAIN_EMPLOYERS = {
    "physics": [("BARC","https://www.barc.gov.in/careers"),("ISRO","https://www.isro.gov.in/Careers.html"),("DRDO","https://www.drdo.gov.in/careers"),("TIFR","https://www.tifr.res.in/"),("NPCIL","https://npcil.nic.in"),("ONGC","https://ongcindia.com/careers"),("Bharat Electronics","https://bel-india.in/careers"),("CSIR Labs","https://www.csir.res.in/"),("Niramai","https://niramai.com/careers"),("Agnikul Cosmos","https://agnikul.in/careers"),("Pixxel","https://www.pixxel.space/careers"),("Skyroot","https://skyroot.in/careers"),("GalaxEye","https://www.galaxeye.space/careers"),],
    "chemistry": [("Dr. Reddy's Labs","https://careers.drreddys.com"),("Sun Pharma","https://www.sunpharma.com/careers"),("Cipla","https://www.cipla.com/careers"),("Biocon","https://www.biocon.com/careers"),("Aurobindo Pharma","https://www.aurobindo.com/careers"),("Divi's Lab","https://www.divislabs.com/careers"),("Aragen Life Sciences","https://www.aragen.com/careers"),("Syngene","https://www.syngeneintl.com/careers"),("Strides Pharma","https://www.stridespharma.com/careers"),],
    "biology": [("Biocon","https://www.biocon.com/careers"),("Serum Institute","https://www.seruminstitute.com/career.php"),("Apollo Hospitals","https://www.apollohospitals.com/careers"),("MedGenome","https://www.medgenome.com/careers"),("Niramai","https://niramai.com/careers"),("Tricog Health","https://tricog.com/careers"),("Qure.ai","https://qure.ai/careers"),("SigTuple","https://sigtuple.com/careers"),("ICMR","https://www.icmr.gov.in"),("Fortis Healthcare","https://www.fortishealthcare.com/careers"),],
    "finance": [("Zerodha","https://zerodha.com/careers"),("Groww","https://groww.in/jobs"),("Razorpay","https://razorpay.com/jobs"),("PhonePe","https://www.phonepe.com/careers"),("Paytm","https://paytm.com/careers"),("CRED","https://careers.cred.club"),("Smallcase","https://smallcase.com/careers"),("PolicyBazaar","https://www.policybazaar.com/careers"),("BankBazaar","https://www.bankbazaar.com/careers"),("Perfios","https://www.perfios.com/careers"),],
    "education": [("Scaler","https://www.scaler.com/careers"),("NxtWave","https://www.ccbp.in/careers"),("upGrad","https://careers.upgrad.com"),("Unacademy","https://unacademy.com/careers"),("Vedantu","https://www.vedantu.com/careers"),("Emeritus","https://emeritus.org/careers"),("Simplilearn","https://www.simplilearn.com/company/careers"),("Great Learning","https://www.mygreatlearning.com/careers"),("Coding Ninjas","https://www.codingninjas.com/careers"),],
    "mechanical": [("Ola Electric","https://olaelectric.com/careers"),("Ather Energy","https://www.atherenergy.com/careers"),("Tata Motors","https://www.tatamotors.com/careers"),("Mahindra","https://careers.mahindra.com"),("Bosch India","https://www.bosch.in/careers"),("Zetwerk","https://www.zetwerk.com/careers"),("BHEL","https://www.bhel.com/career"),("HAL","https://hal-india.co.in/Careers/pg_Careers.aspx"),],
    "civil": [("NoBroker","https://www.nobroker.in/careers"),("Housing.com","https://housing.com/careers"),("L&T Construction","https://www.lntecc.com/careers"),("DLF","https://www.dlf.in/careers"),("Godrej Properties","https://www.godrejproperties.com/careers"),("NHAI","https://nhai.gov.in/career"),("Afcons Infrastructure","https://www.afcons.com/careers"),],
    "electrical": [("Ola Electric","https://olaelectric.com/careers"),("Ather Energy","https://www.atherenergy.com/careers"),("NTPC","https://ntpccareers.net"),("Power Grid","https://www.powergridindia.com/career"),("ABB India","https://new.abb.com/in/careers"),("Siemens India","https://www.siemens.co.in/careers"),("Tata Power","https://www.tatapower.com/careers"),("Havells","https://www.havells.com/careers"),],
    "law": [("LegalDesk","https://legaldesk.com/careers"),("LawRato","https://lawrato.com/careers"),("Vakil Search","https://vakilsearch.com/careers"),("AZB Partners","https://www.azbpartners.com/careers"),("Khaitan & Co","https://www.khaitanco.com/careers"),("Trilegal","https://www.trilegal.com/careers"),("LawSikho","https://lawsikho.com/careers"),("Legistify","https://legistify.com/careers"),],
    "marketing": [("Zomato","https://www.zomato.com/careers"),("Swiggy","https://careers.swiggy.com"),("Meesho","https://meesho.io/jobs"),("Nykaa","https://www.nykaa.com/careers"),("Mamaearth","https://mamaearth.in/careers"),("boAt","https://www.boat-lifestyle.com/careers"),("Lenskart","https://www.lenskart.com/careers"),],
    "computer science": [("Razorpay","https://razorpay.com/jobs"),("Freshworks","https://www.freshworks.com/company/careers"),("BrowserStack","https://www.browserstack.com/careers"),("Postman","https://www.postman.com/company/careers"),("Chargebee","https://www.chargebee.com/jobs"),("Darwinbox","https://darwinbox.com/careers"),("Druva","https://www.druva.com/careers"),("Juspay","https://juspay.in/careers"),],
    "data science": [("Sigmoid","https://www.sigmoid.com/careers"),("Fractal Analytics","https://fractal.ai/careers"),("Mu Sigma","https://www.mu-sigma.com/careers"),("Atlan","https://atlan.com/careers"),("LatentView","https://www.latentview.com/careers"),("Tiger Analytics","https://www.tigeranalytics.com/careers"),("Tredence","https://tredence.com/careers"),("Quantiphi","https://quantiphi.com/careers"),],
    "artificial intelligence": [("Sarvam AI","https://www.sarvam.ai/careers"),("Krutrim","https://olakrutrim.com/careers"),("Mad Street Den","https://www.madstreetden.com/careers"),("Haptik","https://www.haptik.ai/careers"),("Yellow.ai","https://yellow.ai/careers"),("Qure.ai","https://qure.ai/careers"),("Quantiphi","https://quantiphi.com/careers"),("Fractal Analytics","https://fractal.ai/careers"),],
    "machine learning": [("Sarvam AI","https://www.sarvam.ai/careers"),("Krutrim","https://olakrutrim.com/careers"),("Razorpay","https://razorpay.com/jobs"),("Swiggy","https://careers.swiggy.com"),("Fractal Analytics","https://fractal.ai/careers"),("Quantiphi","https://quantiphi.com/careers"),("Mad Street Den","https://www.madstreetden.com/careers"),("Sigmoid","https://www.sigmoid.com/careers"),],
    "general": [("Razorpay","https://razorpay.com/jobs"),("Zepto","https://www.zepto.team/jobs"),("Meesho","https://meesho.io/jobs"),("CRED","https://careers.cred.club"),("Delhivery","https://www.delhivery.com/careers"),("TCS","https://www.tcs.com/careers"),("Infosys","https://www.infosys.com/careers"),("Wipro","https://careers.wipro.com"),("HCL","https://www.hcltech.com/careers"),("Accenture","https://www.accenture.com/in-en/careers"),],

    # ── ENGINEERING ──
    "mechanical": [("L&T Engineering","https://www.lntecc.com/careers"),("Tata Motors","https://careers.tatamotors.com"),("Mahindra","https://careers.mahindra.com"),("Bharat Forge","https://www.bharatforge.com/careers"),("DRDO","https://www.drdo.gov.in/careers"),("ISRO","https://www.isro.gov.in/Careers.html"),("HAL","https://hal-india.co.in/Careers"),("BHEL","https://www.bhel.com/career"),("Cummins India","https://www.cummins.com/careers"),("Atlas Copco","https://www.atlascopco.com/en-in/careers"),],
    "civil": [("L&T Construction","https://www.lntecc.com/careers"),("DLF","https://www.dlf.in/careers"),("NHAI","https://nhai.gov.in/careers"),("RITES","https://www.rites.com/web/index.php/careers"),("CPWD","https://cpwd.gov.in"),("Shapoorji Pallonji","https://www.shapoorjipallonji.com/careers"),("Afcons Infrastructure","https://www.afcons.com/careers"),("Gammon India","https://www.gammonindia.com"),("NBCC","https://nbccindia.com/careers"),("Simplex Infrastructure","https://www.simplexinfra.com"),],
    "electrical": [("NTPC","https://www.ntpc.co.in/careers"),("Power Grid","https://www.powergridindia.com/careers"),("BHEL","https://www.bhel.com/career"),("Siemens India","https://new.siemens.com/in/en/company/jobs.html"),("ABB India","https://global.abb/group/en/careers"),("Schneider Electric","https://www.se.com/in/en/about-us/careers"),("ONGC","https://ongcindia.com/careers"),("CIL","https://www.coalindia.in/careers"),("Tata Power","https://www.tatapower.com/careers"),("Adani Power","https://www.adanipower.com/careers"),],
    "electronics": [("Samsung R&D","https://research.samsung.com/sri-b"),("Qualcomm India","https://www.qualcomm.com/company/careers"),("Texas Instruments","https://careers.ti.com"),("Intel India","https://www.intel.com/content/www/us/en/jobs/locations/india.html"),("ISRO","https://www.isro.gov.in/Careers.html"),("BEL","https://bel-india.in/careers"),("DRDO","https://www.drdo.gov.in/careers"),("MediaTek India","https://www.mediatek.com/careers"),("Bosch India","https://www.bosch.in/careers"),("Analog Devices","https://www.analog.com/en/about-adi/careers.html"),],

    # ── MEDICAL & HEALTHCARE ──
    "medical": [("Apollo Hospitals","https://careers.apollohospitals.com"),("Fortis Healthcare","https://www.fortishealthcare.com/careers"),("AIIMS","https://www.aiims.edu"),("Manipal Hospitals","https://www.manipalhospitals.com/careers"),("Max Healthcare","https://www.maxhealthcare.in/careers"),("Narayana Health","https://www.narayanahealth.org/careers"),("PGIMER","https://pgimer.edu.in"),("Medanta","https://www.medanta.org/careers"),("Sun Pharma","https://www.sunpharma.com/careers"),("Dr Reddy","https://www.drreddys.com/careers"),],
    "nursing": [("Apollo Hospitals","https://careers.apollohospitals.com"),("Fortis Healthcare","https://www.fortishealthcare.com/careers"),("AIIMS Nursing","https://www.aiims.edu"),("Manipal Hospitals","https://www.manipalhospitals.com/careers"),("Christian Medical College","https://www.cmch-vellore.edu"),("Aster DM Healthcare","https://www.asterdmhealthcare.com/careers"),("Care Hospitals","https://www.carehospitals.com/careers"),("NIMHANS","https://nimhans.ac.in"),("Omega Healthcare","https://www.omegahealthcare.com/careers"),("Portea Medical","https://portea.com/careers"),],
    "pharmacy": [("Sun Pharma","https://www.sunpharma.com/careers"),("Dr Reddy's","https://www.drreddys.com/careers"),("Cipla","https://www.cipla.com/careers"),("Lupin","https://www.lupin.com/careers"),("Aurobindo Pharma","https://www.aurobindo.com/careers"),("Biocon","https://www.biocon.com/careers"),("Hetero Drugs","https://www.heterodrugs.com/careers"),("Divi's Laboratories","https://www.divislabs.com/careers"),("Granules India","https://www.granulesindia.com/careers"),("Laurus Labs","https://www.lauruslabs.com/careers"),],
    "biotechnology": [("Biocon","https://www.biocon.com/careers"),("Serum Institute","https://www.seruminstitute.com/careers.php"),("Bharat Biotech","https://www.bharatbiotech.com/careers"),("Piramal Healthcare","https://www.piramal.com/careers"),("Strides Pharma","https://www.strides.com/careers"),("Shantha Biotech","https://sanofi.com/careers"),("Nuziveedu Seeds","https://www.nuziveeduseeds.com"),("CSIR Labs","https://www.csir.res.in/"),("IITs Biotech Research","https://www.iit.ac.in"),("GVK Biosciences","https://www.gvkbio.com/careers"),],

    # ── COMMERCE & BUSINESS ──
    "finance": [("Deloitte India","https://www2.deloitte.com/in/en/careers.html"),("PwC India","https://www.pwc.in/careers.html"),("KPMG India","https://home.kpmg/in/en/home/careers.html"),("EY India","https://www.ey.com/en_in/careers"),("HDFC Bank","https://www.hdfcbank.com/careers"),("ICICI Bank","https://www.icicicareers.com"),("Axis Bank","https://www.axisbank.com/careers"),("Kotak Mahindra","https://www.kotak.com/en/careers.html"),("Goldman Sachs India","https://www.goldmansachs.com/careers/india"),("JP Morgan India","https://careers.jpmorgan.com/global/en/india"),],
    "marketing": [("HUL","https://www.hul.co.in/careers"),("P&G India","https://www.pg.com/en_IN/careers"),("Nestle India","https://www.nestle.in/careers"),("ITC","https://www.itcportal.com/careers"),("Myntra","https://www.myntra.com/careers"),("Nykaa","https://www.nykaa.com/careers"),("Marico","https://www.marico.com/careers"),("Godrej Consumer","https://www.godrejconsumerproducts.com/careers"),("Zomato Marketing","https://www.zomato.com/careers"),("OYO","https://www.oyorooms.com/careers"),],
    "hr": [("Infosys HR","https://www.infosys.com/careers"),("TCS HR","https://www.tcs.com/careers"),("Aon Hewitt","https://www.aon.com/india/careers"),("Mercer India","https://www.mercer.com/careers"),("Randstad India","https://www.randstad.in/careers"),("TeamLease","https://www.teamlease.com/careers"),("Adecco India","https://www.adecco.in/careers"),("Mphasis HR","https://careers.mphasis.com"),("KPMG People & Change","https://home.kpmg/in/en/home/careers.html"),("Deloitte HR","https://www2.deloitte.com/in/en/careers.html"),],
    "business": [("McKinsey India","https://www.mckinsey.com/in/careers"),("BCG India","https://www.bcg.com/careers/india"),("Bain India","https://www.bain.com/offices/new-delhi"),("Accenture Strategy","https://www.accenture.com/in-en/careers"),("Roland Berger","https://www.rolandberger.com/en/careers"),("KPMG Advisory","https://home.kpmg/in/en/home/careers.html"),("EY-Parthenon","https://www.ey.com/en_in/careers"),("Tata Strategic","https://www.tata.com/careers"),("IQVIA","https://www.iqvia.com/careers"),("Gartner India","https://www.gartner.com/en/careers"),],

    # ── ARTS & HUMANITIES ──
    "law": [("Cyril Amarchand Mangaldas","https://www.cyrilshroff.com/careers"),("Khaitan & Co","https://www.khaitanco.com/careers"),("AZB & Partners","https://www.azbpartners.com/careers"),("Trilegal","https://www.trilegal.com/careers"),("Shardul Amarchand","https://www.samlegal.in/careers"),("J Sagar Associates","https://www.jsalaw.com/careers"),("Luthra & Luthra","https://www.luthra.com/careers"),("NLSIU Legal Aid","https://www.nls.ac.in"),("Supreme Court Bar","https://www.scba.in"),("Nishith Desai Associates","https://www.nishithdesai.com/careers"),],
    "psychology": [("Nimhans","https://nimhans.ac.in/careers"),("Vandrevala Foundation","https://www.vandrevalafoundation.com/careers"),("iCall TISS","https://icallhelpline.org"),("Lissun","https://lissun.app/careers"),("YourDOST","https://yourdost.com/careers"),("Wysa","https://www.wysa.io/careers"),("Manastha","https://www.manastha.com"),("The Guidance Centre","https://www.tgcindia.com"),("Fortis Mental Health","https://www.fortishealthcare.com/careers"),("Apollo Psychology","https://careers.apollohospitals.com"),],
    "education": [("BYJU's","https://byjus.com/careers"),("Unacademy","https://unacademy.com/careers"),("upGrad","https://www.upgrad.com/careers"),("WhiteHat Jr","https://www.whitehatjr.com/careers"),("Vedantu","https://www.vedantu.com/careers"),("Testbook","https://testbook.com/careers"),("Toppr","https://www.toppr.com/careers"),("Allen Career","https://www.allen.ac.in/careers"),("Aakash Institute","https://www.aakash.ac.in/careers"),("Narayana Group","https://www.narayanagroup.com/careers"),],
    "journalism": [("Times of India","https://careers.timesgroup.com"),("NDTV","https://www.ndtv.com/careers"),("The Hindu","https://www.thehindu.com/careers"),("Indian Express","https://www.indianexpress.com"),("Hindustan Times","https://career.hindustantimes.com"),("ANI","https://aninews.in"),("PTI","https://www.ptinews.com"),("Republic TV","https://www.republicworld.com/careers"),("News18","https://www.news18.com"),("Bloomberg Quint","https://www.bloombergquint.com"),],

    # ── SCIENCES ──
    "physics": [("ISRO","https://www.isro.gov.in/Careers.html"),("BARC","https://www.barc.gov.in/careers"),("DRDO","https://www.drdo.gov.in/careers"),("TIFR","https://www.tifr.res.in/"),("NPCIL","https://npcil.nic.in"),("IUCAA","https://www.iucaa.in"),("PRL","https://www.prl.res.in/prl-eng/careers"),("ARIES","https://www.aries.res.in"),("IIT Research","https://www.iit.ac.in"),("CSIR NCL","https://www.ncl-india.org"),],
    "chemistry": [("CSIR Labs","https://www.csir.res.in/"),("Reliance Industries","https://careers.ril.com"),("Asian Paints","https://www.asianpaints.com/careers"),("Pidilite","https://www.pidilite.com/careers"),("SRF Limited","https://www.srf.com/careers"),("Aarti Industries","https://www.aartiindustries.com/careers"),("Tata Chemicals","https://www.tatachemicals.com/careers"),("UPL","https://www.upl-ltd.com/careers"),("GHCL","https://www.ghcl.co.in/careers"),("NOCIL","https://www.nocil.com"),],
    "biology": [("CSIR CCMB","https://www.ccmb.res.in/careers"),("DBT India","https://dbtindia.gov.in/careers"),("ICAR","https://icar.org.in/content/careers"),("Biocon","https://www.biocon.com/careers"),("Strand Life Sciences","https://www.strandls.com/careers"),("MedGenome","https://www.medgenome.com/careers"),("Theramex","https://www.theramex.com/careers"),("Krishna Institute","https://kims.com.in"),("Premas Biotech","https://premasbiotech.com"),("Ankura Hospital","https://www.ankurahospitals.com"),],
    "mathematics": [("ISRO","https://www.isro.gov.in/Careers.html"),("RBI","https://www.rbi.org.in/scripts/careers.aspx"),("LIC Actuarial","https://licindia.in/Bottom-Links/Careers"),("IIIT Research","https://www.iiit.ac.in"),("Quantitative Finance firms","https://www.optiver.com/working-at-optiver"),("IMSc","https://www.imsc.res.in"),("ISI Kolkata","https://www.isical.ac.in"),("CMI","https://www.cmi.ac.in"),("Fractal Analytics","https://fractal.ai/careers"),("Data Analytics firms","https://www.mu-sigma.com/careers"),],

    # ── DESIGN & ARCHITECTURE ──
    "architecture": [("Morphogenesis","https://www.morphogenesis.org/careers"),("Studio Lotus","https://studiolotus.in/careers"),("CP Kukreja","https://www.cpkukreja.com"),("Hafeez Contractor","https://www.hafeezcontractor.com"),("RSP India","https://www.rspindia.com/careers"),("L&T Construction","https://www.lntecc.com/careers"),("Jones Lang LaSalle","https://www.joneslanglasalle.co.in/careers"),("CBRE India","https://www.cbre.co.in/careers"),("Godrej Properties","https://www.godrejproperties.com/careers"),("DLF","https://www.dlf.in/careers"),],
    "design": [("Flipkart Design","https://www.flipkart.com/careers"),("Swiggy Design","https://careers.swiggy.com"),("Zomato Design","https://www.zomato.com/careers"),("Dunzo","https://www.dunzo.com/careers"),("PhonePe Design","https://careers.phonepe.com"),("Lollypop Design","https://lollypop.design/careers"),("Thought Over Design","https://www.thoughtoverdesign.com"),("Elephant Design","https://www.elephantdesign.com"),("Lowe Lintas","https://www.linteractive.in/careers"),("Ogilvy India","https://www.ogilvy.com/careers"),],

    # ── AGRICULTURE ──
    "agriculture": [("ICAR","https://icar.org.in/content/careers"),("FCI","https://www.fci.gov.in/recruitment.php"),("NABARD","https://www.nabard.org/recruitment.aspx"),("State Agriculture Dept","https://agricoop.nic.in"),("Mahyco","https://www.mahyco.com/careers"),("UPL","https://www.upl-ltd.com/careers"),("Rallis India","https://www.rallis.co.in/careers"),("BigHaat","https://www.bighaat.com/careers"),("AgroStar","https://www.agrostar.in/careers"),("Ninjacart","https://www.ninjacart.com/careers"),],
    "environment": [("TERI","https://www.teriin.org/careers"),("WWF India","https://www.wwfindia.org/careers"),("Grantham Foundation","https://www.grantham.org.uk"),("ERM India","https://www.erm.com/careers"),("CPCB","https://cpcb.nic.in"),("GIZ India","https://www.giz.de/en/worldwide/369.html"),("Climate Policy Initiative","https://climatepolicyinitiative.org/careers"),("Enviro Legal Defence Firm","https://www.eldf.in"),("AECOM India","https://www.aecom.com/careers"),("Sterlite Power","https://www.sterlitepower.com/careers"),],
}

def get_domain_category(domain_str):
    """Returns broad category for domain — tech, medical, engineering, etc."""
    d = domain_str.lower()
    for keyword, category in DOMAIN_CLASSIFIER.items():
        if keyword in d:
            return category
    # fallback word matching
    if any(w in d for w in ["software","programming","developer","coding","engineer"]):
        return "tech"
    if any(w in d for w in ["medical","doctor","hospital","clinical","health"]):
        return "medical"
    if any(w in d for w in ["mechanical","civil","electrical","chemical","aerospace"]):
        return "mechanical"
    if any(w in d for w in ["finance","accounting","banking","commerce","ca "]):
        return "finance"
    if any(w in d for w in ["law","legal","advocate","llb"]):
        return "law"
    if any(w in d for w in ["teaching","education","teacher","pedagogy"]):
        return "education"
    return "general"


def get_domain_employers(domain_str):
    d = domain_str.lower()
    for key in DOMAIN_EMPLOYERS:
        if key in d or d in key: return DOMAIN_EMPLOYERS[key]
    for key, employers in DOMAIN_EMPLOYERS.items():
        words = [w for w in key.split() if len(w) > 3]
        if any(word in d for word in words): return employers
    return DOMAIN_EMPLOYERS["general"]

def analyze_job_skill_gaps(candidate_skills, job_required_skills, job_title, company, domain):
    candidate_lower = {s.strip().lower() for s in candidate_skills}
    matched = []; missing = []
    for s in job_required_skills:
        s_clean = s.strip()
        if s_clean.lower() in candidate_lower or any(s_clean.lower() in c or c in s_clean.lower() for c in candidate_lower):
            matched.append(s_clean)
        else:
            missing.append(s_clean)
    match_pct = round(len(matched) / max(len(job_required_skills), 1) * 100)
    if not missing:
        matched_str = ", ".join(matched[:3]) if matched else "all skills"
        gap_advice = f"✅ Perfect match for {job_title} at {company}! You have {matched_str}. Apply immediately."
    elif len(missing) == 1:
        gap_advice = f"Only 1 gap for {job_title} at {company}: {missing[0]}. You already have {', '.join(matched[:3])}. Spend 1-2 weeks on a {missing[0]} project and you qualify."
    elif len(missing) <= 3:
        have_str   = ", ".join(matched[:3]) if matched else "core skills"
        need_str   = " and ".join(missing[:2])
        gap_advice = f"For {job_title} at {company} — you have {have_str}. Missing: {need_str}. Focus on these to close the gap."
    else:
        have_str   = ", ".join(matched[:2]) if matched else "some skills"
        need_str   = ", ".join(missing[:3])
        gap_advice = f"For {job_title} at {company} — you have {have_str} but need {need_str} ({len(missing)-3} more). Start with {missing[0]} as it's most in-demand."
    skill_resources = {"docker":"Docker official docs + Play with Docker (free)","kubernetes":"KillerKoda.com free K8s labs","aws":"AWS Free Tier + AWS Skill Builder","react":"React official docs + Scrimba React course","sql":"SQLZoo.net + Mode Analytics SQL tutorial","pytorch":"PyTorch.org tutorials (official, free)","tensorflow":"TensorFlow official tutorials","git":"learngitbranching.js.org (interactive)","mlops":"MLflow.org docs + Weights & Biases free tier","langchain":"python.langchain.com/docs (official)"}
    hints = []
    for sk in missing[:2]:
        for key, resource in skill_resources.items():
            if key in sk.lower(): hints.append(f"Learn {sk}: {resource}"); break
    if hints: gap_advice += " | " + " | ".join(hints)
    return {"matched_skills": matched[:8], "missing_skills": missing[:6], "match_pct": match_pct, "gap_advice": gap_advice}

def fetch_real_jobs_batch(domain, career, skills, location="India"):
    any_key = JSEARCH_API_KEY or ADZUNA_APP_ID or HASDATA_API_KEY or SCRAPEOPS_API_KEY
    if not any_key: return []
    role  = career[0] if career else domain
    query = f"{role} {domain} fresher India"
    jobs  = []
    if JSEARCH_API_KEY:
        try:
            resp = requests.get("https://jsearch.p.rapidapi.com/search",
                headers={"X-RapidAPI-Key": JSEARCH_API_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
                params={"query": query, "page": "1", "num_pages": "2", "date_posted": "week", "country": "in", "language": "en"},
                timeout=15)
            if resp.status_code == 200:
                for r in resp.json().get("data", [])[:15]:
                    url = r.get("job_apply_link") or r.get("job_google_link","")
                    if not url: continue
                    jobs.append({"title": r.get("job_title", role), "company": r.get("employer_name",""), "location": r.get("job_city") or r.get("job_state","") or location, "experience": "Fresher / Entry Level", "salary": "As per industry standards", "description": (r.get("job_description",""))[:400], "required_skills": skills[:6], "nice_to_have": [], "url": url, "naukri_url": f"https://www.naukri.com/{r.get('job_title','').lower().replace(' ','-')}-jobs", "linkedin_url": f"https://www.linkedin.com/jobs/search/?keywords={r.get('job_title','').replace(' ','%20')}&location=India&f_TPR=r2592000", "internshala_url": f"https://internshala.com/jobs/{r.get('job_title','').lower().replace(' ','-')}-jobs", "is_direct": True, "posted_at": r.get("job_posted_at_datetime_utc","")[:10], "source": r.get("job_publisher","Indeed"), "match": "0%"})
                print(f"  [JSearch Batch] ✅ {len(jobs)} real jobs fetched in 1 API call")
        except Exception as e:
            print(f"  [JSearch Batch] Error: {e}")
    return jobs[:15]

def make_job_url(title, company, location, domain):
    return {"apply_url": f"https://www.google.com/search?q={title.replace(' ','+')}+jobs+India&ibp=htl;jobs&tbs=qdr:m", "naukri_url": f"https://www.naukri.com/{title.lower().replace(' ','-')}-jobs-in-{location.lower().replace(' ','-')}", "linkedin_url": f"https://www.linkedin.com/jobs/search/?keywords={title.replace(' ','%20')}&location={location.replace(' ','%20')}%2C%20India&f_TPR=r604800&f_E=1%2C2", "internshala_url": f"https://internshala.com/jobs/{title.lower().replace(' ','-')}-jobs", "is_direct": False}

def fetch_jobs_from_groq(analysis):
    print("  [B] Generating rich job listings via Groq...")
    domain           = analysis.get("domain", "General")
    candidate_skills = analysis.get("skills", [])
    skills_str       = ", ".join(candidate_skills[:10])
    career           = safe_cell(analysis.get("career_fit", []))
    employers        = get_domain_employers(domain)
    domain_cat       = get_domain_category(domain)

    # Non-tech domains shouldn't get software/IT job recommendations
    is_tech = domain_cat in {"tech", "electronics", "mathematics", "biotechnology"}
    employer_list    = ", ".join(f"{name}" for name, _ in employers[:12])
    employer_urls    = {name: url for name, url in employers}
    all_jobs         = []
    careers_list     = analysis.get("career_fit", ["Engineer"])
    jobs_lock        = _threading.Lock()

    # FIX: Generate all 3 job batches in parallel for speed
    def fetch_job_batch(batch_num):
        cities     = ["Hyderabad","Bengaluru","Mumbai","Chennai","Pune","Delhi","Noida","Gurugram","Kolkata","Ahmedabad","Jaipur"]
        city_slice = ", ".join(cities[batch_num*3:(batch_num+1)*3 + 2])
        # Build domain-appropriate recruiter context
        recruiter_type = {
            "tech": "Indian tech recruiter",
            "medical": "Indian healthcare recruiter for hospitals and pharma",
            "mechanical": "Indian engineering recruiter for manufacturing and core sectors",
            "civil": "Indian construction and infrastructure recruiter",
            "electrical": "Indian power sector recruiter",
            "finance": "Indian finance and banking recruiter",
            "marketing": "Indian FMCG and digital marketing recruiter",
            "law": "Indian legal recruitment specialist",
            "education": "Indian education sector recruiter",
            "journalism": "Indian media and communications recruiter",
            "agriculture": "Indian agri-business recruiter",
        }.get(domain_cat, "Indian recruiter")

        prompt = f"""You are a {recruiter_type}. Generate exactly 5 realistic job postings as a JSON array.

CANDIDATE PROFILE: Domain={domain} | Candidate Skills={skills_str} | Target Roles={career}
USE COMPANIES FROM: {employer_list}
USE CITIES: {city_slice}

Return ONLY this JSON array (no explanation, no markdown):
[
  {{
    "title": "specific job title matching {domain}",
    "company": "company name from the list above",
    "location": "city from: {city_slice}",
    "experience": "Fresher / Entry Level",
    "salary": "₹4 LPA - ₹8 LPA",
    "description": "2 sentences about what this specific role does day-to-day.",
    "required_skills": ["role-specific skill 1","role-specific skill 2","role-specific skill 3","role-specific skill 4","role-specific skill 5"],
    "nice_to_have": ["advanced skill relevant to this role"],
    "match": "XX%"
  }}
]

CRITICAL RULES:
- required_skills must be ROLE-SPECIFIC for THAT job title — NOT copied from candidate profile
- Each of the 5 jobs must have DIFFERENT required_skills based on that specific role
- match% = honest % overlap between candidate skills and THIS job's required_skills
- Different company, city, and title for each job"""

        try:
            result = groq_only.call(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=2000
            )
            if not result:
                print(f"  [B] Batch {batch_num+1}: No response from API")
                return
            text = result.strip()
            # Clean markdown
            if "```" in text:
                text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
            # Fix trailing commas
            text = re.sub(r',\s*([}\]])', r'\1', text)
            # Extract JSON array
            s = text.find("["); e = text.rfind("]") + 1
            if s == -1 or e <= s:
                print(f"  [B] Batch {batch_num+1}: No JSON array found in response")
                print(f"  [B] Response preview: {text[:200]}")
                return
            batch = json.loads(text[s:e])
            if isinstance(batch, list) and len(batch) > 0:
                with jobs_lock:
                    all_jobs.extend(batch)
                print(f"  [B] Batch {batch_num+1}: {len(batch)} jobs")
            else:
                print(f"  [B] Batch {batch_num+1}: Empty or invalid list")
        except json.JSONDecodeError as ex:
            print(f"  [B] Batch {batch_num+1} JSON parse error: {ex}")
        except Exception as ex:
            print(f"  [B] Batch {batch_num+1} error: {ex}")

    # Run all 3 job batches in parallel — Ollama handles 3 parallel calls fine
    job_threads = [_threading.Thread(target=fetch_job_batch, args=(i,), daemon=True) for i in range(3)]
    for t in job_threads: t.start()
    for t in job_threads: t.join()
    print(f"  [B] ✅ {len(all_jobs)} jobs generated from 3 parallel batches")
    jobs = all_jobs
    if len(jobs) < 5:
        print(f"  [B] Groq returned only {len(jobs)} — using smart fallback")
        role_skills = {"ai": ["Python","PyTorch","TensorFlow","MLOps","Docker","REST APIs","SQL","Git"], "ml": ["Python","Scikit-learn","XGBoost","Feature Engineering","Pandas","MLflow","AWS","SQL"], "data": ["Python","SQL","Tableau","Power BI","Pandas","Statistics","Excel","BigQuery"], "backend": ["Python","FastAPI","PostgreSQL","Redis","Docker","Kubernetes","AWS","Git"], "default": ["Python","SQL","REST APIs","Git","Linux","Docker","Cloud","Problem Solving"]}
        d  = domain.lower()
        rk = "ai" if "artificial" in d or " ai" in d else "ml" if "machine" in d else "data" if "data" in d else "backend" if "computer" in d or "software" in d else "default"
        locs = ["Hyderabad","Bengaluru","Mumbai","Chennai","Pune","Delhi","Noida","Gurugram","Jaipur","Kolkata"]
        for i, (company, url) in enumerate(employers[:15]):
            role = careers_list[i % len(careers_list)] if careers_list else "Engineer"
            jobs.append({"title": role, "company": company, "location": locs[i % len(locs)], "experience": "Fresher / Entry Level" if i < 8 else "0-2 years", "salary": "₹4 LPA - ₹8 LPA" if i < 8 else "₹8 LPA - ₹15 LPA", "description": f"Join {company}'s {domain} team as a {role}.", "required_skills": role_skills[rk], "nice_to_have": ["Cloud experience"], "match": f"{max(25, 60 - i*4)}%"})
    for job in jobs:
        company  = job.get("company",""); title = job.get("title",""); location = job.get("location","India")
        if not job.get("url"):
            urls = make_job_url(title, company, location, domain); job["url"] = urls["apply_url"]
        if not job.get("naukri_url"):    job["naukri_url"]    = f"https://www.naukri.com/{title.lower().replace(' ','-')}-jobs-in-{location.lower().replace(' ','-')}"
        if not job.get("linkedin_url"):  job["linkedin_url"]  = f"https://www.linkedin.com/jobs/search/?keywords={title.replace(' ','%20')}&location={location.replace(' ','%20')}%2C%20India&f_TPR=r2592000"
        if not job.get("internshala_url"): job["internshala_url"] = f"https://internshala.com/jobs/{title.lower().replace(' ','-')}-jobs"
        if "is_direct" not in job: job["is_direct"] = False
        for emp_name, emp_url in employer_urls.items():
            if emp_name.lower() in company.lower() or company.lower() in emp_name.lower():
                job["career_page"] = emp_url; break
        required = job.get("required_skills", [])
        if required and candidate_skills:
            gap_data = analyze_job_skill_gaps(candidate_skills, required, title, company, domain)
            job["matched_skills"] = gap_data["matched_skills"]; job["missing_skills"] = gap_data["missing_skills"]
            job["gap_advice"]     = gap_data["gap_advice"]
            calc_pct = gap_data["match_pct"]
            try:
                raw_pct = str(job.get("match","0%")).replace("%","").strip()
                groq_pct = int(raw_pct) if raw_pct.isdigit() else 0
            except (ValueError, TypeError):
                groq_pct = 0
            job["match"] = f"{max(calc_pct, min(groq_pct, 95))}%"
        else:
            calc = calculate_match_percent(job.get("description","") + " " + title, candidate_skills)
            job["match"] = f"{max(calc, 20)}%"; job["matched_skills"] = []; job["missing_skills"] = []
            job["gap_advice"] = f"Review the job description and build 1-2 projects using the required skills for {title} at {company}."
    def safe_match(j):
        try:
            raw = str(j.get("match","0%")).replace("%","").strip()
            return int(raw) if raw.isdigit() else 0
        except:
            return 0
    jobs.sort(key=safe_match, reverse=True)
    print(f"  [B] ✅ {len(jobs)} rich jobs generated with skill gap analysis")
    return jobs[:15]

# ================= LEARNING RESOURCES =====================
def learning_resources_agent(analysis):
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
    return result

def get_fallback_questions(skill, count=20):
    base = FALLBACK_QUESTIONS["default"]
    return [{**q, "topic": skill} for q in base[:count]]

# ================= INTERVIEW QUESTIONS =====================
def questions_for_skill(skill, resume_context, career, domain, level):
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
3. Use their actual projects/tools/subjects to make questions concrete
3. Match their domain — never ask coding questions unless skill IS a coding language
4. Mix types: conceptual, applied, experiential, analytical

Return ONLY a JSON array, no markdown, no explanation:
[{{"q":"question text","answer":"concise answer","level":{level},"topic":"{skill}"}}]"""

    try:
        raw = groq_rotator.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=1500
        )
        if not raw:
            raise Exception("Empty response")

        # FIX: Clean up Ollama/Groq markdown wrapping
        raw = raw.strip()
        if "```" in raw:
            raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        # Fix trailing commas before parsing
        raw = re.sub(r',\s*([}\]])', r'\1', raw)

        s = raw.find("["); e = raw.rfind("]") + 1
        if s == -1 or e == 0:
            raise Exception("No JSON array")

        raw = raw[s:e]
        parsed = json.loads(raw)
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
            {"q": f"Explain the most important algorithm or technique in {skill}.", "answer": "Explain with example.", "level": level, "topic": skill},
            {"q": f"What challenges have you faced while working with {skill}?", "answer": "Be specific and honest.", "level": level, "topic": skill},
        ]

def generate_hr_aptitude_logical(resume_context, career, has_coding):
    coding_instruction = '"coding": [5 coding/DSA questions relevant to their tech stack]' if has_coding else '"coding": []'
    # Build domain-specific HR questions
    domain_cat = get_domain_category(domain) if "domain" in dir() else "general"
    domain_context = {
        "medical": "clinical scenarios, patient care ethics, medical emergencies",
        "law": "legal reasoning, case scenarios, client handling, ethics",
        "education": "classroom management, student engagement, teaching philosophy",
        "finance": "financial decision-making, client advisory, risk scenarios",
        "mechanical": "engineering projects, safety protocols, team coordination",
        "civil": "site management, project planning, construction challenges",
        "electrical": "power systems, safety, maintenance scenarios",
        "marketing": "campaign planning, customer insights, brand scenarios",
        "hr": "employee relations, conflict resolution, recruitment scenarios",
        "journalism": "editorial decisions, source ethics, deadline management",
        "psychology": "client scenarios, ethical dilemmas, therapeutic approaches",
        "architecture": "design projects, client briefs, construction coordination",
    }.get(domain_cat, "professional scenarios, teamwork, career goals")

    prompt = f"""Generate interview questions for a {career} candidate. Return ONLY valid JSON:
{{"aptitude":[10 questions with q/answer/level — use {domain_cat} relevant numerical problems],"logical":[10 logical reasoning questions with q/answer/level],"hr":[10 HR questions tailored to {career} covering {domain_context} with q/tip fields],{coding_instruction}}}
Level 1=easy 2=medium 3=hard. Make all questions relevant to {career} field specifically."""

    result = groq_json(prompt, temperature=0.3, max_tokens=4000)
    if result and isinstance(result, dict) and result.get("hr"):
        print(f"    ✓ HR/Aptitude/Logical: {len(result.get('hr',[]))} HR, {len(result.get('aptitude',[]))} aptitude, {len(result.get('logical',[]))} logical, {len(result.get('coding',[]))} coding")
        return result
    print("    ✗ HR/Aptitude failed — using built-in fallback")
    return {
        "aptitude": [
            {"q": "A train travels 300km in 5 hours. What is its speed?", "answer": "60 km/h", "level": 1},
            {"q": "If 8 workers finish a job in 6 days, how long for 12 workers?", "answer": "4 days", "level": 2},
            {"q": "What is 35% of 400?", "answer": "140", "level": 1},
            {"q": "Simple interest on Rs 8000 at 5% for 3 years?", "answer": "Rs 1200", "level": 1},
            {"q": "A:B = 3:4, B:C = 2:5. Find A:C.", "answer": "3:10", "level": 2},
        ],
        "logical": [
            {"q": "Odd one out: 3, 9, 15, 21, 25", "answer": "25 (not divisible by 3)", "level": 1},
            {"q": "Find missing: 2, 6, 18, 54, ?", "answer": "162 (x3 pattern)", "level": 1},
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

# ═══════════════════════════════════════════════════════════════
# MULTI-DOMAIN SUPPORT — ALL BACKGROUNDS
# ═══════════════════════════════════════════════════════════════

# Domain classifier — maps keywords to canonical domain categories
DOMAIN_CLASSIFIER = {
    # CS / Tech
    "artificial intelligence": "tech", "machine learning": "tech",
    "data science": "tech", "computer science": "tech",
    "software": "tech", "web development": "tech",
    "cybersecurity": "tech", "cloud computing": "tech",
    "data engineering": "tech", "nlp": "tech",

    # Engineering (non-CS)
    "mechanical": "mechanical", "civil": "civil",
    "electrical": "electrical", "electronics": "electronics",
    "chemical": "chemical", "aerospace": "aerospace",
    "automobile": "mechanical", "production": "mechanical",
    "structural": "civil", "construction": "civil",
    "eee": "electrical", "ece": "electronics",

    # Medical / Healthcare
    "medicine": "medical", "mbbs": "medical", "nursing": "nursing",
    "pharmacy": "pharmacy", "physiotherapy": "medical",
    "dentistry": "medical", "healthcare": "medical",
    "biomedical": "medical", "clinical": "medical",
    "pharmacology": "pharmacy", "bpharm": "pharmacy",

    # Commerce / Business
    "mba": "business", "finance": "finance", "accounting": "finance",
    "marketing": "marketing", "human resources": "hr",
    "commerce": "finance", "economics": "economics",
    "banking": "finance", "ca": "finance", "chartered": "finance",
    "business administration": "business", "management": "business",

    # Arts / Humanities
    "law": "law", "llb": "law", "legal": "law",
    "psychology": "psychology", "education": "education",
    "teaching": "education", "journalism": "journalism",
    "english": "humanities", "history": "humanities",
    "political science": "humanities", "sociology": "humanities",
    "media": "journalism", "communication": "journalism",

    # Sciences
    "physics": "physics", "chemistry": "chemistry",
    "biology": "biology", "biotechnology": "biotechnology",
    "microbiology": "biology", "biochemistry": "biology",
    "mathematics": "mathematics", "statistics": "mathematics",

    # Design / Architecture
    "architecture": "architecture", "interior design": "design",
    "fashion": "design", "graphic design": "design",
    "product design": "design",

    # Agriculture / Environment
    "agriculture": "agriculture", "environmental": "environment",
    "horticulture": "agriculture", "food technology": "food_tech",
}

DOMAIN_PRIORITY_SKILLS = {
    "artificial intelligence": ["machine learning","deep learning","generative ai","llms","nlp","computer vision","pytorch","tensorflow","transformers","langchain","hugging face","rag","agentic ai","faiss","mlops","semantic search","reinforcement learning"],
    "machine learning": ["machine learning","deep learning","pytorch","tensorflow","scikit-learn","xgboost","feature engineering","mlops","model deployment","pandas","numpy"],
    "data science": ["data science","machine learning","statistics","pandas","numpy","sql","tableau","power bi","data visualization","feature engineering","python"],
    "computer vision": ["computer vision","opencv","cnns","pytorch","tensorflow","image processing","object detection","deep learning","yolo","image segmentation"],
    "nlp": ["nlp","transformers","bert","gpt","langchain","hugging face","spacy","text classification","named entity recognition","sentiment analysis"],
    "computer science": ["data structures","algorithms","system design","databases","operating systems","computer networks","software engineering","design patterns","api development"],
    "web development": ["react","node.js","javascript","html","css","rest apis","databases","django","flask","fastapi","typescript","mongodb","postgresql"],
    "backend": ["python","fastapi","django","postgresql","redis","docker","kubernetes","aws","rest apis","microservices","system design","sql"],
    "data engineering": ["apache spark","kafka","airflow","sql","python","hadoop","etl","data pipelines","aws","azure","databricks","bigquery"],
    "devops": ["docker","kubernetes","ci/cd","jenkins","terraform","aws","azure","linux","bash","ansible","monitoring","git"],

    # ── ENGINEERING (Non-CS) ──
    "mechanical": ["thermodynamics","fluid mechanics","machine design","manufacturing","autocad","solidworks","ansys","catia","heat transfer","materials science","cnc","robotics","finite element analysis","quality control","lean manufacturing","six sigma"],
    "civil": ["structural analysis","autocad","staad pro","revit","concrete design","surveying","geotechnical","water resources","construction management","estimation","urban planning","rcc design","bim","project management","irrigation"],
    "electrical": ["power systems","circuit analysis","control systems","electrical machines","plc","scada","power electronics","transformers","protection systems","matlab","simulink","renewable energy","motor drives","switchgear","load flow"],
    "electronics": ["vlsi","embedded systems","signal processing","microcontrollers","arduino","fpga","communication systems","rf engineering","iot","pcb design","verilog","arm","sensor integration","analog circuits","digital design"],
    "chemical": ["process design","thermodynamics","chemical reaction engineering","mass transfer","heat transfer","process simulation","aspen plus","safety engineering","polymer chemistry","catalysis","separation processes","plant design"],
    "aerospace": ["aerodynamics","flight mechanics","propulsion","structural mechanics","matlab","cfd","spacecraft design","avionics","composite materials","control systems","orbital mechanics","rocket propulsion"],

    # ── MEDICAL & HEALTHCARE ──
    "medical": ["anatomy","physiology","pathology","pharmacology","clinical examination","diagnostics","patient care","surgery","internal medicine","pediatrics","medical ethics","evidence-based medicine","ecg interpretation","radiology"],
    "nursing": ["patient assessment","vital signs","medication administration","wound care","iv therapy","infection control","clinical documentation","patient education","emergency care","palliative care","nursing ethics","bls","acls"],
    "pharmacy": ["pharmacology","drug interactions","dispensing","clinical pharmacy","pharmaceutical calculations","drug regulatory affairs","hospital pharmacy","compounding","pharmacokinetics","medication therapy management"],
    "biotechnology": ["molecular biology","genetic engineering","pcr","cell culture","bioinformatics","protein expression","crispr","fermentation","immunology","western blot","elisa","genomics","drug discovery","bioprocess engineering"],

    # ── COMMERCE & BUSINESS ──
    "finance": ["financial analysis","valuation","financial modeling","excel","accounting","tally","taxation","audit","gst","balance sheet","income statement","investment analysis","risk management","banking operations","ca ipcc"],
    "marketing": ["digital marketing","seo","social media marketing","market research","brand management","consumer behavior","advertising","crm","google analytics","content marketing","email marketing","sales strategy","product launch"],
    "hr": ["recruitment","talent acquisition","employee relations","performance management","payroll","hris","labor law","training development","organizational behavior","compensation","succession planning","hr analytics","conflict resolution"],
    "business": ["business strategy","operations management","supply chain","project management","business analytics","entrepreneurship","financial planning","stakeholder management","business development","consulting","lean startup","bsc"],
    "economics": ["microeconomics","macroeconomics","econometrics","economic policy","game theory","development economics","international trade","monetary policy","statistical analysis","economic research","public finance"],

    # ── ARTS & HUMANITIES ──
    "law": ["contract law","constitutional law","criminal law","civil procedure","legal research","ipc","crpc","evidence act","corporate law","intellectual property","arbitration","legal drafting","negotiation","tort law","family law"],
    "psychology": ["clinical assessment","counseling","cognitive behavioral therapy","psychological testing","research methods","abnormal psychology","developmental psychology","organizational psychology","mental health","psychotherapy","behavior analysis"],
    "education": ["curriculum design","pedagogy","classroom management","lesson planning","educational psychology","assessment design","e-learning","student counseling","special education","learning outcomes","differentiated instruction"],
    "journalism": ["news writing","investigative journalism","media ethics","digital journalism","photojournalism","video production","social media","content strategy","public relations","editing","broadcast journalism","fact-checking"],

    # ── SCIENCES ──
    "physics": ["quantum mechanics","electromagnetism","thermodynamics","optics","nuclear physics","solid state physics","matlab","research methodology","laboratory techniques","mathematical physics","computational physics"],
    "chemistry": ["organic chemistry","inorganic chemistry","analytical chemistry","physical chemistry","spectroscopy","chromatography","laboratory skills","chemical safety","research methodology","green chemistry","synthesis"],
    "biology": ["genetics","microbiology","ecology","biochemistry","cell biology","evolution","molecular biology","taxonomy","research methodology","laboratory techniques","bioinformatics","immunology"],
    "mathematics": ["calculus","linear algebra","differential equations","probability","statistics","numerical methods","discrete mathematics","mathematical modeling","optimization","real analysis","complex analysis"],

    # ── DESIGN & ARCHITECTURE ──
    "architecture": ["architectural design","autocad","revit","sketchup","3ds max","urban planning","building codes","structural systems","environmental design","construction technology","landscape design","interior design","bim"],
    "design": ["ui/ux design","figma","adobe creative suite","graphic design","typography","color theory","user research","prototyping","branding","motion graphics","illustration","product design","design thinking"],

    # ── AGRICULTURE & ENVIRONMENT ──
    "agriculture": ["agronomy","soil science","crop production","plant pathology","agricultural economics","irrigation","precision farming","pest management","food science","horticulture","agricultural machinery","farm management"],
    "environment": ["environmental impact assessment","gis","remote sensing","water quality","pollution control","ecology","sustainability","waste management","environmental law","carbon footprint","climate change","biodiversity"],
    "food_tech": ["food processing","food safety","haccp","quality control","food microbiology","packaging","nutrition","food chemistry","sensory evaluation","food regulations","fermentation technology"],
}

GENERIC_SKILLS = {"python","java","c++","javascript","sql","git","linux","r programming","matlab","html","css","bash","shell"}

def select_interview_skills(raw_skills, domain, num_skills=3):
    domain_lower = domain.lower()
    priority_list = []
    for key, skills in DOMAIN_PRIORITY_SKILLS.items():
        if key in domain_lower or domain_lower in key:
            priority_list = skills; break
    if not priority_list:
        for key, skills in DOMAIN_PRIORITY_SKILLS.items():
            words = [w for w in key.split() if len(w) > 3]
            if any(word in domain_lower for word in words):
                priority_list = skills; break
    priority = []; secondary = []; generic = []
    for skill in raw_skills:
        skill_lower = skill.lower().strip()
        if skill_lower in priority_list or any(p in skill_lower for p in priority_list): priority.append(skill)
        elif skill_lower in GENERIC_SKILLS: generic.append(skill)
        else: secondary.append(skill)
    combined = priority + secondary + generic
    selected = combined[:num_skills]
    if len(priority) > 0 and all(s in GENERIC_SKILLS for s in [x.lower() for x in selected]):
        selected = (priority + secondary)[:num_skills]
    print(f"  [D] Priority skills: {priority[:5]} | Selected: {selected}")
    return selected if selected else raw_skills[:num_skills]

def generate_interview_questions(analysis):
    domain     = analysis.get("domain", "General")
    raw_skills = analysis.get("skills", [])
    career     = safe_cell(analysis.get("career_fit", []))
    education  = analysis.get("education", "")
    projects   = analysis.get("projects", [])
    experience = analysis.get("experience_context", "")
    strengths  = analysis.get("strengths", "")

    resume_context = f"""Domain: {domain}
Education: {education}
Skills: {", ".join(raw_skills[:15])}
Career Target: {career}
Projects: {"; ".join(projects[:4]) if projects else "Not specified"}
Experience: {experience}
Strengths: {strengths}"""

    print(f"  [D] Domain: {domain} | Education: {education[:60]}")
    print(f"  [D] Skills extracted: {raw_skills[:8]}")

    # Filter out any education items that leaked into skills
    education_kw = {'b.tech','m.tech','btech','mtech','intermediate','mpc','bipc','10th','12th',
                    'school','college','university','cgpa','percentage','b.sc','m.sc','bca','mca',
                    'secondary','hsc','ssc','pursuing','cbse','icse'}
    raw_skills = [s for s in raw_skills if not any(kw in s.lower() for kw in education_kw)]

    if not raw_skills:
        print("  [D] No valid skills — inferring from domain...")
        infer_prompt = f"""Candidate background: {resume_context}
List 4-5 specific TECHNICAL topics to interview them about (match their actual field, not their education).
Return ONLY a JSON array of strings like ["Machine Learning", "Python", "Data Analysis"]"""
        try:
            raw = groq_rotator.call(messages=[{"role": "user", "content": infer_prompt}], temperature=0.3, max_tokens=150)
            if raw:
                s2 = raw.find("["); e2 = raw.rfind("]") + 1
                if s2 != -1: raw_skills = json.loads(raw[s2:e2]); print(f"  [D] Inferred: {raw_skills}")
        except Exception as ex:
            print(f"  [D] Inference failed: {ex}")
        if not raw_skills:
            # Use domain to pick sensible defaults
            domain_defaults = {
                "artificial intelligence": ["Machine Learning","Deep Learning","Python"],
                "machine learning": ["Machine Learning","Python","Statistics"],
                "data science": ["Python","SQL","Machine Learning"],
                "computer science": ["Data Structures","Algorithms","Python"],
                "web development": ["HTML","CSS","JavaScript"],
            }
            d = domain.lower()
            for key, defaults in domain_defaults.items():
                if key in d or any(w in d for w in key.split()):
                    raw_skills = defaults; break
            if not raw_skills:
                raw_skills = [domain, "Problem Solving", "Domain Knowledge"]
        print(f"  [D] Using inferred skills: {raw_skills}")

    coding_kw = {"python","java","c++","javascript","sql","r programming","matlab","coding","programming","software","algorithm","typescript","scala","rust","go","kotlin","swift","c#","ruby","php","bash","shell"}
    resume_lower = (education + " " + domain + " " + " ".join(raw_skills)).lower()
    domain_cat   = get_domain_category(domain)
    tech_domains = {"tech", "electronics", "mathematics", "biotechnology", "food_tech"}
    has_coding   = (domain_cat in tech_domains) and any(kw in resume_lower for kw in coding_kw)
    print(f"  [D] Has coding: {has_coding} | Domain: {domain} | Category: {domain_cat}")

    skills_to_use = select_interview_skills(raw_skills, domain, num_skills=3)
    print(f"  [D] Generating questions for: {skills_to_use} (3 calls instead of 9)")

    all_technical = []

    def fetch_skill_all_levels(skill):
        """Generate L1+L2+L3 questions for a skill in ONE API call — 3× faster for Ollama."""
        prompt = f"""Expert interviewer. Generate 30 interview questions about: {skill}
CANDIDATE: {resume_context}
Field: {domain} | Role: {career}

Generate EXACTLY 21 questions: 7 beginner (level 1), 7 intermediate (level 2), 7 advanced (level 3).
Each must be specific to "{skill}" for this candidate's background.
Return ONLY a JSON array, no markdown:
[{{"q":"question","answer":"concise answer","level":1,"topic":"{skill}"}},...]"""

        try:
            raw = groq_rotator.call(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=3000
            )
            if not raw: raise Exception("Empty response")
            raw = raw.strip()
            if "```" in raw: raw = re.sub(r"```(?:json)?","",raw).strip().rstrip("`").strip()
            raw = re.sub(r',\s*([}}\]])', r'\1', raw)
            s = raw.find("["); e = raw.rfind("]") + 1
            if s == -1: raise Exception("No JSON array")
            try:
                parsed = json.loads(raw[s:e])
            except json.JSONDecodeError:
                raw_clean = re.sub(r'[\\x00-\\x1f]', ' ', raw[s:e])
                raw_clean = re.sub(r'\\\\(?!["\\\\/bfnrtu])', '', raw_clean)
                parsed = json.loads(raw_clean)
            if not isinstance(parsed, list) or len(parsed) == 0:
                raise Exception("Empty list")
            for q in parsed:
                q["topic"] = skill
            print(f"    ✓ [{domain}] {skill} all levels: {len(parsed)} questions")
            return parsed
        except Exception as err:
            print(f"    ✗ {skill} all levels failed ({err}) — using per-level fallback")
            # Fallback: generate each level separately
            result = []
            for level in [1, 2, 3]:
                result.extend(questions_for_skill(skill, resume_context, career, domain, level))
            return result

    # 3 skills × 1 call each = 3 total Ollama calls (was 9)
    # Run in parallel — 3 parallel calls Ollama handles fine
    skill_results = {}
    lock = _threading.Lock()

    def fetch_one_skill(skill):
        qs = fetch_skill_all_levels(skill)
        with lock:
            skill_results[skill] = qs

    threads = [_threading.Thread(target=fetch_one_skill, args=(s,), daemon=True) for s in skills_to_use]
    for t in threads: t.start()
    for t in threads: t.join()

    for skill in skills_to_use:
        all_technical.extend(skill_results.get(skill, []))

    print("  [D] Generating HR/aptitude/logical...")
    common = generate_hr_aptitude_logical(resume_context, career, has_coding)

    result = {
        "technical": all_technical,
        "aptitude":  common.get("aptitude", []),
        "logical":   common.get("logical", []),
        "hr":        common.get("hr", []),
        "coding":    common.get("coding", [])
    }
    print(f"  [D] ✅ Done: {len(all_technical)} technical, {len(result['aptitude'])} aptitude, {len(result['hr'])} HR, {len(result['coding'])} coding")
    return result

# ================= AGI FEEDBACK =====================
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
    data       = request.json
    question   = data.get("question", "")
    answer     = data.get("answer", "").strip()
    expected   = data.get("expected_answer", "")
    topic      = data.get("topic", "General")
    level      = data.get("level", 1)
    domain     = data.get("domain", "General")
    career     = data.get("career", "Professional")
    session_id = data.get("session_id", "")

    profile = None
    if AI_ENGINE_LOADED and session_id:
        session = INTERVIEW_SESSIONS.get(session_id, {})
        profile = get_or_create_profile(session_id, session.get("name","Candidate"), domain, session.get("skills",[]))

    if len(answer) < 8:
        # Build a meaningful hint using the actual question text
        question_preview = question[:120] if question else ""
        if question_preview:
            hint = f"For this question: '{question_preview}...' — give a clear definition, explain the concept with an example from your projects, and mention why it matters in {domain}."
        else:
            hint = f"A strong answer clearly defines the concept, explains how it works in practice, and gives a real example from your own projects or coursework in {domain}."
        return jsonify({"score": 0, "grade": "F", "correct": False,
            "feedback": "No answer was provided. Please attempt the question.",
            "what_was_right": "Nothing yet — but attempting is the first step.",
            "what_was_wrong": "Answer was blank or too short to evaluate.",
            "improvement": "Write at least 2-3 sentences explaining your understanding of the concept.",
            "model_answer_hint": hint,
            "encouragement": "Every expert was once a beginner — give it a genuine try!",
            "confidence_impact": "negative"})

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
{{"score": <integer 0-10>, "grade": "<A/B/C/D/F>", "correct": <true if score >= 6>, "feedback": "2-3 sentences of specific, kind, constructive feedback referencing what they actually said", "what_was_right": "Specific things the candidate got right", "what_was_wrong": "Specific gaps or misconceptions in their answer", "improvement": "One concrete, actionable tip to improve this answer", "model_answer_hint": "A specific 2-3 sentence model answer showing exactly what facts, concepts, and examples a perfect answer would include — be concrete, not vague", "encouragement": "One genuinely motivating sentence tailored to their domain/level", "confidence_impact": "<positive/neutral/negative>"}}"""

    result = groq_json(prompt, temperature=0.2, max_tokens=600)
    if not result:
        if AI_ENGINE_LOADED:
            print(f"  [Eval] Groq unavailable — Local Evaluator handling {topic}")
            result = local_evaluate_answer(question, answer, topic, level, domain)
        else:
            length = len(answer.split()); score = min(7, max(3, length // 8)); grade = "B" if score >= 7 else "C" if score >= 5 else "D"
            result = {"score": score, "grade": grade, "correct": score >= 6, "feedback": "Answer received. Add more detail for higher scores.", "what_was_right": "You attempted the question.", "what_was_wrong": "Could not fully evaluate.", "improvement": "Add concrete examples.", "model_answer_hint": f"Define {topic} clearly and give an example.", "encouragement": "Keep practising!", "confidence_impact": "neutral"}

    result["score"] = max(0, min(10, int(result.get("score", 5))))
    if profile is not None:
        try: profile.record_answer(topic, result["score"])
        except Exception: pass
    return jsonify(result)

# ================= SESSION ROUTES =====================
@app.route("/create_session", methods=["POST"])
def create_session():
    data = request.json; session_id = str(uuid.uuid4())
    INTERVIEW_SESSIONS[session_id] = data
    return jsonify({"session_id": session_id})

@app.route("/session/<session_id>", methods=["GET"])
def get_session(session_id):
    session = INTERVIEW_SESSIONS.get(session_id)
    if not session: return jsonify({"error": "Session not found"}), 404
    return jsonify(session)

@app.route("/interview/<session_id>")
def interview_page(session_id):
    return send_from_directory("interview_app", "index.html")

# ================= MONGODB =====================
_mongo_client = None; _mongo_db = None; _mongo_col = None

def init_db():
    global _mongo_client, _mongo_db, _mongo_col
    try:
        import certifi
        _mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000, tls=True, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=False)
        _mongo_client.server_info()
        _mongo_db  = _mongo_client["agi_career"]
        _mongo_col = _mongo_db["candidates"]
        _mongo_col.create_index("email", unique=True, sparse=True)
        print("  [DB] ✅ MongoDB connected")
    except Exception as e:
        print(f"  [DB] ❌ MongoDB connection failed: {e}"); _mongo_col = None

def get_col():
    global _mongo_col
    if _mongo_col is None: init_db()
    return _mongo_col

def get_existing_emails():
    try:
        col = get_col()
        if col is None: return set()
        return {d["email"].strip().lower() for d in col.find({"email":{"$exists":True}},{"email":1})}
    except Exception as e: print(f"  [DB] Email fetch error: {e}"); return set()

def ensure_table_exists(): return get_col() is not None

def save_to_sheet(details, analysis, jobs, resources, feedback, interview_link, session_id=""):
    name  = details.get("name", "Unknown"); email = details.get("email", "").strip().lower()
    print(f"  [DB] Saving: {name}")
    top_job = jobs[0] if jobs else {}
    doc = {"name": safe_cell(name), "email": email, "phone": safe_cell(details.get("phone","")), "education": safe_cell(details.get("education","")), "cgpa": safe_cell(details.get("cgpa","")), "domain": safe_cell(analysis.get("domain","")), "skills": safe_cell(analysis.get("skills",[])), "career_fit": safe_cell(analysis.get("career_fit",[])), "confidence": safe_cell(analysis.get("confidence_level","Medium")), "strengths": safe_cell(analysis.get("strengths","")), "weaknesses": safe_cell(analysis.get("weaknesses","")), "skill_gaps": safe_cell(analysis.get("skill_gaps","")), "top_jobs": " | ".join(f"{j.get('title','')} @ {j.get('company','')} [{j.get('match','?')}]" for j in jobs[:5]), "best_title": safe_cell(top_job.get("title","")), "best_company": safe_cell(top_job.get("company","")), "location": safe_cell(top_job.get("location","")), "match_pct": safe_cell(top_job.get("match","0%")), "apply_url": safe_cell(top_job.get("url","")), "books": safe_cell(resources.get("books","")), "courses": safe_cell(resources.get("courses","")), "youtube": safe_cell(resources.get("youtube","")), "learning_path": safe_cell(resources.get("learning_path","")), "agi_feedback": str(feedback or "")[:2000], "interview_link": interview_link, "status": "New", "processed_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    try:
        col = get_col()
        if col is not None:
            col.update_one({"email": email} if email else {"interview_link": interview_link}, {"$set": doc}, upsert=True)
            print(f"  [DB] ✅ Saved to MongoDB: {name}")
        else: print("  [DB] ⚠️  MongoDB not connected — data not saved")
    except Exception as e: print(f"  [DB] ❌ Save failed: {e}")
    try: sync_to_google_sheet(details, analysis, jobs, resources, feedback, interview_link, session_id)
    except Exception as e: print(f"  [Email] Error: {e}")

def send_candidate_email(to_email, name, report_link, interview_link):
    if not EMAIL_ENABLED or not to_email: return
    try:
        import smtplib; from email.mime.multipart import MIMEMultipart; from email.mime.text import MIMEText
        subject = EMAIL_SUBJECT.format(name=name)
        body = f"""<html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px;"><div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;"><div style="background:linear-gradient(135deg,#6c63ff,#00d4aa);padding:32px;text-align:center;"><h1 style="color:#fff;margin:0;">Your AGI Career Report is Ready!</h1><p style="color:rgba(255,255,255,0.85);margin-top:8px;">Hello <strong>{name}</strong></p></div><div style="padding:32px;"><a href="{report_link}" style="display:block;background:#6c63ff;color:#fff;padding:14px;border-radius:8px;text-decoration:none;font-weight:bold;text-align:center;margin-bottom:12px;">View Career Report</a><a href="{interview_link}" style="display:block;background:#00d4aa;color:#111;padding:14px;border-radius:8px;text-decoration:none;font-weight:bold;text-align:center;">Start Mock Interview</a></div></div></body></html>"""
        msg = MIMEMultipart("alternative"); msg["From"] = EMAIL_SENDER; msg["To"] = to_email; msg["Subject"] = subject; msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD); server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        print(f"  [Email] ✅ Sent to {to_email}")
    except Exception as e: print(f"  [Email] ❌ {to_email}: {e}")

def sync_to_google_sheet(details, analysis, jobs, resources, feedback, interview_link, session_id):
    report_link = f"{BASE_URL}/report/{session_id}"
    send_candidate_email(details.get("email",""), details.get("name",""), report_link, interview_link)
    print(f"  [Sync] ✅ Report: {report_link}")

@app.route("/candidates", methods=["GET"])
def get_candidates():
    try:
        col  = get_col(); rows = list(col.find({}, {"_id": 0}).sort("processed_at", -1)) if col else []
        return jsonify({"total": len(rows), "candidates": rows})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/candidates/export", methods=["GET"])
def export_candidates():
    import csv, io
    try:
        col  = get_col(); rows = list(col.find({}, {"_id": 0}).sort("processed_at", -1)) if col else []
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
        from flask import Response
        return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=candidates.csv"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/db-test", methods=["GET"])
def db_test():
    col = get_col()
    if col is None: return jsonify({"status": "FAILED", "error": "MongoDB not connected"}), 500
    try:
        col.update_one({"email": "test@test.com"}, {"$set": {"name":"TEST","email":"test@test.com","domain":"Test","processed_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}}, upsert=True)
        count = col.count_documents({})
        return jsonify({"status": "✅ MongoDB working", "total_candidates": count, "view_all": f"{BASE_URL}/candidates", "export_csv": f"{BASE_URL}/candidates/export"})
    except Exception as e: return jsonify({"status": "FAILED", "error": str(e)}), 500

# ================= UPLOAD RESUME =====================
@app.route("/uploadresume", methods=["POST"])
def upload_resume():
    import threading
    from werkzeug.utils import secure_filename

    # ── SECURITY: File validation ──
    if "resume" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["resume"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Extension whitelist — only PDF and DOCX allowed
    ALLOWED_EXTENSIONS = {".pdf", ".docx"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Only PDF and DOCX files allowed. Got: {ext}"}), 400

    # File size limit — max 5MB
    file_bytes = file.read()
    MAX_SIZE = 5 * 1024 * 1024  # 5MB
    if len(file_bytes) > MAX_SIZE:
        return jsonify({"error": "File too large. Maximum size is 5MB."}), 400

    # Sanitize filename
    filename = secure_filename(file.filename)
    print("\n=== New resume received ===")
    print("File:", filename, f"| Size: {len(file_bytes)//1024}KB")
    print("[1/2] Extracting PDF text...")
    import io
    resume_text = extract_text_from_pdf(io.BytesIO(file_bytes))
    resume_text = sanitize_resume_text(resume_text)  # Security: prevent prompt injection
    print("  Text length:", len(resume_text), "chars")
    print("[2/2] Extracting basic details...")
    details = extract_basic_details(resume_text, filename)
    print("  Name:", details['name'])
    session_id     = str(uuid.uuid4())
    interview_link = BASE_URL + "/interview/" + session_id
    INTERVIEW_SESSIONS[session_id] = {
        "name":       details["name"],
        "status":     "processing",
        "questions":  {},
        "career_fit": [],
        "skills":     [],
        "uploaded_at": time.time(),  # for cleanup
    }
    # file_bytes processed in memory — no temp files written to disk

    def background_processing():
        print(f"\n[BG] Starting parallel processing for {details['name']}...")
        analysis_result  = {}; jobs_result = [{}]; resources_result = {}; questions_result = {}; feedback_result = [""]

        def run_analysis():
            print("  [BG-A] AI analysis...")
            analysis_result.update(ai_analyze(resume_text))
            print("  [BG-A] Done.")

        # Step 0: Run analysis synchronously (takes ~3s) as jobs/questions depend on it
        run_analysis()
        
        # UI speed optimisation: Immediately push details to session so report page populates
        INTERVIEW_SESSIONS[session_id].update({
            "career_fit":   analysis_result.get("career_fit", []),
            "skills":       analysis_result.get("skills", []),
            "domain":       analysis_result.get("domain", "General"),
            "education":    analysis_result.get("education", ""),
            "strengths":    analysis_result.get("strengths", ""),
            "weaknesses":   analysis_result.get("weaknesses", ""),
            "skill_gaps":   analysis_result.get("skill_gaps", ""),
            "achievements": analysis_result.get("achievements", "")
        })

        def run_jobs():
            print("  [BG-B] Fetching jobs...")
            jobs_result.clear(); jobs_result.extend(fetch_jobs_from_resume(analysis_result))
            INTERVIEW_SESSIONS[session_id]["jobs"] = list(jobs_result)
            print(f"  [BG-B] Done. {len(jobs_result)} jobs.")

        def run_resources():
            print("  [BG-C] Learning resources...")
            resources_result.update(learning_resources_agent(analysis_result))
            INTERVIEW_SESSIONS[session_id]["resources"] = dict(resources_result)
            print("  [BG-C] Done.")

        def run_questions():
            print("  [BG-D] Interview questions...")
            try: questions_result.update(generate_interview_questions(analysis_result))
            except Exception as e: print(f"  [BG-D] Question generation error: {e}"); import traceback; traceback.print_exc()
            INTERVIEW_SESSIONS[session_id]["questions"]    = questions_result
            INTERVIEW_SESSIONS[session_id]["status"]       = "ready"
            if not INTERVIEW_SESSIONS[session_id].get("jobs"):      INTERVIEW_SESSIONS[session_id]["jobs"]      = list(jobs_result)
            if not INTERVIEW_SESSIONS[session_id].get("resources"): INTERVIEW_SESSIONS[session_id]["resources"] = dict(resources_result)
            total_q = sum(len(v) for v in questions_result.values() if isinstance(v, list))
            print(f"  [BG-D] ✅ Done. {total_q} total questions. Interview is LIVE.")

        def run_feedback():
            print("  [BG-E] AGI feedback...")
            feedback_result[0] = agi_feedback(analysis_result)
            print("  [BG-E] Done.")

        # ── SMART PIPELINE: Ollama gets exclusive access for questions ──
        # Jobs/Resources/Feedback → Groq (parallel, non-blocking)
        # Questions → Ollama (sequential, gets full bandwidth)
        #
        # Step 1: Start Groq tasks in parallel (they don't use Ollama)
        groq_threads = [
            threading.Thread(target=run_jobs,      name="run_jobs", daemon=True),
            threading.Thread(target=run_resources, name="run_resources", daemon=True),
            threading.Thread(target=run_feedback,  name="run_feedback", daemon=True),
        ]
        for t in groq_threads: t.start()

        # Step 2: Run questions on Ollama — gets full bandwidth now
        # (Groq threads don't touch Ollama, so no contention)
        run_questions()

        # Step 3: Wait for Groq tasks to finish
        for t in groq_threads: t.join()
        
        # Step 4: Write to Database securely after all parallel tasks finish
        save_to_sheet(details, analysis_result, jobs_result, resources_result, feedback_result[0], interview_link, session_id)
        print("  [BG-E] Saved to DB.")
        print(f"=== [BG] All done for {details['name']} ===\n")

    bg = threading.Thread(target=background_processing, daemon=True)
    bg.start()
    print(f"[FAST RETURN] Interview link ready: {interview_link}")
    return jsonify({"message": "Resume received! Processing in background.", "candidate": details["name"], "interview_link": interview_link, "status": "processing", "note": "Interview link is live now. Questions will be ready in ~30 seconds."})

# ================= REPORT RENDERER =====================
def _render_jobs(sess_jobs, jobs_text, apply_url):
    if not sess_jobs:
        return "".join("<div class='job-card'><h3>" + line + "</h3></div>" for line in jobs_text.split(" | ") if line)
    parts = []
    for j in sess_jobs[:15]:
        title = j.get('title','—'); company = j.get('company','—'); location = j.get('location','India')
        exp = j.get('experience','Fresher'); salary = j.get('salary',''); desc = j.get('description','')
        match = j.get('match','—'); url = j.get('url','#'); naukri = j.get('naukri_url','#')
        linkedin = j.get('linkedin_url','#'); intern = j.get('internshala_url','#')
        career_p = j.get('career_page',''); is_direct = j.get('is_direct',False)
        posted = j.get('posted_at','recent'); source = j.get('source','')
        gap = j.get('gap_advice',''); req_skills = j.get('required_skills',[])
        matched_skills = j.get('matched_skills',[]); missing_skills = j.get('missing_skills',[])
        try: mp = int(str(match).replace('%','').strip() or '0')
        except: mp = 0
        match_color = '#ff9a5c' if mp >= 60 else '#ff6b35' if mp >= 35 else '#ff3d8b'
        salary_html = ("&nbsp;·&nbsp; 💰 " + salary) if salary else ""
        req_html = ""
        if req_skills:
            tags = "".join("<span style='background:rgba(255,107,53,0.12);border:1px solid rgba(255,107,53,0.25);border-radius:4px;padding:2px 9px;font-size:11px;margin:2px;display:inline-block;color:#ffb899;'>" + s + "</span>" for s in req_skills)
            req_html = "<div style='margin-bottom:8px;'><div style='font-size:11px;color:#a05a40;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px;'>Required Skills</div><div>" + tags + "</div></div>"
        skills_html = ""
        if matched_skills or missing_skills:
            matched_html = ""
            if matched_skills:
                mtags = "".join("<span style='background:rgba(255,154,92,0.1);border:1px solid rgba(255,154,92,0.3);border-radius:4px;padding:2px 9px;font-size:11px;margin:2px;display:inline-block;color:#ff9a5c;'>✓ " + s + "</span>" for s in matched_skills)
                matched_html = "<div><div style='font-size:11px;color:#ff9a5c;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;'>✅ You Have</div><div>" + mtags + "</div></div>"
            missing_html = ""
            if missing_skills:
                mstags = "".join("<span style='background:rgba(255,61,139,0.08);border:1px solid rgba(255,61,139,0.25);border-radius:4px;padding:2px 9px;font-size:11px;margin:2px;display:inline-block;color:#ff8bbf;'>+ " + s + "</span>" for s in missing_skills)
                missing_html = "<div><div style='font-size:11px;color:#ff8bbf;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;'>⚠️ Need to Learn</div><div>" + mstags + "</div></div>"
            skills_html = "<div style='display:flex;gap:20px;flex-wrap:wrap;margin-bottom:8px;'>" + matched_html + missing_html + "</div>"
        gap_html = ""
        if gap:
            gap_html = "<div style='background:rgba(255,107,53,0.06);border-left:3px solid #ff6b35;border-radius:0 6px 6px 0;padding:10px 14px;margin-bottom:12px;font-size:13px;color:#ffcca8;line-height:1.65;'><strong>🎯 Gap Analysis: </strong>" + gap + "</div>"
        apply_label = "⚡ Direct Apply" if is_direct else "🔍 Search Jobs"
        direct_badge = ""
        if is_direct:
            direct_badge = "<span style='font-size:11px;color:#ff9a5c;background:rgba(255,107,53,0.1);border:1px solid rgba(255,107,53,0.3);padding:3px 8px;border-radius:10px;'>✓ Real listing · " + posted + " · via " + source + "</span>"
        career_btn = ""
        if career_p:
            career_btn = "<a href='" + career_p + "' target='_blank' style='background:rgba(255,61,139,0.1);border:1px solid rgba(255,61,139,0.3);color:#ff8bbf;padding:7px 14px;border-radius:6px;font-size:12px;text-decoration:none;font-weight:600;'>Career Page</a>"
        card = ("<div class='job-card' style='margin-bottom:20px;'><div style='display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;'><div style='flex:1;'><h3 style='font-size:16px;font-weight:700;color:#f0e8e0;margin-bottom:4px;'>" + title + "</h3><div style='font-size:13px;color:#c4887a;margin-bottom:6px;'>🏢 <strong style='color:#ffb899;'>" + company + "</strong>&nbsp;·&nbsp; 📍 " + location + "&nbsp;·&nbsp; 💼 " + exp + salary_html + "</div><span style='background:rgba(255,107,53,0.1);border:1px solid rgba(255,107,53,0.25);color:#ff9a5c;padding:2px 10px;border-radius:12px;font-size:11px;'>🕐 Recent postings — last 7 days</span></div><div style='text-align:right;min-width:60px;'><div style='font-size:22px;font-weight:800;color:" + match_color + ";'>" + match + "</div><div style='font-size:10px;color:#a05a40;'>skill match</div></div></div><p style='font-size:13px;color:#e0c8b8;line-height:1.7;margin:10px 0;'>" + desc + "</p>" + req_html + skills_html + gap_html + "<div style='display:flex;gap:8px;flex-wrap:wrap;align-items:center;'><a href='" + url + "' target='_blank' style='background:linear-gradient(135deg,#ff6b35,#ff3d8b);color:#fff;padding:8px 18px;border-radius:6px;font-size:13px;text-decoration:none;font-weight:700;'>" + apply_label + "</a>" + direct_badge + "<a href='" + naukri + "' target='_blank' style='background:rgba(255,107,53,0.15);border:1px solid rgba(255,107,53,0.35);color:#ffb899;padding:7px 14px;border-radius:6px;font-size:12px;text-decoration:none;font-weight:600;'>Naukri</a><a href='" + linkedin + "' target='_blank' style='background:rgba(255,61,139,0.12);border:1px solid rgba(255,61,139,0.3);color:#ff8bbf;padding:7px 14px;border-radius:6px;font-size:12px;text-decoration:none;font-weight:600;'>LinkedIn</a><a href='" + intern + "' target='_blank' style='background:rgba(255,154,92,0.12);border:1px solid rgba(255,154,92,0.3);color:#ffcca8;padding:7px 14px;border-radius:6px;font-size:12px;text-decoration:none;font-weight:600;'>Internshala</a>" + career_btn + "</div></div>")
        parts.append(card)
    result = "".join(parts)
    if apply_url and apply_url != "#":
        result += "<a href='" + apply_url + "' target='_blank' class='btn btn-outline' style='margin-top:12px;display:inline-block;'>Apply to Top Match →</a>"
    return result

@app.route("/report/<session_id>")
def personal_report(session_id):
    session = INTERVIEW_SESSIONS.get(session_id)
    if not session:
        return "<h2 style='font-family:sans-serif;text-align:center;margin-top:80px;color:#fff;background:#0a0a0f;min-height:100vh;padding:40px;'>Report not found or server restarted. Please re-upload your resume.</h2>", 404
    name = str(session.get("name","Candidate") or "Candidate"); domain = str(session.get("domain","") or ""); education = str(session.get("education","") or "")
    skills = session.get("skills",[])
    if isinstance(skills, str): skills = [s.strip() for s in skills.split(",") if s.strip()]
    career = session.get("career_fit",[])
    if isinstance(career, str): career = [c.strip() for c in career.split(",") if c.strip()]
    interview = f"{BASE_URL}/interview/{session_id}"; status = session.get("status","processing")
    row = {}
    try:
        col = get_col()
        if col:
            found = col.find_one({"interview_link": {"$regex": session_id}}, {"_id": 0}); row = found or {}
    except: row = {}
    def _s(val, default=""):
        if val is None: return default
        if isinstance(val, list): return ", ".join(str(v) for v in val if v)
        if isinstance(val, dict): return str(val)
        return str(val).strip() or default
    sess_resources = session.get("resources",{}); sess_jobs = session.get("jobs",[])
    if not sess_jobs and row:
        top_jobs_str = row.get("top_jobs","")
        if top_jobs_str:
            sess_jobs = [{"title": part.split(" @ ")[0].strip(), "company": part.split(" @ ")[1].split(" [")[0].strip() if " @ " in part else "", "match": part.split("[")[1].rstrip("]").strip() if "[" in part else "?", "url": f"https://www.google.com/search?q={part.split(' @ ')[0].replace(' ','+')}+jobs+India&ibp=htl;jobs", "location": "India","experience": "Fresher","salary": "","description": "","required_skills": [],"is_direct": False} for part in top_jobs_str.split(" | ") if part.strip()]
    jobs_text     = _s(row.get("top_jobs")) or " | ".join(f"{j.get('title','')} @ {j.get('company','')} [{j.get('match','?')}]" for j in sess_jobs[:5]) or ""
    strengths     = _s(row.get("strengths")     or session.get("strengths",""))
    weaknesses    = _s(row.get("weaknesses")    or session.get("weaknesses",""))
    skill_gaps    = _s(row.get("skill_gaps")    or session.get("skill_gaps",""))
    books         = _s(row.get("books")         or sess_resources.get("books",""))
    courses       = _s(row.get("courses")       or sess_resources.get("courses",""))
    youtube       = _s(row.get("youtube")       or sess_resources.get("youtube",""))
    learning_path = _s(row.get("learning_path") or sess_resources.get("learning_path",""))
    agi_feedback_text = _s(row.get("agi_feedback",""))
    confidence    = _s(row.get("confidence")    or session.get("confidence","Medium")) or "Medium"
    best_job      = _s(row.get("best_title",""))
    best_company  = _s(row.get("best_company",""))
    match_pct     = _s(row.get("match_pct",""))
    apply_url     = _s(row.get("apply_url","#")) or "#"
    still_processing = (status == "processing")
    auto_refresh     = '<meta http-equiv="refresh" content="8">' if still_processing else ""
    processing_banner = ""
    if still_processing:
        processing_banner = """<div style="background:linear-gradient(135deg,#1a1a00,#1a0f00);border:1px solid rgba(245,166,35,0.3);border-radius:10px;padding:14px 18px;margin-bottom:18px;display:flex;align-items:center;gap:12px;"><div style="font-size:20px;animation:spin 2s linear infinite;display:inline-block;">⏳</div><div><div style="color:#f5a623;font-weight:700;font-size:14px;">AI is still processing your full report...</div><div style="color:#8888aa;font-size:12px;margin-top:2px;">This page will auto-refresh every 8 seconds.</div></div></div><style>@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}</style>"""
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
  body{{font-family:'Space Grotesk',sans-serif;background:#0f0800;color:#f0e8e0;min-height:100vh;}}
  .hero{{background:linear-gradient(135deg,#1f0d05,#2a1020);padding:40px 20px;text-align:center;border-bottom:1px solid rgba(255,107,53,0.3);}}
  .hero h1{{font-size:28px;font-weight:700;background:linear-gradient(135deg,#ff6b35,#ff3d8b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:6px;}}
  .hero p{{color:#c4887a;font-size:15px;}}
  .badge{{display:inline-block;background:{conf_color}22;border:1px solid {conf_color};color:{conf_color};padding:4px 14px;border-radius:20px;font-size:13px;font-weight:600;margin-top:10px;}}
  .container{{max-width:800px;margin:0 auto;padding:24px 16px;}}
  .card{{background:#1a0d08;border:1px solid rgba(255,107,53,0.2);border-radius:12px;padding:20px 24px;margin-bottom:18px;}}
  .card h2{{font-size:15px;font-weight:700;background:linear-gradient(135deg,#ff6b35,#ff3d8b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:12px;text-transform:uppercase;letter-spacing:0.5px;}}
  .tag{{display:inline-block;background:rgba(255,107,53,0.12);border:1px solid rgba(255,107,53,0.3);border-radius:6px;padding:3px 10px;font-size:12px;margin:3px;color:#ffb899;}}
  .job-card{{background:#240f08;border-radius:8px;padding:14px 16px;margin-bottom:10px;border-left:3px solid #ff6b35;}}
  .job-card h3{{font-size:15px;font-weight:600;color:#f0e8e0;}}
  .job-card p{{font-size:13px;color:#c4887a;margin-top:4px;}}
  .btn{{display:inline-block;background:linear-gradient(135deg,#ff6b35,#ff3d8b);color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;margin:6px;}}
  .btn-outline{{background:transparent;border:2px solid #ff6b35;color:#ff6b35;}}
  .section-label{{font-size:12px;color:#a05a40;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;}}
  .feedback-box{{background:#1f0d08;border:1px solid rgba(255,107,53,0.25);border-radius:8px;padding:16px;font-size:14px;line-height:1.7;color:#ffd4b8;}}
  .cta{{text-align:center;padding:30px 0 10px;}}
  .footer{{text-align:center;padding:20px;color:#7a4030;font-size:12px;border-top:1px solid rgba(255,107,53,0.15);margin-top:20px;}}
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
  <div class="card"><h2>🎯 Career Fit</h2>
    {"".join(f"<span class='tag'>{r}</span>" for r in (career if isinstance(career,list) and career else str(career).split(",") if career else ["Processing..."]))}
    {f"<p style='margin-top:12px;font-size:13px;color:#9999b3;'><strong>Top Match:</strong> {best_job} @ {best_company} — {match_pct}</p>" if best_job else ""}
  </div>
  <div class="card"><h2>🛠 Your Skills</h2>
    {"".join(f"<span class='tag'>{s.strip()}</span>" for s in (skills if isinstance(skills,list) else str(skills).split(",")) if s and str(s).strip()) or "<p style='color:#6b6b85;font-size:13px;'>Skills will appear shortly — refresh in a few seconds.</p>"}
  </div>
  {"<div class='card'><h2>💪 Strengths</h2><p style='font-size:14px;line-height:1.7;color:#c8e8f0;'>" + strengths + "</p></div>" if strengths else ""}
  {"<div class='card'><h2>📈 Areas to Grow</h2><p style='font-size:14px;line-height:1.7;color:#ffd580;'>" + weaknesses + "</p></div>" if weaknesses else ""}
  {"<div class='card'><h2>🔍 Skill Gaps to Bridge</h2><p style='font-size:14px;color:#ff9999;'>" + skill_gaps + "</p></div>" if skill_gaps and len(skill_gaps) < 200 and not any(edu in skill_gaps.lower() for edu in ['10th','intermediate','secondary','school','mpc','btech','mtech','b.tech','m.tech','degree','college','university']) else ""}
  <div class="card"><h2>💼 Recommended Jobs</h2>{_render_jobs(sess_jobs, jobs_text, apply_url)}</div>
  <div class="card"><h2>📚 Learning Path</h2>
    {"<p style='font-size:14px;color:#a0c4ff;margin-bottom:12px;'>" + learning_path + "</p>" if learning_path else ""}
    {"<div class='section-label'>📖 Books</div><p style='font-size:13px;color:#9999b3;margin-bottom:10px;'>" + books + "</p>" if books else ""}
    {"<div class='section-label'>🎓 Courses</div><p style='font-size:13px;color:#9999b3;margin-bottom:10px;'>" + courses + "</p>" if courses else ""}
    {"<div class='section-label'>▶️ YouTube</div><p style='font-size:13px;color:#9999b3;'>" + youtube + "</p>" if youtube else ""}
  </div>
  {"<div class='card'><h2>🤖 AGI Mentor Feedback</h2><div class='feedback-box'>" + agi_feedback_text + "</div></div>" if agi_feedback_text else ""}
  <div class="cta">
    <a href="{interview}" class="btn">🎤 Start Mock Interview</a>
    <a href="/ats_score/{session_id}" class="btn" style="background:linear-gradient(135deg,#7c3aed,#06b6d4);margin-left:0;">📊 ATS Resume Scorer</a>
    <a href="/retry/{session_id}" class="btn" style="background:linear-gradient(135deg,#ef4444,#f59e0b);margin-left:0;">🎯 Retry Weak Areas</a>
    <p style="color:#6b6b85;font-size:12px;margin-top:12px;">All links are valid for this session</p>
  </div>
  <div class="card" style="border-color:rgba(255,61,139,0.3);background:linear-gradient(135deg,#1a0d08,#1f0815);">
    <h2 style="color:#ff3d8b;">💙 Feeling Rejected or Burned Out?</h2>
    <p style="font-size:14px;color:#c4887a;line-height:1.7;margin-bottom:16px;">Job rejections are painful. It's okay to feel exhausted, lost, or hopeless. Your AGI mentor is here — not to give career advice, but to <strong style="color:#ffb8d4;">listen and be with you</strong>.</p>
    <div id="supportChat" style="display:none;">
      <div id="chatMessages" style="background:#0f0800;border:1px solid rgba(255,61,139,0.2);border-radius:10px;padding:16px;min-height:120px;max-height:320px;overflow-y:auto;margin-bottom:12px;font-size:14px;line-height:1.7;"></div>
      <div style="display:flex;gap:8px;">
        <textarea id="supportInput" placeholder="Tell me how you're feeling right now..." rows="2" style="flex:1;background:#240f08;border:1px solid rgba(255,61,139,0.3);border-radius:8px;padding:10px 14px;color:#f0e8e0;font-family:inherit;font-size:13px;resize:none;outline:none;"></textarea>
        <button onclick="sendSupport()" id="sendBtn" style="background:linear-gradient(135deg,#ff3d8b,#ff6b35);color:#fff;border:none;border-radius:8px;padding:10px 18px;font-weight:700;cursor:pointer;font-size:13px;align-self:stretch;">Send</button>
      </div>
      <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;">
        <button onclick="quickMsg('I keep getting rejected and I feel like giving up')" class="quick-btn">😔 I want to give up</button>
        <button onclick="quickMsg('I feel like I am not good enough for any job')" class="quick-btn">💔 I feel worthless</button>
        <button onclick="quickMsg('I have been rejected 10+ times and I am completely exhausted')" class="quick-btn">😮‍💨 I am exhausted</button>
        <button onclick="quickMsg('Everyone around me got placed except me. I feel ashamed')" class="quick-btn">😶 I feel left behind</button>
      </div>
    </div>
    <button onclick="openSupport()" id="openSupportBtn" style="background:linear-gradient(135deg,#ff3d8b,#ff6b35);color:#fff;border:none;padding:12px 28px;border-radius:8px;font-weight:700;font-size:14px;cursor:pointer;width:100%;margin-top:4px;">💙 Talk to Your AGI Mentor</button>
  </div>
</div>
<div class="footer">AGI Career System · Personalised Report for {name} · {datetime.datetime.now().strftime("%d %b %Y")}</div>
<style>
.quick-btn{{background:rgba(255,107,53,0.1);border:1px solid rgba(255,107,53,0.3);color:#ffb899;padding:6px 12px;border-radius:20px;font-size:12px;cursor:pointer;transition:all 0.2s;}}
.msg-ai{{background:rgba(255,107,53,0.1);border-left:3px solid #ff6b35;border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px;color:#ffd4b8;}}
.msg-user{{background:rgba(255,61,139,0.08);border-right:3px solid #ff3d8b;border-radius:8px 0 0 8px;padding:10px 14px;margin-bottom:10px;color:#ffb8d4;text-align:right;}}
.typing{{color:#a05a40;font-style:italic;font-size:13px;padding:8px 14px;}}
</style>
<script>
const studentName = "{name}"; const studentDomain = "{domain}"; const chatHistory = [];
function openSupport() {{ document.getElementById('supportChat').style.display='block'; document.getElementById('openSupportBtn').style.display='none'; appendAI(`Hi {name} 💙 I'm here with you. This isn't about your resume right now — it's about YOU.\\n\\nRejections hurt deeply, especially when you've worked so hard. Tell me honestly — how are you feeling right now?`); }}
function quickMsg(text) {{ document.getElementById('supportInput').value=text; sendSupport(); }}
function appendUser(msg) {{ const div=document.createElement('div'); div.className='msg-user'; div.textContent=msg; document.getElementById('chatMessages').appendChild(div); scrollChat(); }}
function appendAI(msg) {{ const div=document.createElement('div'); div.className='msg-ai'; div.innerHTML=msg.replace(/\\n/g,'<br>'); document.getElementById('chatMessages').appendChild(div); scrollChat(); }}
function appendTyping() {{ const div=document.createElement('div'); div.className='typing'; div.id='typingIndicator'; div.textContent='💙 Your mentor is thinking...'; document.getElementById('chatMessages').appendChild(div); scrollChat(); }}
function removeTyping() {{ const t=document.getElementById('typingIndicator'); if(t) t.remove(); }}
function scrollChat() {{ const c=document.getElementById('chatMessages'); c.scrollTop=c.scrollHeight; }}
async function sendSupport() {{
  const input=document.getElementById('supportInput'); const msg=input.value.trim(); if(!msg) return;
  input.value=''; document.getElementById('sendBtn').disabled=true;
  appendUser(msg); chatHistory.push({{"role":"user","content":msg}}); appendTyping();
  try {{
    const res=await fetch('/emotional_support',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:msg,name:studentName,domain:studentDomain,history:chatHistory.slice(-6)}})}});
    const data=await res.json(); removeTyping();
    const reply=data.reply||"I'm here with you. Take a breath. 💙";
    appendAI(reply); chatHistory.push({{"role":"assistant","content":reply}});
  }} catch(e) {{ removeTyping(); appendAI("I'm here with you. Take a breath. You are seen. 💙"); }}
  document.getElementById('sendBtn').disabled=false; document.getElementById('supportInput').focus();
}}
document.getElementById('supportInput')?.addEventListener('keydown', e=>{{ if(e.key==='Enter'&&!e.shiftKey){{e.preventDefault();sendSupport();}} }});
</script>
</body>
</html>"""
    from flask import Response
    return Response(html, mimetype="text/html")

@app.route("/fetch_indeed_jobs", methods=["POST"])
def fetch_indeed_jobs():
    data = request.get_json() or {}; query = data.get("query","Software Engineer"); location = data.get("location","India"); api_key = ANTHROPIC_API_KEY
    if not api_key: return jsonify({"jobs": [], "error": "No Anthropic key"}), 200
    try:
        resp = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json={"model": "claude-sonnet-4-20250514", "max_tokens": 2000, "mcp_servers": [{"type":"url","url":"https://mcp.indeed.com/claude/mcp","name":"indeed"}], "messages": [{"role":"user","content":f'Search Indeed for jobs matching: "{query}" in {location}. Return results as a JSON array only: [{{"title":"","company":"","location":"","experience":"","description":"","url":"","match":"0%"}}]'}]}, timeout=30)
        if resp.status_code == 200:
            text = "".join(block.get("text","") for block in resp.json().get("content",[]) if block.get("type")=="text")
            if text:
                s = text.find("["); e = text.rfind("]") + 1
                if s != -1 and e > s:
                    jobs = json.loads(text[s:e])
                    if isinstance(jobs, list) and jobs: return jsonify({"jobs": jobs})
        return jsonify({"jobs": []})
    except Exception as e: print(f"  [Indeed] Error: {e}"); return jsonify({"jobs": []})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "AGI Career System Online"})

@app.route("/emotional_support", methods=["POST"])
def emotional_support():
    data = request.get_json() or {}; message = data.get("message","").strip(); name = data.get("name","friend"); domain = data.get("domain",""); history = data.get("history",[])
    if not message: return jsonify({"reply": "I'm here. Take your time. 💙"})
    system_prompt = f"""You are an emotionally intelligent AGI mentor named Arya.
You are talking to {name}, a student in the field of {domain or 'technology'} who is exhausted from job rejections.
Your ONLY job right now is to provide emotional support. NOT career advice. NOT to-do lists.
Your personality: Warm, gentle, deeply human. You validate their pain without minimising it. You speak like a wise, caring older sibling. You use their name naturally. You ask ONE gentle question at a time.
Rules: Maximum 4 short paragraphs. Never give resume advice unless explicitly asked. Never say "as an AI". If they express self-harm thoughts, gently encourage them to speak to someone and provide iCall India: 9152987821. Always end with a gentle question OR a single line of quiet encouragement."""
    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-8:]:
        role = h.get("role","user"); content = h.get("content","")
        if role in ("user","assistant") and content: messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    try:
        reply = nvidia_client.call(messages=messages, temperature=0.85, max_tokens=400)
        if not reply: reply = f"I hear you, {name}. What you're feeling right now is real, and it matters. I'm right here. 💙"
    except Exception as e:
        print(f"  [Emotional] Error: {e}"); reply = f"I'm here with you, {name}. Rejections are genuinely painful — not a reflection of who you are. 💙"
    return jsonify({"reply": reply})

@app.route("/support")
def support_page():
    html = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>AGI Mentor — Emotional Support</title><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Segoe UI',sans-serif;background:#0f0800;color:#f0e8e0;height:100vh;display:flex;flex-direction:column;}.topbar{background:linear-gradient(135deg,#1f0d05,#2a1020);padding:16px 24px;border-bottom:1px solid rgba(255,107,53,0.2);display:flex;align-items:center;gap:12px;}.avatar{width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#ff6b35,#ff3d8b);display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0;}.mentor-info h2{font-size:15px;color:#fff;font-weight:600;}.mentor-info p{font-size:12px;color:#c4887a;}.online-dot{width:8px;height:8px;background:#ff9a5c;border-radius:50%;display:inline-block;margin-right:4px;animation:pulse 2s infinite;}@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}.messages{flex:1;overflow-y:auto;padding:20px 16px;display:flex;flex-direction:column;gap:12px;max-width:700px;width:100%;margin:0 auto;}.msg{max-width:82%;padding:12px 16px;border-radius:12px;font-size:14px;line-height:1.7;}.msg-ai{background:rgba(255,107,53,0.1);border:1px solid rgba(255,107,53,0.2);border-radius:4px 12px 12px 12px;align-self:flex-start;color:#ffd4b8;}.msg-user{background:rgba(255,61,139,0.1);border:1px solid rgba(255,61,139,0.2);border-radius:12px 4px 12px 12px;align-self:flex-end;color:#ffb8d4;text-align:right;}.typing-msg{background:rgba(255,107,53,0.06);border:1px solid rgba(255,107,53,0.12);border-radius:4px 12px 12px 12px;align-self:flex-start;padding:12px 16px;color:#a05a40;font-style:italic;font-size:13px;}.bottom{background:#1a0d08;border-top:1px solid rgba(255,107,53,0.1);padding:16px;max-width:700px;width:100%;margin:0 auto;}.quick-row{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;}.quick{background:rgba(255,107,53,0.08);border:1px solid rgba(255,107,53,0.2);color:#ffb899;padding:5px 12px;border-radius:20px;font-size:11px;cursor:pointer;}.input-row{display:flex;gap:8px;}textarea{flex:1;background:#240f08;border:1px solid rgba(255,61,139,0.25);border-radius:10px;padding:10px 14px;color:#f0e8e0;font-family:inherit;font-size:14px;resize:none;outline:none;}.send-btn{background:linear-gradient(135deg,#ff6b35,#ff3d8b);color:#fff;border:none;border-radius:10px;padding:10px 20px;font-weight:700;font-size:14px;cursor:pointer;align-self:stretch;min-width:72px;}.send-btn:disabled{opacity:0.4;cursor:not-allowed;}.name-modal{position:fixed;inset:0;background:rgba(0,0,0,0.88);display:flex;align-items:center;justify-content:center;z-index:100;padding:20px;}.name-card{background:#1a0d08;border:1px solid rgba(255,107,53,0.35);border-radius:16px;padding:32px;max-width:400px;width:100%;text-align:center;}.name-card h2{color:#ff9a5c;margin-bottom:8px;font-size:20px;}.name-card p{color:#c4887a;font-size:13px;margin-bottom:20px;line-height:1.6;}.name-input{width:100%;background:#240f08;border:1px solid rgba(255,107,53,0.3);border-radius:8px;padding:12px 16px;color:#fff;font-size:15px;outline:none;text-align:center;margin-bottom:14px;}.start-btn{width:100%;background:linear-gradient(135deg,#ff6b35,#ff3d8b);color:#fff;border:none;padding:12px;border-radius:8px;font-weight:700;font-size:15px;cursor:pointer;}</style></head><body><div class="name-modal" id="nameModal"><div class="name-card"><div style="font-size:40px;margin-bottom:12px;">💙</div><h2>You are not alone.</h2><p>Job rejections are painful. This is a safe space — no judgement, no advice unless you want it.</p><input class="name-input" id="nameInput" placeholder="What's your name?" maxlength="40"><button class="start-btn" onclick="startChat()">I'm ready to talk →</button></div></div><div class="topbar"><div class="avatar">🤝</div><div class="mentor-info"><h2>Arya — Your AGI Mentor</h2><p><span class="online-dot"></span>Here for you, right now</p></div></div><div class="messages" id="messages"></div><div class="bottom" style="display:none;" id="bottomBar"><div class="quick-row"><button class="quick" onclick="quick('I keep getting rejected and I want to give up')">😔 Want to give up</button><button class="quick" onclick="quick('I feel like I am not smart enough')">💔 Feel not enough</button><button class="quick" onclick="quick('Everyone got placed except me. I feel so ashamed')">😶 Left behind</button><button class="quick" onclick="quick('I am completely exhausted from job hunting')">😮‍💨 Exhausted</button><button class="quick" onclick="quick('I just need someone to talk to right now')">🤝 Just talk</button></div><div class="input-row"><textarea id="msgInput" rows="2" placeholder="Tell me how you're really feeling..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send();}"></textarea><button class="send-btn" id="sendBtn" onclick="send()">Send</button></div></div><script>let userName='';const history=[];function startChat(){const n=document.getElementById('nameInput').value.trim();userName=n||'friend';document.getElementById('nameModal').style.display='none';document.getElementById('bottomBar').style.display='block';appendAI(`Hi ${userName} 💙 Thank you for being here.\\n\\nThis isn't about your resume right now. It's about you.\\n\\nTell me... what's been the hardest part of this journey for you?`);}document.getElementById('nameInput').addEventListener('keydown',e=>{if(e.key==='Enter')startChat();});function appendAI(msg){const div=document.createElement('div');div.className='msg msg-ai';div.innerHTML=msg.replace(/\\n/g,'<br>');document.getElementById('messages').appendChild(div);scroll();}function appendUser(msg){const div=document.createElement('div');div.className='msg msg-user';div.textContent=msg;document.getElementById('messages').appendChild(div);scroll();}function appendTyping(){const div=document.createElement('div');div.className='typing-msg';div.id='typing';div.textContent='Arya is with you...';document.getElementById('messages').appendChild(div);scroll();}function removeTyping(){const t=document.getElementById('typing');if(t)t.remove();}function scroll(){const m=document.getElementById('messages');m.scrollTop=m.scrollHeight;}function quick(text){document.getElementById('msgInput').value=text;send();}async function send(){const input=document.getElementById('msgInput');const msg=input.value.trim();if(!msg)return;input.value='';document.getElementById('sendBtn').disabled=true;appendUser(msg);history.push({role:'user',content:msg});appendTyping();try{const res=await fetch('/emotional_support',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,name:userName,domain:'',history:history.slice(-8)})});const data=await res.json();removeTyping();const reply=data.reply||`I'm right here with you, ${userName}. You are not alone. 💙`;appendAI(reply);history.push({role:'assistant',content:reply});}catch(e){removeTyping();appendAI(`I'm here, ${userName}. Take a breath. You are seen. 💙`);}document.getElementById('sendBtn').disabled=false;document.getElementById('msgInput').focus();}</script></body></html>"""
    from flask import Response
    return Response(html, mimetype="text/html")

@app.route("/debug/<session_id>", methods=["GET"])
def debug_session(session_id):
    session = INTERVIEW_SESSIONS.get(session_id)
    if not session: return jsonify({"error": "Session not found"}), 404
    qs = session.get("questions",{}); technical = qs.get("technical",[])
    topics = {}
    for q in technical:
        t = q.get("topic","NO_TOPIC"); topics[t] = topics.get(t,0) + 1
    return jsonify({"name": session.get("name"), "skills": session.get("skills"), "total_technical": len(technical), "topics_found": topics, "aptitude": len(qs.get("aptitude",[])), "hr": len(qs.get("hr",[])), "logical": len(qs.get("logical",[])), "coding": len(qs.get("coding",[])), "sample_question": technical[0] if technical else None})

# FIX: Updated upload page — Ollama + Groq AI
@app.route("/upload")
@app.route("/")
def upload_page():
    from flask import Response
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AGI Career System — Upload Resume</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#1a0a00 0%,#2a0f0a 40%,#1a0a1a 100%);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
  .container{max-width:560px;width:100%;text-align:center}
  .logo{font-size:48px;margin-bottom:8px}
  h1{color:#fff;font-size:28px;font-weight:700;margin-bottom:6px}
  .sub{color:#c4887a;font-size:14px;margin-bottom:36px}
  .drop-zone{border:2px dashed #ff6b35;border-radius:16px;padding:48px 24px;background:rgba(255,107,53,0.05);cursor:pointer;transition:all 0.3s;position:relative}
  .drop-zone:hover,.drop-zone.dragover{border-color:#ff3d8b;background:rgba(255,61,139,0.08)}
  .drop-zone input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
  .drop-icon{font-size:48px;margin-bottom:12px}
  .drop-text{color:#c4887a;font-size:15px}
  .drop-text strong{color:#ff6b35}
  .file-name{margin-top:10px;color:#ff9a5c;font-size:13px;font-weight:600}
  .btn{display:inline-block;margin-top:24px;background:linear-gradient(135deg,#ff6b35,#ff3d8b);color:#fff;border:none;padding:14px 40px;border-radius:10px;font-size:16px;font-weight:700;cursor:pointer;width:100%;transition:opacity 0.2s}
  .btn:hover{opacity:0.9}
  .btn:disabled{opacity:0.4;cursor:not-allowed}
  .progress{display:none;margin-top:20px}
  .progress-bar{height:6px;background:#3a1a10;border-radius:3px;overflow:hidden}
  .progress-fill{height:100%;background:linear-gradient(90deg,#ff6b35,#ff3d8b);width:0%;transition:width 0.4s;border-radius:3px}
  .status{color:#c4887a;font-size:13px;margin-top:10px}
  .result{display:none;margin-top:24px;background:rgba(255,107,53,0.08);border:1px solid rgba(255,107,53,0.3);border-radius:12px;padding:20px}
  .result h3{color:#ff9a5c;margin-bottom:12px;font-size:16px}
  .link-btn{display:block;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:700;font-size:14px;margin-bottom:10px;transition:opacity 0.2s}
  .link-btn:hover{opacity:0.85}
  .report-btn{background:linear-gradient(135deg,#ff6b35,#ff8c42);color:#fff}
  .interview-btn{background:linear-gradient(135deg,#ff3d8b,#ff6baa);color:#fff}
  .company-btn{background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff}
  .features{display:flex;gap:12px;margin-top:24px;flex-wrap:wrap;justify-content:center}
  .feat{background:rgba(255,107,53,0.06);border:1px solid rgba(255,107,53,0.15);border-radius:10px;padding:12px 16px;font-size:12px;color:#c4887a;flex:1;min-width:120px}
  .feat .icon{font-size:20px;margin-bottom:4px}
</style>
</head>
<body>
<div class="container">
  <div class="logo">🎓</div>
  <h1>AGI Career System</h1>
  <p class="sub">Upload your resume — get a career report, ATS score + mock interview in 60 seconds</p>
  <div class="drop-zone" id="dropZone">
    <input type="file" id="fileInput" accept=".pdf,.docx" onchange="fileSelected(this)">
    <div class="drop-icon">📄</div>
    <div class="drop-text">Drag & drop your resume here<br><strong>or click to browse</strong></div>
    <div class="file-name" id="fileName"></div>
  </div>
  <button class="btn" id="uploadBtn" onclick="uploadResume()" disabled>🚀 Analyse My Resume</button>
  <div class="progress" id="progressDiv">
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    <div class="status" id="statusText">Uploading...</div>
  </div>
  <div class="result" id="resultDiv">
    <h3>✅ Your links are ready!</h3>
    <a id="reportLink" class="link-btn report-btn" href="#" target="_blank">📋 View Career Report + ATS Score</a>
    <a id="interviewLink" class="link-btn interview-btn" href="#" target="_blank">🎤 Start Mock Interview</a>
    <a href="/company_interview" class="link-btn company-btn">🏢 Company-Specific Interview Prep</a>
    <p style="color:#666;font-size:11px;margin-top:8px;">⏳ Full analysis completes in ~30 seconds. Refresh the report if it shows loading.</p>
  </div>
  <div class="features">
    <div class="feat"><div class="icon">🦙</div>Ollama + Groq AI</div>
    <div class="feat"><div class="icon">📊</div>ATS Scorer</div>
    <div class="feat"><div class="icon">🎤</div>145 Questions</div>
    <div class="feat"><div class="icon">🏢</div>Company Prep</div>
    <div class="feat"><div class="icon">🎯</div>Weak Area Retry</div>
  </div>
</div>
<script>
const dropZone = document.getElementById('dropZone');
let selectedFile = null;
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('dragover');
  const f = e.dataTransfer.files[0]; if(f) setFile(f);
});
function fileSelected(input) { if(input.files[0]) setFile(input.files[0]); }
function setFile(f) {
  selectedFile = f;
  document.getElementById('fileName').textContent = '📎 ' + f.name;
  document.getElementById('uploadBtn').disabled = false;
}
async function uploadResume() {
  if(!selectedFile) return;
  const btn = document.getElementById('uploadBtn');
  btn.disabled = true; btn.textContent = '⏳ Uploading...';
  const prog = document.getElementById('progressDiv');
  const fill = document.getElementById('progressFill');
  const status = document.getElementById('statusText');
  prog.style.display = 'block';
  let pct = 0;
  const steps = [[10,'Uploading resume...'],[30,'Extracting text & skills...'],[60,'AI analysis in progress...'],[85,'Generating interview questions...'],[95,'Almost done...']];
  let si = 0;
  const interval = setInterval(() => {
    if(si < steps.length) { pct = steps[si][0]; status.textContent = steps[si][1]; si++; }
    fill.style.width = pct + '%';
  }, 1200);
  try {
    const form = new FormData();
    form.append('resume', selectedFile);
    const res = await fetch('/uploadresume', { method:'POST', body:form });
    const data = await res.json();
    clearInterval(interval); fill.style.width = '100%'; status.textContent = '✅ Done!';
    if(data.interview_link) {
      const report = data.interview_link.replace('/interview/','/report/');
      document.getElementById('reportLink').href = report;
      document.getElementById('interviewLink').href = data.interview_link;
      document.getElementById('resultDiv').style.display = 'block';
      btn.textContent = '✅ Upload another resume'; btn.disabled = false;
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
    return Response(html, mimetype="text/html")


@app.route("/profile/<session_id>", methods=["GET"])
def get_profile(session_id):
    if not AI_ENGINE_LOADED: return jsonify({"error": "AI engine not loaded"}), 503
    profile = USER_PROFILES.get(session_id)
    if not profile: return jsonify({"error": "No profile yet"}), 404
    return jsonify(profile.to_dict())

@app.route("/skill_graph/<skill>", methods=["GET"])
def get_skill_graph(skill):
    if not AI_ENGINE_LOADED: return jsonify({"error": "AI engine not loaded"}), 503
    try:
        from ai_engine import get_related_skills; related = get_related_skills(skill)
    except Exception: related = []
    return jsonify({"skill": skill, "related": related, "graph": {skill: related}})

@app.route("/explain_match", methods=["POST"])
def explain_match():
    if not AI_ENGINE_LOADED: return jsonify({"error": "AI engine not loaded"}), 503
    data = request.get_json() or {}
    result = skill_gap_intelligence(data.get("candidate_skills",[]), data.get("job_required_skills",[]), data.get("job_title",""), data.get("domain",""))
    return jsonify(result)

@app.route("/pipeline_status/<session_id>", methods=["GET"])
def pipeline_status(session_id):
    session = INTERVIEW_SESSIONS.get(session_id)
    if not session: return jsonify({"error": "Session not found"}), 404
    skills = session.get("skills",[]); domain = session.get("domain","General"); jobs = session.get("jobs",[]); qs = session.get("questions",{})
    total_q = sum(len(v) for v in qs.values() if isinstance(v, list))
    inferred_list = []
    if AI_ENGINE_LOADED and skills:
        inferred_list = list(infer_implicit_skills(skills).keys())[:8]
    profile_summary = "No interview data yet"
    if AI_ENGINE_LOADED and session_id in USER_PROFILES:
        profile_summary = USER_PROFILES[session_id].get_improvement_summary()
    top_job   = jobs[0].get("title","None") if jobs else "None"
    top_score = jobs[0].get("decision_score","N/A") if jobs else "N/A"
    return jsonify({"pipeline": [{"agent":"ResumeAgent","status":"complete","output":f"Extracted {len(skills)} skills, domain={domain}"},{"agent":"SkillEngine","status":"complete","output":f"{len(skills)} explicit + {len(inferred_list)} inferred via skill graph","inferred_skills":inferred_list},{"agent":"DecisionEngine","status":"complete","output":f"Ranked {len(jobs)} jobs with multi-factor scoring","top_job":top_job,"top_score":top_score},{"agent":"InterviewEngine","status":session.get("status","processing"),"output":f"Generated {total_q} questions"},{"agent":"MemorySystem","status":"active","output":profile_summary}],"intelligence_features":["Skill Graph relationship inference","Decision Engine explainable scoring","Prioritised gap analysis with learning estimates","Local Answer Evaluator (API-independent)","User Profile memory system","Explainable AI match scores"]})



# ═══════════════════════════════════════════════════════════════
# FEATURE 1: ATS RESUME SCORER + MODIFIER
# ═══════════════════════════════════════════════════════════════

@app.route("/ats")
def ats_page():
    """ATS Resume Scorer and Modifier landing page."""
    html = open_ats_html()
    from flask import Response
    return Response(html, mimetype="text/html")

@app.route("/ats_score", methods=["POST"])
def ats_score():
    """Score a resume against a job description and return ATS analysis."""
    import io
    data        = request.form
    job_desc    = data.get("job_description", "").strip()
    resume_file = request.files.get("resume")

    if not resume_file or not job_desc:
        return jsonify({"error": "Resume and job description are required"}), 400

    resume_text = extract_text_from_pdf(io.BytesIO(resume_file.read()))
    if not resume_text:
        return jsonify({"error": "Could not extract text from resume"}), 400

    prompt = f"""You are an expert ATS (Applicant Tracking System) analyst and resume coach.

RESUME:
{resume_text[:3000]}

JOB DESCRIPTION:
{job_desc[:2000]}

Analyze the resume against this job description and return ONLY valid JSON:
{{
  "ats_score": <integer 0-100>,
  "keyword_match_score": <integer 0-100>,
  "format_score": <integer 0-100>,
  "impact_score": <integer 0-100>,
  "matched_keywords": ["keyword1", "keyword2", "keyword3"],
  "missing_keywords": ["missing1", "missing2", "missing3", "missing4", "missing5"],
  "action_verbs_found": ["developed", "implemented", "led"],
  "action_verbs_missing": ["quantified", "optimized", "architected", "deployed"],
  "format_issues": ["Issue 1 with formatting", "Issue 2"],
  "strengths": ["Strength 1", "Strength 2", "Strength 3"],
  "critical_fixes": ["Fix 1 that will most improve ATS score", "Fix 2", "Fix 3"],
  "modified_summary": "Rewritten professional summary using job keywords and strong action verbs",
  "modified_skills": ["skill1 (from JD)", "skill2 (from JD)", "skill3"],
  "ats_verdict": "Strong Match / Moderate Match / Weak Match",
  "interview_probability": "<percentage chance of getting interview call>"
}}

Be specific to THIS resume and THIS job description."""

    result = groq_json(prompt, max_tokens=2000, temperature=0.2)
    if not result:
        return jsonify({"error": "Analysis failed — try again"}), 500

    # Add modified resume bullets
    modify_prompt = f"""Based on this resume and job description, rewrite 3-5 key bullet points 
using strong action verbs and quantified achievements matching the JD keywords.

RESUME EXCERPT: {resume_text[:1500]}
JOB DESCRIPTION: {job_desc[:1000]}

Return ONLY a JSON array of improved bullet points:
["• Developed and deployed X achieving Y% improvement in Z",
 "• Implemented ABC system reducing processing time by X%"]"""

    bullets = groq_rotator.call(
        messages=[{"role": "user", "content": modify_prompt}],
        temperature=0.3, max_tokens=800
    )
    if bullets:
        try:
            import re as _re
            bullets = bullets.strip()
            if "```" in bullets:
                bullets = _re.sub(r"```(?:json)?", "", bullets).strip().rstrip("`").strip()
            s = bullets.find("["); e = bullets.rfind("]") + 1
            if s != -1 and e > s:
                result["improved_bullets"] = json.loads(bullets[s:e])
        except Exception:
            result["improved_bullets"] = []

    return jsonify(result)


# ═══════════════════════════════════════════════════════════════
# FEATURE 2: WEAK AREA DETECTION + RETRY MODE
# ═══════════════════════════════════════════════════════════════

@app.route("/weak_areas/<session_id>", methods=["GET"])
def get_weak_areas(session_id):
    """Return weak topics from interview session for retry mode."""
    if not AI_ENGINE_LOADED:
        return jsonify({"error": "AI engine not loaded"}), 503
    profile = USER_PROFILES.get(session_id)
    if not profile:
        return jsonify({"weak_areas": [], "strong_areas": [], "message": "No data yet — complete an interview first"})
    weak   = profile.get_weak_topics(threshold=6)
    strong = profile.get_strong_topics(threshold=7)
    session = INTERVIEW_SESSIONS.get(session_id, {})
    qs      = session.get("questions", {})
    # Build retry question set from weak topics
    retry_questions = []
    for topic in list(weak.keys())[:3]:
        for q in qs.get("technical", []):
            if q.get("topic","").lower() == topic.lower():
                retry_questions.append(q)
        if len(retry_questions) >= 15:
            break
    return jsonify({
        "weak_areas":       weak,
        "strong_areas":     strong,
        "summary":          profile.get_improvement_summary(),
        "retry_questions":  retry_questions[:15],
        "total_answered":   sum(len(v) for v in profile.weak_areas.values()),
        "recommendation":   f"Focus on: {', '.join(list(weak.keys())[:3])}" if weak else "Great performance! Try advanced level."
    })


@app.route("/retry_session", methods=["POST"])
def create_retry_session():
    """Create a focused retry session on weak areas."""
    data        = request.get_json() or {}
    session_id  = data.get("original_session_id", "")
    weak_topics = data.get("weak_topics", [])
    original    = INTERVIEW_SESSIONS.get(session_id, {})
    if not original:
        return jsonify({"error": "Original session not found"}), 404
    # Get questions only for weak topics
    qs    = original.get("questions", {})
    retry = [q for q in qs.get("technical", []) if q.get("topic","") in weak_topics]
    if not retry:
        retry = qs.get("technical", [])[:20]
    new_session_id = str(uuid.uuid4())
    INTERVIEW_SESSIONS[new_session_id] = {
        **original,
        "session_id":   new_session_id,
        "status":       "ready",
        "retry_mode":   True,
        "focus_topics": weak_topics,
        "questions": {
            "technical": retry,
            "hr":        [],
            "aptitude":  [],
            "logical":   [],
            "coding":    []
        }
    }
    return jsonify({
        "retry_session_id":   new_session_id,
        "interview_link":     f"{BASE_URL}/interview/{new_session_id}",
        "focus_topics":       weak_topics,
        "question_count":     len(retry),
        "message":            f"Retry session created focusing on {', '.join(weak_topics)}"
    })


# ═══════════════════════════════════════════════════════════════
# FEATURE 3: COMPANY-SPECIFIC INTERVIEW MODE
# ═══════════════════════════════════════════════════════════════

COMPANY_PROFILES = {
    "Google": {
        "style": "algorithmic problem-solving, system design, behavioral (STAR method)",
        "focus": ["Data Structures", "Algorithms", "System Design", "Leadership Principles"],
        "rounds": ["DSA Round", "System Design", "Googleyness", "Team Match"],
        "tips": "Heavy focus on Big O complexity. Always discuss trade-offs."
    },
    "Microsoft": {
        "style": "coding + problem solving + behavioral",
        "focus": ["OOP Design", "Algorithms", "Azure Cloud", "Growth Mindset"],
        "rounds": ["Coding Round", "Design Round", "Behavioral", "As Appropriate"],
        "tips": "Focus on growth mindset answers. Cloud experience valued."
    },
    "Amazon": {
        "style": "Leadership Principles heavily weighted",
        "focus": ["16 Leadership Principles", "System Design", "Coding", "Customer Obsession"],
        "rounds": ["OA Test", "Technical Screen", "Virtual Onsite (5 rounds)"],
        "tips": "Every answer must connect to an Amazon LP. Prepare STAR stories."
    },
    "Sarvam AI": {
        "style": "AI/ML deep technical + India-specific AI problems",
        "focus": ["LLMs", "Indian Language NLP", "MLOps", "Research", "Generative AI"],
        "rounds": ["ML Fundamentals", "Coding", "Research Discussion", "Culture Fit"],
        "tips": "Focus on Indic language models, ASR, TTS. Open source contributions valued."
    },
    "Krutrim": {
        "style": "AI systems + scaling + Indian context",
        "focus": ["LLM Training", "Infrastructure", "Python", "Distributed Systems"],
        "rounds": ["Technical Screen", "System Design", "ML Round", "Founders Round"],
        "tips": "Building at scale for India. Show passion for Indian AI ecosystem."
    },
    "Quantiphi": {
        "style": "Applied ML + consulting mindset",
        "focus": ["Machine Learning", "Deep Learning", "Cloud (AWS/GCP)", "Business Problem Solving"],
        "rounds": ["Aptitude Test", "Technical Interview", "Case Study", "HR Round"],
        "tips": "Frame ML solutions as business impact. Know cloud ML services."
    },
    "Fractal Analytics": {
        "style": "Data science + analytics + storytelling",
        "focus": ["Statistics", "Machine Learning", "SQL", "Business Acumen", "Python"],
        "rounds": ["Case Study", "Technical Round", "Analytics Round", "HR"],
        "tips": "Strong statistics fundamentals required. Communication skills crucial."
    },
    "Zerodha": {
        "style": "practical engineering + minimal BS",
        "focus": ["Backend Engineering", "Databases", "System Reliability", "Python/Go"],
        "rounds": ["Take-home Assignment", "Technical Discussion", "Culture Interview"],
        "tips": "No-nonsense culture. Show real projects. Performance and reliability matter."
    },
    "Swiggy": {
        "style": "engineering excellence + scale",
        "focus": ["System Design", "Algorithms", "Backend", "Real-time Systems"],
        "rounds": ["Coding Round", "System Design", "Behavioral", "Bar Raiser"],
        "tips": "Focus on low-latency systems. Real-time order management context."
    },
    "Razorpay": {
        "style": "fintech engineering + security mindset",
        "focus": ["System Design", "Backend", "Security", "Payments Infrastructure"],
        "rounds": ["DSA Round", "System Design", "Fintech Domain", "Culture"],
        "tips": "Understand payment flows, idempotency, distributed transactions."
    }
}

@app.route("/company_interview/<session_id>/<company>", methods=["GET"])
def company_interview_questions(session_id, company):
    """Generate company-specific interview questions."""
    session = INTERVIEW_SESSIONS.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    profile = COMPANY_PROFILES.get(company)
    if not profile:
        available = list(COMPANY_PROFILES.keys())
        return jsonify({"error": f"Company not found. Available: {available}"}), 404

    domain     = session.get("domain", "General")
    skills     = session.get("skills", [])
    skills_str = ", ".join(skills[:8])

    prompt = f"""You are a senior interviewer at {company}.

Company interview style: {profile['style']}
Focus areas: {', '.join(profile['focus'])}

Candidate: {domain} | Skills: {skills_str}

Generate 10 interview questions specifically in {company}'s interview style.
Include: technical questions, behavioral questions in their format, and company-specific questions.

Return ONLY JSON array:
[{{"q":"question","answer":"ideal answer approach","type":"technical/behavioral/company-specific","tip":"{company} tip: ..."}}]"""

    raw = groq_rotator.call(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3, max_tokens=2000
    )
    questions = []
    if raw:
        try:
            raw = raw.strip()
            if "```" in raw:
                import re as _re; raw = _re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
            s = raw.find("["); e = raw.rfind("]") + 1
            if s != -1 and e > s:
                questions = json.loads(raw[s:e])
        except Exception as ex:
            print(f"  [Company] Parse error: {ex}")

    return jsonify({
        "company":   company,
        "profile":   profile,
        "questions": questions,
        "rounds":    profile["rounds"],
        "top_tip":   profile["tips"]
    })

@app.route("/companies", methods=["GET"])
def get_companies():
    """Return list of supported companies."""
    return jsonify({
        "companies": [
            {"name": k, "style": v["style"][:60] + "...", "focus": v["focus"][:3]}
            for k, v in COMPANY_PROFILES.items()
        ]
    })
# ═══════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# FEATURE 1: ATS RESUME SCORER + MODIFIER
# ═══════════════════════════════════════════════════════════════

@app.route("/ats_score/<session_id>", methods=["GET"])
def ats_score_page(session_id):
    session = INTERVIEW_SESSIONS.get(session_id, {})
    name   = session.get("name", "Candidate")
    skills = session.get("skills", [])
    domain = session.get("domain", "General")
    from flask import Response
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ATS Resume Scorer — {name}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
  :root{{--bg:#050510;--s1:#0d0d2b;--s2:#12122f;--acc:#7c3aed;--acc2:#06b6d4;--acc3:#f59e0b;--ok:#10b981;--warn:#ef4444;--text:#e2e8f0;--muted:#64748b;}}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}}
  body::before{{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 80% 50% at 20% 0%,rgba(124,58,237,0.15),transparent),radial-gradient(ellipse 60% 40% at 80% 100%,rgba(6,182,212,0.1),transparent);pointer-events:none;z-index:0;}}
  .wrap{{position:relative;z-index:1;max-width:900px;margin:0 auto;padding:30px 20px;}}
  h1{{font-family:'Syne',sans-serif;font-size:clamp(24px,4vw,42px);font-weight:800;background:linear-gradient(135deg,#fff,var(--acc2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:6px;}}
  .sub{{color:var(--muted);font-size:14px;margin-bottom:30px;}}
  .card{{background:var(--s1);border:1px solid rgba(124,58,237,0.2);border-radius:16px;padding:24px;margin-bottom:20px;}}
  .card h2{{font-family:'Syne',sans-serif;font-size:16px;font-weight:700;color:var(--acc2);margin-bottom:16px;text-transform:uppercase;letter-spacing:1px;}}
  textarea{{width:100%;background:var(--s2);border:1px solid rgba(124,58,237,0.3);border-radius:10px;padding:14px;color:var(--text);font-family:'DM Sans',sans-serif;font-size:14px;resize:vertical;outline:none;transition:border-color 0.3s;}}
  textarea:focus{{border-color:var(--acc2);}}
  .btn{{padding:12px 28px;border-radius:10px;border:none;font-family:'Syne',sans-serif;font-size:14px;font-weight:700;cursor:pointer;transition:all 0.3s;}}
  .btn-primary{{background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;box-shadow:0 4px 20px rgba(124,58,237,0.4);}}
  .btn-primary:hover{{transform:translateY(-2px);box-shadow:0 8px 30px rgba(124,58,237,0.5);}}
  .btn-primary:disabled{{opacity:0.4;cursor:not-allowed;transform:none;}}
  .score-ring{{width:140px;height:140px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 20px;position:relative;flex-shrink:0;}}
  .score-ring svg{{position:absolute;inset:0;transform:rotate(-90deg);}}
  .score-inner{{position:relative;text-align:center;}}
  .score-num{{font-family:'Syne',sans-serif;font-size:38px;font-weight:800;}}
  .score-label{{font-size:11px;color:var(--muted);}}
  .grid-3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-top:16px;}}
  .metric-box{{background:var(--s2);border-radius:12px;padding:16px;border:1px solid rgba(255,255,255,0.05);}}
  .metric-val{{font-family:'Syne',sans-serif;font-size:28px;font-weight:800;}}
  .metric-lbl{{font-size:12px;color:var(--muted);margin-top:4px;}}
  .tag{{display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;margin:3px;font-weight:500;}}
  .tag-ok{{background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.4);color:#10b981;}}
  .tag-miss{{background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);color:#ef4444;}}
  .tag-kw{{background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.3);color:#f59e0b;}}
  .progress-bar{{height:8px;background:var(--s2);border-radius:4px;overflow:hidden;margin-top:8px;}}
  .progress-fill{{height:100%;border-radius:4px;transition:width 1s ease;}}
  .section-score{{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.05);}}
  .section-score:last-child{{border-bottom:none;}}
  .modified-resume{{background:var(--s2);border:1px solid rgba(6,182,212,0.3);border-radius:10px;padding:16px;font-size:13px;line-height:1.8;white-space:pre-wrap;max-height:400px;overflow-y:auto;color:#a5f3fc;}}
  .spinner{{width:36px;height:36px;border:3px solid var(--s2);border-top-color:var(--acc);border-radius:50%;animation:spin 0.8s linear infinite;margin:20px auto;}}
  @keyframes spin{{to{{transform:rotate(360deg)}}}}
  .loading-text{{text-align:center;color:var(--acc2);font-size:14px;}}
  .hidden{{display:none;}}
  .action-kw{{background:rgba(124,58,237,0.15);border:1px solid rgba(124,58,237,0.3);border-radius:6px;padding:3px 10px;font-size:12px;display:inline-block;margin:3px;color:#c4b5fd;}}
  .back-btn{{display:inline-flex;align-items:center;gap:8px;color:var(--muted);font-size:13px;text-decoration:none;margin-bottom:20px;transition:color 0.2s;}}
  .back-btn:hover{{color:var(--text);}}
</style>
</head>
<body>
<div class="wrap">
  <a href="/report/{session_id}" class="back-btn">← Back to Report</a>
  <h1>📄 ATS Resume Scorer</h1>
  <p class="sub">Analyse your resume against any job description — get ATS score, missing keywords, and improvement tips</p>

  <div class="card">
    <h2>📋 Paste Job Description</h2>
    <textarea id="jdInput" rows="6" placeholder="Paste the full job description here — e.g. from LinkedIn, Naukri, or any company careers page..."></textarea>
    <div style="display:flex;gap:12px;margin-top:14px;flex-wrap:wrap;">
      <button class="btn btn-primary" onclick="analyseATS()" id="analyseBtn">🔍 Analyse ATS Score</button>
    </div>
  </div>

  <div id="loadingDiv" class="hidden">
    <div class="card" style="text-align:center;padding:40px;">
      <div class="spinner"></div>
      <div class="loading-text" id="loadingText">Analysing your resume against the job description...</div>
    </div>
  </div>

  <div id="resultsDiv" class="hidden">
    <div class="card">
      <h2>🎯 ATS Score</h2>
      <div style="display:flex;align-items:center;gap:30px;flex-wrap:wrap;">
        <div class="score-ring" id="scoreRing">
          <svg viewBox="0 0 140 140"><circle cx="70" cy="70" r="58" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="12"/><circle id="scoreCircle" cx="70" cy="70" r="58" fill="none" stroke="url(#grad)" stroke-width="12" stroke-linecap="round" stroke-dasharray="364" stroke-dashoffset="364"/><defs><linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#7c3aed"/><stop offset="100%" stop-color="#06b6d4"/></linearGradient></defs></svg>
          <div class="score-inner">
            <div class="score-num" id="scoreNum">0</div>
            <div class="score-label">ATS Score</div>
          </div>
        </div>
        <div style="flex:1;">
          <div id="scoreVerdict" style="font-family:'Syne',sans-serif;font-size:18px;font-weight:700;margin-bottom:8px;"></div>
          <div id="scoreSummary" style="font-size:13px;color:var(--muted);line-height:1.7;"></div>
        </div>
      </div>
      <div class="grid-3" id="metricsGrid"></div>
    </div>

    <div class="card">
      <h2>📊 Section Breakdown</h2>
      <div id="sectionBreakdown"></div>
    </div>

    <div class="card">
      <h2>✅ Keywords You Have</h2>
      <div id="matchedKeywords"></div>
    </div>

    <div class="card">
      <h2>❌ Missing Keywords</h2>
      <div id="missingKeywords"></div>
      <div style="margin-top:14px;">
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:1px;">💡 Recommended Action Keywords to Add</div>
        <div id="actionKeywords"></div>
      </div>
    </div>

    <div class="card">
      <h2>🔧 Improvement Tips</h2>
      <div id="improvementTips"></div>
    </div>
  </div>

  <div id="modifiedDiv" class="hidden">
    <div class="card" style="border-color:rgba(6,182,212,0.3);">
      <h2 style="color:var(--acc2);">✨ AI-Modified Resume</h2>
      <p style="font-size:13px;color:var(--muted);margin-bottom:14px;">Your resume rewritten to match this job description — ATS optimized with action keywords and relevant skills highlighted.</p>
      <div class="modified-resume" id="modifiedResume"></div>
      <button class="btn btn-primary" style="margin-top:14px;" onclick="copyResume()">📋 Copy Modified Resume</button>
    </div>
  </div>
</div>

<script>
const sessionId = "{session_id}";
const candidateSkills = {json.dumps(skills)};
const candidateDomain = "{domain}";
const candidateName   = "{name}";

async function analyseATS() {{
  const jd = document.getElementById('jdInput').value.trim();
  if (!jd) {{ alert('Please paste a job description first.'); return; }}
  document.getElementById('analyseBtn').disabled = true;
  document.getElementById('loadingDiv').classList.remove('hidden');
  document.getElementById('resultsDiv').classList.add('hidden');
  document.getElementById('loadingText').textContent = 'Analysing your resume against the job description...';

  try {{
    const res  = await fetch('/api/ats_analyse', {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{ session_id: sessionId, job_description: jd }})
    }});
    const data = await res.json();
    renderATSResults(data);
  }} catch(e) {{
    alert('Analysis failed — please try again.');
  }}
  document.getElementById('loadingDiv').classList.add('hidden');
  document.getElementById('analyseBtn').disabled = false;
}}



function renderATSResults(data) {{
  const score = data.ats_score || 0;
  // Animate score ring
  const offset = 364 - (364 * score / 100);
  setTimeout(() => {{
    document.getElementById('scoreCircle').style.strokeDashoffset = offset;
    animateNum('scoreNum', 0, score, 1000);
  }}, 100);

  const color  = score >= 75 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';
  document.getElementById('scoreNum').style.color = color;
  document.getElementById('scoreVerdict').textContent = score >= 75 ? '🎉 Strong ATS Match!' : score >= 50 ? '⚠️ Moderate Match — Needs Improvement' : '❌ Poor Match — Significant Gaps';
  document.getElementById('scoreVerdict').style.color = color;
  document.getElementById('scoreSummary').textContent = data.summary || '';

  // Metrics
  const metrics = [
    {{ label:'Keyword Match', val: (data.keyword_match_pct||0)+'%', color:'#7c3aed' }},
    {{ label:'Skills Match',  val: (data.skills_match_pct||0)+'%', color:'#06b6d4' }},
    {{ label:'Missing Terms', val: (data.missing_keywords||[]).length, color:'#ef4444' }},
  ];
  document.getElementById('metricsGrid').innerHTML = metrics.map(m =>
    `<div class="metric-box"><div class="metric-val" style="color:${{m.color}}">${{m.val}}</div><div class="metric-lbl">${{m.label}}</div></div>`
  ).join('');

  // Section breakdown
  const sections = data.section_scores || {{}};
  document.getElementById('sectionBreakdown').innerHTML = Object.entries(sections).map(([k,v]) => {{
    const col = v >= 75 ? '#10b981' : v >= 50 ? '#f59e0b' : '#ef4444';
    return `<div class="section-score">
      <span style="font-size:14px;">${{k}}</span>
      <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:120px;"><div class="progress-bar"><div class="progress-fill" style="width:${{v}}%;background:${{col}};"></div></div></div>
        <span style="font-size:13px;font-weight:700;color:${{col}};width:40px;text-align:right;">${{v}}%</span>
      </div>
    </div>`;
  }}).join('');

  // Keywords
  document.getElementById('matchedKeywords').innerHTML = (data.matched_keywords||[]).map(k => `<span class="tag tag-ok">✓ ${{k}}</span>`).join('');
  document.getElementById('missingKeywords').innerHTML = (data.missing_keywords||[]).map(k => `<span class="tag tag-miss">✗ ${{k}}</span>`).join('');
  document.getElementById('actionKeywords').innerHTML  = (data.action_keywords||[]).map(k => `<span class="action-kw">${{k}}</span>`).join('');

  // Tips
  document.getElementById('improvementTips').innerHTML = (data.improvement_tips||[]).map((t,i) =>
    `<div style="display:flex;gap:12px;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
       <span style="color:var(--acc2);font-weight:700;min-width:24px;">${{i+1}}.</span>
       <span style="font-size:14px;line-height:1.6;">${{t}}</span>
     </div>`
  ).join('');

  document.getElementById('resultsDiv').classList.remove('hidden');
}}

function animateNum(id, from, to, dur) {{
  const el = document.getElementById(id); let start = null;
  function step(ts) {{ if(!start) start=ts; const p=Math.min((ts-start)/dur,1); el.textContent=Math.round(from+(to-from)*p); if(p<1) requestAnimationFrame(step); }}
  requestAnimationFrame(step);
}}

function copyResume() {{
  const text = document.getElementById('modifiedResume').textContent;
  navigator.clipboard.writeText(text).then(() => alert('✅ Resume copied to clipboard!'));
}}
</script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


@app.route("/api/ats_analyse", methods=["POST"])
def api_ats_analyse():
    import json as _json
    data       = request.get_json() or {}
    session_id = data.get("session_id","")
    jd         = sanitize(data.get("job_description",""), max_len=5000)
    session    = INTERVIEW_SESSIONS.get(session_id, {})
    skills     = session.get("skills",[])
    domain     = session.get("domain","General")
    education  = session.get("education","")
    projects   = session.get("achievements","") or session.get("skill_gaps","")

    if not jd:
        return jsonify({"error": "No job description provided"}), 400

    prompt = f"""You are an expert ATS (Applicant Tracking System) analyser.

CANDIDATE PROFILE:
- Domain: {domain}
- Skills: {", ".join(skills[:20])}
- Education: {education}

JOB DESCRIPTION:
{jd[:3000]}

Analyse how well this candidate matches the job description for ATS systems.
Return ONLY valid JSON:
{{
  "ats_score": <integer 0-100>,
  "summary": "2 sentences explaining the overall match",
  "keyword_match_pct": <integer 0-100>,
  "skills_match_pct": <integer 0-100>,
  "section_scores": {{
    "Technical Skills": <0-100>,
    "Experience Level": <0-100>,
    "Education": <0-100>,
    "Domain Relevance": <0-100>,
    "Keywords Density": <0-100>
  }},
  "matched_keywords": ["list of keywords candidate has that appear in JD"],
  "missing_keywords": ["list of important JD keywords candidate is missing"],
  "action_keywords": ["10 powerful action verbs to add: Developed, Implemented, Optimised, etc."],
  "improvement_tips": [
    "Specific tip 1 to improve ATS score for THIS job",
    "Specific tip 2",
    "Specific tip 3",
    "Specific tip 4",
    "Specific tip 5"
  ]
}}"""

    result = groq_json(prompt, temperature=0.2, max_tokens=2000)
    if not result:
        return jsonify({"ats_score": 50, "summary": "Analysis unavailable — try again.", "keyword_match_pct": 50, "skills_match_pct": 50, "section_scores": {{"Technical Skills": 50, "Experience Level": 40, "Education": 60, "Domain Relevance": 55, "Keywords Density": 45}}, "matched_keywords": skills[:5], "missing_keywords": [], "action_keywords": ["Developed","Implemented","Designed","Optimised","Built","Analysed","Deployed","Collaborated","Engineered","Managed"], "improvement_tips": ["Add more keywords from the job description", "Quantify your achievements with numbers", "Match your skills section to required skills", "Use exact terminology from the JD", "Add a professional summary"]})
    return jsonify(result)


@app.route("/api/modify_resume", methods=["POST"])
def api_modify_resume():
    data       = request.get_json() or {}
    session_id = data.get("session_id","")
    jd         = data.get("job_description","")
    session    = INTERVIEW_SESSIONS.get(session_id, {})
    name       = session.get("name","Candidate")
    skills     = session.get("skills",[])
    domain     = session.get("domain","General")
    education  = session.get("education","")
    career     = session.get("career_fit",[])
    strengths  = session.get("strengths","")

    prompt = f"""You are an expert resume writer. Rewrite this candidate's resume to be ATS-optimised for the given job description.

CANDIDATE INFO:
Name: {name}
Domain: {domain}
Skills: {", ".join(skills[:20])}
Education: {education}
Career Target: {", ".join(career[:3]) if career else domain}
Strengths: {strengths}

TARGET JOB DESCRIPTION:
{jd[:2000]}

Write a complete, professional, ATS-optimised resume that:
1. Incorporates exact keywords from the job description
2. Uses strong action verbs (Developed, Implemented, Designed, Optimised, Built, Deployed)
3. Quantifies achievements where possible
4. Matches the exact skills and requirements mentioned in the JD
5. Has clear sections: Summary, Skills, Education, Projects, Certifications

Format as plain text with clear section headers. Make it 1 page worth of content."""

    raw = groq_rotator.call(
        messages=[{{"role":"user","content":prompt}}],
        temperature=0.3, max_tokens=2000
    )
    if not raw:
        raw = f"{name}\n{'='*50}\n\nPROFESSIONAL SUMMARY\nExperienced {domain} professional with expertise in {', '.join(skills[:5])}.\n\nSKILLS\n{chr(10).join('• ' + s for s in skills[:15])}\n\nEDUCATION\n{education}"
    return jsonify({{"modified_resume": raw}})


# ═══════════════════════════════════════════════════════════════
# FEATURE 2: VOICE ANSWER PLAYBACK (handled in index.html JS)
# Backend endpoint to save voice recordings metadata
# ═══════════════════════════════════════════════════════════════

@app.route("/api/save_recording", methods=["POST"])
def save_recording():
    data = request.get_json() or {}
    session_id = data.get("session_id","")
    if session_id in INTERVIEW_SESSIONS:
        if "recordings" not in INTERVIEW_SESSIONS[session_id]:
            INTERVIEW_SESSIONS[session_id]["recordings"] = []
        INTERVIEW_SESSIONS[session_id]["recordings"].append({
            "question_idx": data.get("question_idx", 0),
            "duration":     data.get("duration", 0),
            "score":        data.get("score", 0),
            "topic":        data.get("topic",""),
        })
    return jsonify({{"status":"saved"}})


# ═══════════════════════════════════════════════════════════════
# FEATURE 3: WEAK AREA DETECTION + RETRY MODE
# ═══════════════════════════════════════════════════════════════

@app.route("/retry/<session_id>")
def retry_weak_page(session_id):
    session = INTERVIEW_SESSIONS.get(session_id, {{}})
    name    = session.get("name","Candidate")
    from flask import Response

    # Get weak topics from memory system
    weak_topics = []
    if AI_ENGINE_LOADED and session_id in USER_PROFILES:
        profile     = USER_PROFILES[session_id]
        weak_topics = list(profile.get_weak_topics().keys())

    # Fallback: analyse scores from answers
    if not weak_topics:
        qs       = session.get("questions", {{}})
        technical = qs.get("technical",[])
        topic_scores = {{}}
        for q in technical:
            t = q.get("topic","General")
            if t not in topic_scores: topic_scores[t] = []
            topic_scores[t].append(q.get("score", 5))
        weak_topics = [t for t,scores in topic_scores.items() if scores and sum(scores)/len(scores) < 5]

    import json as _json

    # Build topic cards HTML outside f-string (backslash not allowed inside f-string)
    topic_items = weak_topics or ['Machine Learning', 'Deep Learning', 'Generative AI']
    topics_html = ''.join(
        '<div class="topic-card" onclick="toggleTopic(this, '' + t + '')" data-topic="' + t + '">'
        '<div><div class="topic-name">' + t + '</div>'
        '<div style="font-size:12px;color:var(--muted);margin-top:4px;">Tap to select for retry</div>'
        '</div><div class="topic-score">⚠️</div></div>'
        for t in topic_items
    )
    no_weak_html = '<div class="no-weak">🎉 No weak areas detected yet — complete the interview first!</div>' if not weak_topics else ''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Retry Weak Areas — {name}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Sans:wght@300;400;500&display=swap');
  :root{{--bg:#050510;--s1:#0d0d2b;--s2:#12122f;--acc:#7c3aed;--acc2:#06b6d4;--acc3:#f59e0b;--ok:#10b981;--warn:#ef4444;--text:#e2e8f0;--muted:#64748b;}}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:30px 20px;}}
  body::before{{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 60% 40% at 10% 10%,rgba(239,68,68,0.1),transparent),radial-gradient(ellipse 50% 50% at 90% 90%,rgba(124,58,237,0.1),transparent);pointer-events:none;z-index:0;}}
  .wrap{{position:relative;z-index:1;max-width:800px;margin:0 auto;}}
  h1{{font-family:'Syne',sans-serif;font-size:clamp(22px,4vw,38px);font-weight:800;background:linear-gradient(135deg,#fff,#ef4444);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:6px;}}
  .sub{{color:var(--muted);font-size:14px;margin-bottom:30px;}}
  .card{{background:var(--s1);border:1px solid rgba(124,58,237,0.2);border-radius:16px;padding:24px;margin-bottom:20px;}}
  .card h2{{font-family:'Syne',sans-serif;font-size:15px;font-weight:700;color:var(--acc2);margin-bottom:16px;text-transform:uppercase;letter-spacing:1px;}}
  .topic-card{{background:var(--s2);border-radius:12px;padding:16px;margin-bottom:12px;border:1px solid rgba(239,68,68,0.2);display:flex;justify-content:space-between;align-items:center;cursor:pointer;transition:all 0.3s;}}
  .topic-card:hover{{border-color:rgba(239,68,68,0.5);background:rgba(239,68,68,0.05);}}
  .topic-card.selected{{border-color:#ef4444;background:rgba(239,68,68,0.1);}}
  .topic-name{{font-family:'Syne',sans-serif;font-weight:700;font-size:15px;}}
  .topic-score{{font-size:24px;font-weight:800;color:#ef4444;font-family:'Syne',sans-serif;}}
  .btn{{padding:12px 28px;border-radius:10px;border:none;font-family:'Syne',sans-serif;font-size:14px;font-weight:700;cursor:pointer;transition:all 0.3s;}}
  .btn-primary{{background:linear-gradient(135deg,#ef4444,#7c3aed);color:#fff;width:100%;font-size:16px;padding:16px;}}
  .btn-primary:hover{{transform:translateY(-2px);box-shadow:0 8px 30px rgba(239,68,68,0.4);}}
  .performance-bar{{height:6px;background:rgba(255,255,255,0.1);border-radius:3px;overflow:hidden;width:120px;}}
  .perf-fill{{height:100%;border-radius:3px;}}
  .back-btn{{display:inline-flex;align-items:center;gap:8px;color:var(--muted);font-size:13px;text-decoration:none;margin-bottom:20px;}}
  .back-btn:hover{{color:var(--text);}}
  .no-weak{{text-align:center;padding:40px;color:var(--ok);font-size:16px;}}
</style>
</head>
<body>
<div class="wrap">
  <a href="/interview/{session_id}" class="back-btn">← Back to Interview</a>
  <h1>🎯 Retry Weak Areas</h1>
  <p class="sub">Focus on topics where you scored below 5/10 — targeted practice makes perfect</p>

  <div class="card">
    <h2>📉 Your Weak Topics</h2>
    <div id="weakTopicsList">
      {topics_html}
    </div>
    {no_weak_html}
  </div>

  <div class="card">
    <h2>⚙️ Session Settings</h2>
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
      <label style="font-size:14px;color:var(--muted);">Difficulty:</label>
      <select id="diffLevel" style="background:var(--s2);border:1px solid rgba(124,58,237,0.3);border-radius:8px;padding:8px 12px;color:var(--text);font-family:inherit;">
        <option value="1">Level 1 — Beginner</option>
        <option value="2" selected>Level 2 — Intermediate</option>
        <option value="3">Level 3 — Advanced</option>
        <option value="0">All Levels</option>
      </select>
      <label style="font-size:14px;color:var(--muted);">Questions:</label>
      <select id="qCount" style="background:var(--s2);border:1px solid rgba(124,58,237,0.3);border-radius:8px;padding:8px 12px;color:var(--text);font-family:inherit;">
        <option value="10">10 Questions</option>
        <option value="20" selected>20 Questions</option>
        <option value="30">30 Questions</option>
      </select>
    </div>
    <button class="btn btn-primary" onclick="startRetry()">🔄 Start Focused Practice Session</button>
  </div>
</div>

<script>
const sessionId = "{session_id}";
let selectedTopics = {_json.dumps(weak_topics[:3] if weak_topics else [])};

function toggleTopic(el, topic) {{
  el.classList.toggle('selected');
  if (selectedTopics.includes(topic)) {{
    selectedTopics = selectedTopics.filter(t => t !== topic);
  }} else {{
    selectedTopics.push(topic);
  }}
}}

async function startRetry() {{
  if (selectedTopics.length === 0) {{
    alert('Please select at least one topic to practice.');
    return;
  }}
  const level = parseInt(document.getElementById('diffLevel').value);
  const count = parseInt(document.getElementById('qCount').value);

  // Fetch session, filter to selected weak topics
  const res  = await fetch('/session/' + sessionId);
  const sess = await res.json();
  const allQ = sess.questions?.technical || [];

  // Filter questions for selected topics
  let retryQ = allQ.filter(q => selectedTopics.includes(q.topic || ''));
  if (level !== 0) retryQ = retryQ.filter(q => (q.level||1) === level);
  retryQ = retryQ.sort(() => Math.random() - 0.5).slice(0, count);

  if (retryQ.length === 0) {{
    alert('No questions found for selected topics. Generating new ones...');
    // Fallback: generate fresh questions via API
    const genRes  = await fetch('/api/generate_retry_questions', {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{ session_id: sessionId, topics: selectedTopics, level, count }})
    }});
    const genData = await genRes.json();
    retryQ = genData.questions || [];
  }}

  if (retryQ.length === 0) {{
    alert('Could not load questions. Please try again.');
    return;
  }}

  // Store retry session and redirect to interview with filtered questions
  const createRes = await fetch('/api/create_retry_session', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{ parent_session_id: sessionId, questions: retryQ, topics: selectedTopics }})
  }});
  const createData = await createRes.json();
  window.location.href = '/interview/' + createData.retry_session_id;
}}
</script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


@app.route("/api/generate_retry_questions", methods=["POST"])
def generate_retry_questions():
    data       = request.get_json() or {}
    session_id = data.get("session_id","")
    topics     = data.get("topics",[])
    level      = data.get("level", 2)
    count      = data.get("count", 20)
    session    = INTERVIEW_SESSIONS.get(session_id, {})
    domain     = session.get("domain","General")
    career     = safe_cell(session.get("career_fit",[]))
    education  = session.get("education","")

    resume_context = f"Domain: {domain}, Education: {education}, Career: {career}"
    all_questions  = []
    for topic in topics[:3]:
        qs = questions_for_skill(topic, resume_context, career, domain, level)
        all_questions.extend(qs)
    return jsonify({"questions": all_questions[:count]})





# ═══════════════════════════════════════════════════════════════
# FEATURE 4: COMPANY-SPECIFIC INTERVIEW MODE
# ═══════════════════════════════════════════════════════════════

COMPANY_PROFILES = {
    "Sarvam AI":      {"focus":["nlp","llms","transformers","indic languages","speech recognition"],"style":"research-heavy","rounds":3,"tips":"Focus on multilingual NLP, Indic language models, and speech-to-text systems."},
    "Krutrim":        {"focus":["llms","generative ai","rag","fine-tuning","mlops"],"style":"applied AI","rounds":3,"tips":"Emphasise LLM fine-tuning, RAG pipelines, and production AI deployment."},
    "Quantiphi":      {"focus":["machine learning","data science","mlops","aws","gcp"],"style":"consulting","rounds":4,"tips":"Strong ML fundamentals + cloud deployment. Case-study style questions."},
    "Fractal Analytics":{"focus":["data science","statistics","python","tableau","business analytics"],"style":"analytics","rounds":3,"tips":"Business-driven analytics. Know your stats and storytelling with data."},
    "Razorpay":       {"focus":["python","system design","sql","rest apis","distributed systems"],"style":"product","rounds":4,"tips":"Strong backend fundamentals, low-latency systems, and payment domain knowledge."},
    "Freshworks":     {"focus":["javascript","react","node.js","system design","databases"],"style":"product","rounds":4,"tips":"Full-stack questions. Focus on scalability and SaaS product thinking."},
    "Zerodha":        {"focus":["python","databases","linux","algorithms","financial systems"],"style":"engineering","rounds":3,"tips":"Clean code, efficient algorithms, and basic finance/trading knowledge."},
    "Mad Street Den": {"focus":["computer vision","deep learning","pytorch","opencv","product sense"],"style":"AI product","rounds":3,"tips":"CV fundamentals + product thinking. Know retail AI use cases."},
    "Sigmoid":        {"focus":["data engineering","spark","kafka","airflow","sql","python"],"style":"data engineering","rounds":3,"tips":"Heavy on pipelines, ETL, and big data. Know Spark and Kafka deeply."},
    "upGrad":         {"focus":["python","machine learning","sql","data analysis","product analytics"],"style":"edtech","rounds":3,"tips":"Data-driven product decisions. Know A/B testing and user analytics."},
}

@app.route("/company_interview")
def company_interview_page():
    from flask import Response
    companies_json = json.dumps(list(COMPANY_PROFILES.keys()))
    profiles_json  = json.dumps(COMPANY_PROFILES)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Company-Specific Interview Prep</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
  :root{{--bg:#050510;--s1:#0d0d2b;--s2:#12122f;--acc:#7c3aed;--acc2:#06b6d4;--acc3:#f59e0b;--ok:#10b981;--text:#e2e8f0;--muted:#64748b;}}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:30px 20px;}}
  body::before{{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 70% 50% at 50% 0%,rgba(124,58,237,0.12),transparent);pointer-events:none;z-index:0;}}
  .wrap{{position:relative;z-index:1;max-width:900px;margin:0 auto;}}
  h1{{font-family:'Syne',sans-serif;font-size:clamp(24px,4vw,42px);font-weight:800;background:linear-gradient(135deg,#fff,var(--acc2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:6px;}}
  .company-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;margin:20px 0;}}
  .company-card{{background:var(--s1);border:2px solid rgba(124,58,237,0.15);border-radius:14px;padding:18px 14px;cursor:pointer;transition:all 0.3s;text-align:center;}}
  .company-card:hover{{border-color:rgba(124,58,237,0.5);transform:translateY(-3px);box-shadow:0 8px 30px rgba(124,58,237,0.2);}}
  .company-card.selected{{border-color:var(--acc2);background:rgba(6,182,212,0.08);}}
  .company-logo{{font-size:32px;margin-bottom:8px;}}
  .company-name{{font-family:'Syne',sans-serif;font-size:13px;font-weight:700;}}
  .company-type{{font-size:11px;color:var(--muted);margin-top:4px;}}
  .card{{background:var(--s1);border:1px solid rgba(124,58,237,0.2);border-radius:16px;padding:24px;margin-bottom:20px;}}
  .card h2{{font-family:'Syne',sans-serif;font-size:15px;font-weight:700;color:var(--acc2);margin-bottom:14px;text-transform:uppercase;letter-spacing:1px;}}
  .btn{{padding:12px 28px;border-radius:10px;border:none;font-family:'Syne',sans-serif;font-size:15px;font-weight:700;cursor:pointer;transition:all 0.3s;}}
  .btn-primary{{background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;box-shadow:0 4px 20px rgba(124,58,237,0.4);width:100%;padding:16px;font-size:16px;}}
  .btn-primary:hover{{transform:translateY(-2px);}}
  .btn-primary:disabled{{opacity:0.4;cursor:not-allowed;transform:none;}}
  .focus-tag{{display:inline-block;background:rgba(6,182,212,0.1);border:1px solid rgba(6,182,212,0.3);color:var(--acc2);padding:4px 12px;border-radius:20px;font-size:12px;margin:3px;}}
  .tip-box{{background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);border-radius:10px;padding:14px;font-size:14px;color:#fcd34d;line-height:1.7;}}
  input{{background:var(--s2);border:1px solid rgba(124,58,237,0.3);border-radius:10px;padding:12px 16px;color:var(--text);font-family:inherit;font-size:14px;outline:none;width:100%;}}
  input:focus{{border-color:var(--acc2);}}
  .spinner{{width:36px;height:36px;border:3px solid var(--s2);border-top-color:var(--acc);border-radius:50%;animation:spin 0.8s linear infinite;margin:20px auto;}}
  @keyframes spin{{to{{transform:rotate(360deg)}}}}
</style>
</head>
<body>
<div class="wrap">
  <h1>🏢 Company-Specific Interview</h1>
  <p style="color:var(--muted);font-size:14px;margin-bottom:24px;">Get interview questions tailored to a specific company's style, tech stack, and hiring process</p>

  <div class="card">
    <h2>👤 Your Profile</h2>
    <input type="text" id="nameInput" placeholder="Your name" style="margin-bottom:10px;">
    <input type="text" id="skillsInput" placeholder="Your skills (e.g. Python, Machine Learning, SQL)">
  </div>

  <div class="card">
    <h2>🏢 Select Company</h2>
    <div class="company-grid" id="companyGrid"></div>
  </div>

  <div id="companyDetail" style="display:none;">
    <div class="card">
      <h2>📋 Company Profile</h2>
      <div id="companyFocus" style="margin-bottom:12px;"></div>
      <div class="tip-box" id="companyTips"></div>
    </div>
  </div>

  <div class="card">
    <h2>⚙️ Session Settings</h2>
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
      <select id="roundType" style="background:var(--s2);border:1px solid rgba(124,58,237,0.3);border-radius:8px;padding:10px 14px;color:var(--text);font-family:inherit;flex:1;">
        <option value="technical">Technical Round</option>
        <option value="hr">HR Round</option>
        <option value="system_design">System Design Round</option>
        <option value="mixed">Mixed (All Types)</option>
      </select>
      <select id="qCount" style="background:var(--s2);border:1px solid rgba(124,58,237,0.3);border-radius:8px;padding:10px 14px;color:var(--text);font-family:inherit;">
        <option value="10">10 Questions</option>
        <option value="20" selected>20 Questions</option>
        <option value="30">30 Questions</option>
      </select>
    </div>
    <button class="btn btn-primary" onclick="startCompanyInterview()" id="startBtn" disabled>🚀 Start Company Interview</button>
  </div>

  <div id="generatingDiv" style="display:none;">
    <div class="card" style="text-align:center;padding:40px;">
      <div class="spinner"></div>
      <div style="color:var(--acc2);font-size:14px;">Generating company-specific questions...</div>
    </div>
  </div>
</div>

<script>
const companies  = {companies_json};
const profiles   = {profiles_json};
const companyIcons = {{"Sarvam AI":"🤖","Krutrim":"⚡","Quantiphi":"📊","Fractal Analytics":"🔬","Razorpay":"💳","Freshworks":"🌿","Zerodha":"📈","Mad Street Den":"👁️","Sigmoid":"🔄","upGrad":"🎓"}};
let selectedCompany = null;

// Build company grid
const grid = document.getElementById('companyGrid');
companies.forEach(name => {{
  const p   = profiles[name];
  const div = document.createElement('div');
  div.className = 'company-card';
  div.innerHTML = `<div class="company-logo">${{companyIcons[name]||'🏢'}}</div><div class="company-name">${{name}}</div><div class="company-type">${{p.style}}</div>`;
  div.onclick   = () => selectCompany(name, div);
  grid.appendChild(div);
}});

function selectCompany(name, el) {{
  document.querySelectorAll('.company-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  selectedCompany = name;
  const p = profiles[name];
  document.getElementById('companyDetail').style.display = 'block';
  document.getElementById('companyFocus').innerHTML = p.focus.map(f => `<span class="focus-tag">${{f}}</span>`).join('');
  document.getElementById('companyTips').textContent = '💡 ' + p.tips;
  document.getElementById('startBtn').disabled = false;
}}

async function startCompanyInterview() {{
  if (!selectedCompany) {{ alert('Please select a company.'); return; }}
  const name   = document.getElementById('nameInput').value.trim() || 'Candidate';
  const skills = document.getElementById('skillsInput').value.split(',').map(s=>s.trim()).filter(Boolean);
  const round  = document.getElementById('roundType').value;
  const count  = parseInt(document.getElementById('qCount').value);

  document.getElementById('generatingDiv').style.display = 'block';
  document.getElementById('startBtn').disabled = true;

  try {{
    const res  = await fetch('/api/company_questions', {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{ company: selectedCompany, round_type: round, count, name, skills }})
    }});
    const data = await res.json();
    if (data.session_id) {{
      window.location.href = '/interview/' + data.session_id;
    }} else {{
      alert('Failed to generate questions. Try again.');
    }}
  }} catch(e) {{
    alert('Error: ' + e.message);
  }}
  document.getElementById('generatingDiv').style.display = 'none';
  document.getElementById('startBtn').disabled = false;
}}
</script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


@app.route("/api/company_questions", methods=["POST"])
def api_company_questions():
    data       = request.get_json() or {}
    company    = data.get("company","")
    round_type = data.get("round_type","technical")
    count      = data.get("count", 20)
    name       = data.get("name","Candidate")
    skills     = data.get("skills",[])
    profile    = COMPANY_PROFILES.get(company,{})
    focus      = profile.get("focus",[])
    style      = profile.get("style","technical")
    tips       = profile.get("tips","")

    focus_str  = ", ".join(focus[:6])
    skills_str = ", ".join(skills[:10]) if skills else "General technical skills"

    round_instructions = {
        "technical":     "Generate technical coding and concept questions focused on their tech stack",
        "hr":            "Generate HR and behavioural questions specific to working at this company's culture",
        "system_design": "Generate system design questions relevant to this company's products and scale",
        "mixed":         "Generate a mix of technical, HR, and problem-solving questions"
    }.get(round_type, "Generate technical questions")

    prompt = f"""You are a senior interviewer at {company}, a {style} company.

CANDIDATE: {name} | Skills: {skills_str}
COMPANY FOCUS AREAS: {focus_str}
INTERVIEW STYLE: {style}
ROUND TYPE: {round_type}
INSTRUCTION: {round_instructions}
COMPANY CONTEXT: {tips}

Generate exactly {min(count, 20)} interview questions that {company} actually asks.
Make questions specific to {company}'s products, scale, and engineering culture.

Return ONLY a JSON array:
[{{"q":"question","answer":"detailed answer","level":1-3,"topic":"topic name","type":"{round_type}"}}]"""

    try:
        raw = groq_rotator.call(
            messages=[{"role":"user","content":prompt}],
            temperature=0.3, max_tokens=3000
        )
        if not raw: raise Exception("No response")
        raw = raw.strip()
        if "```" in raw: raw = re.sub(r"```(?:json)?","",raw).strip().rstrip("`").strip()
        raw = re.sub(r',\s*([}\]])', r'\1', raw)
        s = raw.find("["); e = raw.rfind("]") + 1
        if s == -1: raise Exception("No array")
        questions = json.loads(raw[s:e])
    except Exception as ex:
        print(f"  [Company] Question generation error: {ex}")
        questions = [
            {"q":f"Tell me about your experience with {f}","answer":"Describe your hands-on experience","level":2,"topic":f,"type":round_type}
            for f in focus[:count]
        ]

    # Create session
    session_id = str(uuid.uuid4())
    INTERVIEW_SESSIONS[session_id] = {
        "name":        name,
        "domain":      company + " Interview",
        "skills":      skills,
        "career_fit":  [f"{company} {style.title()} Role"],
        "education":   "",
        "status":      "ready",
        "is_company":  True,
        "company":     company,
        "round_type":  round_type,
        "questions": {
            "technical": [q for q in questions if q.get("type") in ("technical","system_design","mixed","")],
            "hr":        [q for q in questions if q.get("type") == "hr"],
            "aptitude":  [], "logical": [], "coding": []
        },
        "jobs":      [],
        "resources": {},
    }
    return jsonify({"session_id": session_id, "question_count": len(questions)})

if __name__ == "__main__":
    os.makedirs("interview_app", exist_ok=True)
    init_db()
    print("  [Upload] Resume upload → http://localhost:5000/upload")
    app.run(debug=False, port=5000, use_reloader=False)  # Security: debug OFF in production

# ── FREE AI PROVIDERS (no local GPU needed for deployment) ──
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")      # aistudio.google.com — 1500/day FREE
OPENROUTER_KEY    = os.environ.get("OPENROUTER_API_KEY", "")  # openrouter.ai — free models available
GEMINI_MODEL      = "gemini-1.5-flash"  # fastest free Gemini model