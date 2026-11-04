"""Groq wrappers (open-weight gpt-oss + Whisper). MOCK_LLM=1 returns canned data for offline testing."""
import json, os, time, logging
import httpx

log = logging.getLogger("llm")
GROQ = "https://api.groq.com/openai/v1"
MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")
FALLBACK = os.environ.get("LLM_FALLBACK", "openai/gpt-oss-20b")
STT_MODEL = os.environ.get("STT_MODEL", "whisper-large-v3-turbo")


def mock() -> bool:
    return os.environ.get("MOCK_LLM") == "1" or not os.environ.get("GROQ_API_KEY")


def _headers():
    return {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}


def chat_json(system: str, user: str, temperature=0.3, max_tokens=4000) -> dict:
    last = None
    for model in (MODEL, FALLBACK):
        for attempt in range(2):
            try:
                r = httpx.post(f"{GROQ}/chat/completions", headers=_headers(), timeout=60, json={
                    "model": model, "temperature": temperature, "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    **({"reasoning_effort": "low"} if "gpt-oss" in model else {}),
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
                if r.status_code == 429:
                    last = "rate limited"; time.sleep(2 + attempt * 3); continue
                r.raise_for_status()
                out = json.loads(r.json()["choices"][0]["message"]["content"])
                if isinstance(out, list) and len(out) == 1 and isinstance(out[0], dict):
                    out = out[0]
                if not isinstance(out, dict):
                    raise ValueError("model returned non-object JSON")
                return out
            except Exception as e:
                last = e; log.warning("LLM %s failed: %s", model, e)
    raise RuntimeError(f"LLM unavailable: {last}")


def transcribe(data: bytes, filename: str) -> str:
    if mock():
        return ("Since that resume, I joined Northwind Analytics in Paris as a product manager in January 2025. "
                "I own the self-serve onboarding flow and we raised activation from 22 to 31 percent in six months. "
                "I also launched an AI assistant for report building used by about 4,000 customers.")
    r = httpx.post(f"{GROQ}/audio/transcriptions", headers=_headers(), timeout=180,
                   files={"file": (filename, data)}, data={"model": STT_MODEL, "response_format": "json", "language": "en"})
    r.raise_for_status()
    return r.json()["text"].strip()


# ---------------- canned outputs for MOCK mode ----------------
MOCK_PROFILE = {
    "name": "Alex Martin", "email": "alex.martin@example.com", "phone": "+33 6 12 34 56 78", "location": "Paris, France",
    "linkedin": "linkedin.com/in/alexmartin-demo", "headline": "Product Manager · Data & AI products",
    "summary": "Product manager with 4 years across analytics and B2B SaaS. Ships data-heavy features with engineering and design, and measures impact through activation and retention.",
    "total_years_experience": 4, "education_tier": "top",
    "experience": [
        {"title": "Product Analyst", "company": "Blue Harbor Payments", "location": "Lyon", "start": "2021", "end": "2023",
         "bullets": ["Built the checkout funnel dashboard used by 3 product squads", "Ran 20+ A/B tests on payment flows"]},
        {"title": "Associate Product Manager", "company": "Kestrel Software", "location": "Paris", "start": "2023", "end": "2024",
         "bullets": ["Owned the reporting module roadmap", "Ran customer interviews with 30 B2B clients"]}],
    "education": [{"degree": "MSc Management", "school": "École de Commerce (demo)", "year": "2021"}],
    "skills": ["Product discovery", "SQL", "A/B testing", "Roadmapping", "Figma", "Python"],
    "languages": ["English (fluent)", "French (native)"], "achievements": []}


def mock_analyze():
    return {"profile": MOCK_PROFILE, "questions": [
        {"id": "q1", "question": "Your Kestrel role has no outcome metric. Which best describes your impact?",
         "options": ["Grew usage / adoption", "Cut costs or time", "Improved revenue", "Skip"]},
        {"id": "q2", "question": "How big was the team you worked with at Kestrel?",
         "options": ["1–5 people", "6–15 people", "16+ people", "Skip"]}]}


def mock_build(profile, addendum):
    p = json.loads(json.dumps(profile))
    changes = []
    if addendum:
        p["experience"].append({"title": "Product Manager", "company": "Northwind Analytics", "location": "Paris",
                                "start": "Jan 2025", "end": "Present",
                                "bullets": ["Own self-serve onboarding; raised activation from 22% to 31% in six months",
                                            "Launched an AI report-building assistant used by ~4,000 customers"]})
        p["total_years_experience"] = 5
        p["experience"][1]["end"] = "Dec 2024"
        changes += [{"what": "Added new role: Product Manager at Northwind Analytics (2025–Present)", "source": "your voice note"},
                    {"what": "Ended Kestrel Software role in Dec 2024", "source": "your voice note"}]
    p["experience"].sort(key=lambda e: e["end"] == "Present", reverse=True)
    p["experience"][-1]["bullets"][0] = "Owned the reporting module roadmap, growing weekly active usage"
    p["skills"] = p["skills"] + ["Onboarding optimisation"]
    p["headline"] = "Product Manager · Onboarding, Data & AI"
    changes.append({"what": "Added usage-growth framing to the Kestrel roadmap bullet", "source": "your answers"})
    return {"profile": p, "changes": changes}


def mock_tailor(profile, job):
    first = profile.get("name", "").split()[0] if profile.get("name") else ""
    return {"summary": profile.get("summary", ""),
            "cover": f"Dear {job['company']} team,\n\nI'm excited to apply for the {job['title']} role. In my recent work I owned data-heavy product areas end to end, ran discovery with users and shipped measurable improvements in activation. I'd love to bring that same approach to {job['company']}.\n\nBest regards,\n{profile.get('name','')}",
            "answers": ["Yes, I am authorised to work in France.", "French: native", f"{job['company']}'s focus on {job['sector'].lower()} matches my experience and interests."]}
