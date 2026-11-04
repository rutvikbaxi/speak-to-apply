"""Speak-to-Apply — voice/LinkedIn/PDF to resume, job recommendations and pre-filled applications."""
import json, os, re, sqlite3, time, logging
from pathlib import Path

import httpx, pymupdf
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

import llm
from scoring import rank_jobs

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("speak")
BASE = Path(__file__).parent
DATA = Path(os.environ.get("DATA_DIR", BASE / "data")); DATA.mkdir(parents=True, exist_ok=True)
HIREHUB_URL = os.environ.get("HIREHUB_URL", "http://localhost:8001").rstrip("/")
PREFILL_SECRET = os.environ.get("PREFILL_SECRET", "dev-secret")
jenv = Environment(loader=FileSystemLoader(BASE / "templates"), autoescape=select_autoescape())

app = FastAPI(title="Speak-to-Apply")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

with sqlite3.connect(DATA / "events.db") as c:
    c.execute("CREATE TABLE IF NOT EXISTS events(t REAL, sid TEXT, name TEXT, props TEXT)")

_jobs_cache = {"t": 0, "jobs": None}


def get_jobs():
    if _jobs_cache["jobs"] and time.time() - _jobs_cache["t"] < 600:
        return _jobs_cache["jobs"]
    try:
        jobs = httpx.get(f"{HIREHUB_URL}/api/jobs", timeout=15).json()
    except Exception:
        log.warning("HireHub unreachable, using bundled jobs.json")
        jobs = json.loads((BASE / "jobs.json").read_text())
    _jobs_cache.update(t=time.time(), jobs=jobs)
    return jobs


@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE / "static" / "index.html").read_text()


# ---------------- intake ----------------
@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    data = await audio.read()
    if len(data) > 24_000_000: raise HTTPException(413, "Recording too long")
    try:
        return {"text": llm.transcribe(data, audio.filename or "audio.webm")}
    except Exception as e:
        log.exception("stt"); raise HTTPException(502, f"Transcription failed: {e}")


@app.post("/api/pdf-text")
async def pdf_text(file: UploadFile = File(...)):
    data = await file.read()
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
        text = "\n".join(p.get_text() for p in doc)[:30000]
    except Exception:
        raise HTTPException(400, "Could not read that PDF")
    return {"text": text, "pages": len(doc)}


PROFILE_SCHEMA = """{
 "name": str, "email": str, "phone": str, "location": str, "linkedin": str,
 "headline": str (short, e.g. "Product Manager · Fintech & AI"),
 "summary": str (2-3 sentences, first person implied, no "I"),
 "total_years_experience": number (full-time professional years only; exclude internships and education),
 "education_tier": "top" | "other" ("top" = Grande École, IIT, IIM, Ivy/Oxbridge, INSEAD/HEC/ESSEC-level or similar),
 "experience": [{"title": str, "company": str, "location": str, "start": str, "end": str ("Present" if current), "bullets": [str]}] (most recent first),
 "education": [{"degree": str, "school": str, "year": str}],
 "skills": [str], "languages": [str], "achievements": [str]
}"""

RULES = """Rules:
- NEVER invent facts, employers, dates, numbers or skills. Use only what the sources say. Leave a field "" or [] if unknown.
- LinkedIn copy-paste text is messy (menus, "Show all", reactions, other people's posts). Ignore that noise.
- Bullets: start with a strong verb, keep the person's real numbers, max ~25 words each.
- Every bullet must be traceable to a specific statement in the sources. Write only as many bullets as the facts support (1 is fine). Do NOT pad with generic duties ("defined roadmap", "collaborated with teams") that the sources don't state.
- Do not upgrade claims: "worked on X" must not become "reduced X" or "led X".
- Write in English."""


@app.post("/api/analyze")
async def analyze(req: Request):
    b = await req.json()
    sources = {k: (b.get(k) or "")[:20000] for k in ("linkedin", "pdf", "dictation")}
    if not any(v.strip() for v in sources.values()):
        raise HTTPException(400, "Please add at least one source")
    if llm.mock():
        return llm.mock_analyze()
    system = f"""You turn raw career information into a structured profile, and decide whether any follow-up questions are needed.
Return JSON: {{"profile": PROFILE, "questions": [{{"id": "q1", "question": str, "options": [str, str, str, "Skip"]}}]}}
PROFILE schema: {PROFILE_SCHEMA}
{RULES}
Follow-up questions:
- Ask 0 to 3 multiple-choice questions ONLY for important gaps that would clearly improve the resume (e.g. a recent role with no outcome, a missing date range, unclear seniority/team size, missing education).
- If the information is already good enough, return "questions": [].
- Each question has 3 concrete options plus "Skip". Keep questions short and specific to this person.
- Ask about career substance only (outcomes, scope, team size, seniority, dates). NEVER ask for contact details (email, phone, address) and never put guessed personal data in options.
- Options must be general ranges or categories (e.g. "Cut drop-off by under 10%", "10–25%", "Over 25%"), not invented specifics."""
    user = f"Job seeker preferences (for context): {json.dumps(b.get('prefs', {}))}\n\n" + "\n\n".join(
        f"=== {k.upper()} ===\n{v}" for k, v in sources.items() if v.strip())
    try:
        out = llm.chat_json(system, user)
    except Exception as e:
        raise HTTPException(502, str(e))
    out["questions"] = [q for q in (out.get("questions") or []) if not re.search(r"email|phone|address|contact", q.get("question", ""), re.I)][:3]
    return _fix_years(out)


@app.post("/api/build")
async def build(req: Request):
    b = await req.json()
    profile, addendum, answers = b.get("profile") or {}, (b.get("addendum") or "").strip(), b.get("answers") or []
    if llm.mock():
        return llm.mock_build(profile, addendum)
    system = f"""You finalise a resume profile. Merge the draft profile with the person's multiple-choice answers and any NEW INFORMATION they dictated (e.g. a new job since their old resume).
Return JSON: {{"profile": PROFILE, "changes": [str]}}
PROFILE schema: {PROFILE_SCHEMA}
{RULES}
- Answers marked "Skip" are ignored. Use answers only to sharpen wording of existing items. They are ranges/categories, so phrase them as such (e.g. "cut drop-off by 10–25%"); never turn them into exact numbers.
- Never add contact details that are not in the draft profile.
- Add new roles/projects from NEW INFORMATION in the right chronological position; if a new role starts after a role marked "Present", end the older role.
- Tune headline and summary toward their target: {json.dumps(b.get('prefs', {}))}.
- "changes": 2-6 short plain-English notes of what you added or changed vs the draft (e.g. "Added Product Manager at X (2025–Present)")."""
    user = f"DRAFT PROFILE:\n{json.dumps(profile)}\n\nMULTIPLE-CHOICE ANSWERS:\n{json.dumps(answers)}\n\nNEW INFORMATION (dictated):\n{addendum or '(none)'}"
    try:
        out = llm.chat_json(system, user)
    except Exception as e:
        raise HTTPException(502, str(e))
    out["changes"] = [c for c in out.get("changes", []) if "years of experience" not in c.lower()]
    return _fix_years(out)


# ---------------- years of experience (computed, not trusted to the LLM) ----------------
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _ym(s, end=False):
    s = (s or "").strip().lower()
    if not s: return None
    if s in ("present", "current", "now", "today", "aujourd'hui"): t = time.localtime(); return t.tm_year * 12 + t.tm_mon
    y = re.search(r"(19|20)\d\d", s)
    if not y: return None
    m = next((v for k, v in MONTHS.items() if k in s), 12 if end else 1)
    return int(y.group()) * 12 + m


def compute_years(profile):
    spans = []
    for e in profile.get("experience") or []:
        if re.search(r"intern|stagiaire|apprenti|trainee", (e.get("title") or "").lower()): continue
        a, b = _ym(e.get("start")), _ym(e.get("end"), end=True)
        if a and b and b >= a: spans.append((a, b))
    spans.sort(); months, cur = 0, None
    for a, b in spans:  # merge overlaps
        if cur and a <= cur[1]: cur = (cur[0], max(cur[1], b))
        else:
            if cur: months += cur[1] - cur[0]
            cur = (a, b)
    if cur: months += cur[1] - cur[0]
    return round(months / 12, 1) if spans else profile.get("total_years_experience") or 0


def _fix_years(out):
    if out.get("profile"): out["profile"]["total_years_experience"] = compute_years(out["profile"])
    return out


# ---------------- resume PDF ----------------
def render_resume_pdf(profile: dict) -> bytes:
    if os.environ.get("PDF_ENGINE") == "weasyprint":
        try:
            from weasyprint import HTML
            return HTML(string=jenv.get_template("resume.html").render(p=profile), base_url=str(BASE)).write_pdf()
        except Exception:
            log.warning("WeasyPrint unavailable, using PyMuPDF")
    # PyMuPDF renderer: no system dependencies, works on macOS/Windows/Linux out of the box
    import io
    story = pymupdf.Story(html=jenv.get_template("resume_simple.html").render(p=profile))
    buf = io.BytesIO(); w = pymupdf.DocumentWriter(buf)
    page = pymupdf.paper_rect("a4"); area = page + (42, 40, -42, -40)
    more = 1
    while more:
        dev = w.begin_page(page); more, _ = story.place(area); story.draw(dev); w.end_page()
    w.close()
    return buf.getvalue()


@app.post("/api/resume.pdf")
async def resume_pdf(req: Request):
    b = await req.json()
    pdf = render_resume_pdf(b.get("profile") or {})
    name = re.sub(r"[^A-Za-z0-9]+", "_", (b.get("profile") or {}).get("name", "resume")).strip("_") or "resume"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}_Resume.pdf"'})


# ---------------- jobs ----------------
@app.post("/api/recommend")
async def recommend(req: Request):
    b = await req.json()
    profile, prefs = b.get("profile") or {}, b.get("prefs") or {}
    ranked = rank_jobs(profile, prefs, get_jobs())[:5]
    if not llm.mock():
        try:
            brief = [{"id": r["job"]["id"], "title": r["job"]["title"], "company": r["job"]["company"], "sector": r["job"]["sector"],
                      "requirements": r["job"]["requirements"], "score": r["score"],
                      "factors": {f["label"]: f["status"] for f in r["factors"]}} for r in ranked]
            out = llm.chat_json(
                "For each job, write ONE short sentence (max 22 words) explaining the fit for this candidate, grounded in their profile and the factor results. "
                "Never contradict the factor results (good/ok/bad). If any factor is 'bad', name that gap. Don't claim skills the candidate doesn't list. "
                'Return JSON {"reasons": {"<job id>": str}}.',
                f"CANDIDATE: {json.dumps({k: profile.get(k) for k in ('headline','total_years_experience','experience','skills','languages')})[:6000]}\n\nJOBS: {json.dumps(brief)}",
                max_tokens=2500)
            for r in ranked:
                r["reason"] = out.get("reasons", {}).get(r["job"]["id"], r["reason"])
        except Exception:
            log.warning("reason generation failed; using rule-based reasons")
    return {"jobs": ranked}


@app.post("/api/apply")
async def apply(req: Request):
    b = await req.json()
    profile, prefs, job_id = b.get("profile") or {}, b.get("prefs") or {}, b.get("job_id")
    job = next((j for j in get_jobs() if j["id"] == job_id), None)
    if not job: raise HTTPException(404, "Job not found")
    if llm.mock():
        t = llm.mock_tailor(profile, job)
    else:
        system = """You prepare a job application for a candidate. Never invent facts.
Return JSON {"summary": str, "cover": str, "answers": [str, str, str]}.
- summary: 2-3 sentence resume summary tailored to this job, using only real facts.
- Never upgrade claims beyond the profile wording (e.g. "worked on" must not become "reduced").
- cover: a warm, specific cover note of 110-160 words, plain text with line breaks, signed with the candidate's name. Mention 2 concrete, relevant achievements from the profile and why this company.
- answers: one short answer for each screening question, in order. Use the candidate's stated preferences for work authorisation and French level; if unknown, write "" (empty) rather than guessing."""
        user = f"CANDIDATE PROFILE: {json.dumps(profile)[:9000]}\nPREFERENCES: {json.dumps(prefs)}\nJOB: {json.dumps(job)}"
        try:
            t = llm.chat_json(system, user, temperature=0.5, max_tokens=3000)
        except Exception as e:
            raise HTTPException(502, str(e))
    tailored = dict(profile); tailored["summary"] = t.get("summary") or profile.get("summary", "")
    pdf = render_resume_pdf(tailored)
    data = {"job_id": job_id, "name": profile.get("name", ""), "email": b.get("email") or profile.get("email", ""),
            "phone": profile.get("phone", ""), "linkedin": profile.get("linkedin", ""),
            "cover": t.get("cover", ""), "answers": (t.get("answers") or [])[:3]}
    try:
        r = httpx.post(f"{HIREHUB_URL}/api/prefill", timeout=30, headers={"x-prefill-secret": PREFILL_SECRET},
                       data={"data": json.dumps(data)}, files={"resume": ("resume.pdf", pdf, "application/pdf")})
        r.raise_for_status()
    except Exception as e:
        log.exception("prefill"); raise HTTPException(502, f"Could not reach HireHub: {e}")
    return {"url": HIREHUB_URL + r.json()["path"], "cover": data["cover"]}


# ---------------- lean-startup metrics ----------------
@app.post("/api/event")
async def event(req: Request):
    b = await req.json()
    with sqlite3.connect(DATA / "events.db") as c:
        c.execute("INSERT INTO events VALUES(?,?,?,?)", (time.time(), str(b.get("sid", ""))[:40], str(b.get("name", ""))[:40], json.dumps(b.get("props", {}))[:2000]))
    return {"ok": True}


@app.get("/stats", response_class=HTMLResponse)
def stats():
    with sqlite3.connect(DATA / "events.db") as c:
        rows = c.execute("SELECT sid, name, t, props FROM events ORDER BY t").fetchall()
    steps = ["start", "intake_done", "resume_built", "resume_downloaded", "jobs_viewed", "apply_clicked"]
    funnel = {s: len({r[0] for r in rows if r[1] == s}) for s in steps}
    sources, qcounts, times = {}, [], []
    starts = {}
    for sid, name, t, props in rows:
        p = json.loads(props or "{}")
        if name == "start": starts[sid] = t
        if name == "intake_done":
            for s in p.get("sources", []): sources[s] = sources.get(s, 0) + 1
            qcounts.append(p.get("questions", 0))
        if name == "resume_built" and sid in starts: times.append(t - starts[sid])
    return jenv.get_template("stats.html").render(funnel=funnel, steps=steps, sources=sources,
        avg_q=(sum(qcounts) / len(qcounts)) if qcounts else 0, no_q=sum(1 for q in qcounts if q == 0),
        n_intake=len(qcounts), avg_t=(sum(times) / len(times) / 60) if times else 0)


@app.get("/healthz")
def health():
    return {"ok": True, "mock": llm.mock()}
