"""HireHub — a fictional job portal for the Speak-to-Apply demo."""
import json, os, secrets, sqlite3, time, uuid, base64, smtplib, logging, hmac
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

log = logging.getLogger("hirehub")
logging.basicConfig(level=logging.INFO)

BASE = Path(__file__).parent
DATA = Path(os.environ.get("DATA_DIR", BASE / "data"))
(DATA / "resumes").mkdir(parents=True, exist_ok=True)
JOBS = json.loads((BASE / "jobs.json").read_text())
JOBS_BY_ID = {j["id"]: j for j in JOBS}

PREFILL_SECRET = os.environ.get("PREFILL_SECRET", "dev-secret")
RECRUITER_PASSWORD = os.environ.get("RECRUITER_PASSWORD", "recruiter")
SENDER = os.environ.get("BREVO_SENDER_EMAIL", "")
EMAILS_PER_HOUR = int(os.environ.get("EMAILS_PER_HOUR", "40"))

app = FastAPI(title="HireHub")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
tpl = Jinja2Templates(directory=BASE / "templates")
tpl.env.globals["size_label"] = {"seed": "Seed", "seriesAB": "Series A–B", "scaleup": "Scale-up", "large": "Large company"}


def db():
    con = sqlite3.connect(DATA / "hirehub.db")
    con.row_factory = sqlite3.Row
    return con


with db() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS applications(id TEXT PRIMARY KEY, job_id TEXT, name TEXT, email TEXT,
        phone TEXT, linkedin TEXT, cover TEXT, answers TEXT, resume TEXT, source TEXT, created REAL, email_status TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS prefills(token TEXT PRIMARY KEY, job_id TEXT, data TEXT, resume TEXT, created REAL)""")


# ---------------- email ----------------
def confirmation_html(name, job, app_id):
    return f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#1f2430">
<div style="background:#2445d6;color:#fff;padding:18px 24px;border-radius:10px 10px 0 0;font-size:20px;font-weight:bold">HireHub</div>
<div style="border:1px solid #e3e6ee;border-top:0;padding:24px;border-radius:0 0 10px 10px">
<p>Hi {name.split()[0] if name else 'there'},</p>
<p>Thanks for applying! We've received your application for:</p>
<p style="background:#f3f5fb;padding:14px;border-radius:8px"><b>{job['title']}</b><br>{job['company']} · {job['location']}</p>
<p>Application reference: <b>{app_id[:8].upper()}</b></p>
<p>The {job['company']} hiring team will review your profile. If there's a match, they'll reach out within 2–3 weeks.</p>
<p style="color:#7a8194;font-size:12px;margin-top:28px">HireHub is a demo job portal built for a course project. All companies and jobs are fictional.</p>
</div></div>"""


def _sent_last_hour():
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM applications WHERE created>? AND email_status='sent'", (time.time() - 3600,)).fetchone()[0]


def send_confirmation(to, name, job, app_id):
    if _sent_last_hour() >= EMAILS_PER_HOUR:
        return "rate-limited"
    subject = f"Application received: {job['title']} at {job['company']}"
    html = confirmation_html(name, job, app_id)
    key = os.environ.get("BREVO_API_KEY")
    try:
        if key:
            r = httpx.post("https://api.brevo.com/v3/smtp/email", timeout=20, headers={"api-key": key},
                           json={"sender": {"name": "HireHub", "email": SENDER}, "to": [{"email": to, "name": name}],
                                 "subject": subject, "htmlContent": html})
            r.raise_for_status()
            return "sent"
        if os.environ.get("BREVO_SMTP_KEY"):
            m = EmailMessage(); m["From"] = f"HireHub <{SENDER}>"; m["To"] = to; m["Subject"] = subject
            m.set_content("Your application was received."); m.add_alternative(html, subtype="html")
            with smtplib.SMTP("smtp-relay.brevo.com", 587, timeout=20) as s:
                s.starttls(); s.login(os.environ["BREVO_SMTP_LOGIN"], os.environ["BREVO_SMTP_KEY"]); s.send_message(m)
            return "sent"
        return "not-configured"
    except Exception as e:
        log.exception("email failed")
        return f"failed: {str(e)[:120]}"


# ---------------- pages ----------------
@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = "", mode: str = "", city: str = "", level: str = ""):
    jobs = JOBS
    if q:
        ql = q.lower(); jobs = [j for j in jobs if ql in (j["title"] + j["company"] + j["sector"]).lower()]
    if mode: jobs = [j for j in jobs if j["work_mode"] == mode]
    if city: jobs = [j for j in jobs if j["city"] == city]
    if level: jobs = [j for j in jobs if j["level"] == level]
    cities = sorted({j["city"] for j in JOBS})
    levels = ["Associate Product Manager", "Product Manager", "Senior Product Manager", "Group Product Manager"]
    return tpl.TemplateResponse(request, "index.html", dict(jobs=jobs, q=q, mode=mode, city=city, level=level,
                                                            cities=cities, levels=levels, total=len(JOBS)))


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str, prefill: str = ""):
    job = JOBS_BY_ID.get(job_id) or _404()
    pf, has_resume = {}, False
    if prefill:
        with db() as c:
            row = c.execute("SELECT * FROM prefills WHERE token=? AND job_id=?", (prefill, job_id)).fetchone()
        if row and time.time() - row["created"] < 7 * 86400:
            pf = json.loads(row["data"]); has_resume = bool(row["resume"])
    return tpl.TemplateResponse(request, "job.html", dict(job=job, pf=pf, token=prefill if pf else "", has_resume=has_resume))


@app.get("/prefill-resume/{token}")
def prefill_resume(token: str):
    with db() as c:
        row = c.execute("SELECT resume FROM prefills WHERE token=?", (token,)).fetchone()
    if not row or not row["resume"]: _404()
    return FileResponse(DATA / "resumes" / row["resume"], media_type="application/pdf", filename="resume.pdf")


@app.post("/jobs/{job_id}/apply")
async def apply(job_id: str, name: str = Form(...), email: str = Form(...), phone: str = Form(""),
                linkedin: str = Form(""), cover: str = Form(""), token: str = Form(""),
                a0: str = Form(""), a1: str = Form(""), a2: str = Form(""), resume: Optional[UploadFile] = File(None)):
    job = JOBS_BY_ID.get(job_id) or _404()
    app_id = uuid.uuid4().hex
    resume_name, source = "", "manual"
    if resume is not None and resume.filename:
        data = await resume.read()
        if len(data) > 8_000_000: raise HTTPException(413, "Resume too large (max 8 MB)")
        resume_name = f"{app_id}.pdf"; (DATA / "resumes" / resume_name).write_bytes(data)
    if token:
        with db() as c:
            row = c.execute("SELECT resume FROM prefills WHERE token=?", (token,)).fetchone()
        if row:
            source = "speak-to-apply"
            if not resume_name and row["resume"]:
                resume_name = row["resume"]
    status = send_confirmation(email.strip(), name.strip(), job, app_id)
    answers = dict(zip(job["screening"], [a0, a1, a2]))
    with db() as c:
        c.execute("INSERT INTO applications VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (app_id, job_id, name, email, phone, linkedin, cover, json.dumps(answers), resume_name, source, time.time(), status))
    return RedirectResponse(f"/applied/{app_id}", status_code=303)


@app.get("/applied/{app_id}", response_class=HTMLResponse)
def applied(request: Request, app_id: str):
    with db() as c:
        row = c.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    if not row: _404()
    return tpl.TemplateResponse(request, "applied.html", dict(a=row, job=JOBS_BY_ID[row["job_id"]]))


security = HTTPBasic()


def recruiter_auth(cred: HTTPBasicCredentials = Depends(security)):
    if not hmac.compare_digest(cred.password, RECRUITER_PASSWORD):
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})


@app.get("/recruiter", response_class=HTMLResponse, dependencies=[Depends(recruiter_auth)])
def recruiter(request: Request):
    with db() as c:
        rows = c.execute("SELECT * FROM applications ORDER BY created DESC LIMIT 200").fetchall()
    apps = [dict(r) | {"job": JOBS_BY_ID.get(r["job_id"], {}), "answers": json.loads(r["answers"] or "{}"),
                       "when": time.strftime("%d %b %H:%M", time.localtime(r["created"]))} for r in rows]
    return tpl.TemplateResponse(request, "recruiter.html", dict(apps=apps))


@app.get("/recruiter/resume/{app_id}", dependencies=[Depends(recruiter_auth)])
def recruiter_resume(app_id: str):
    with db() as c:
        row = c.execute("SELECT resume FROM applications WHERE id=?", (app_id,)).fetchone()
    if not row or not row["resume"]: _404()
    return FileResponse(DATA / "resumes" / row["resume"], media_type="application/pdf")


# ---------------- API used by Speak-to-Apply ----------------
@app.get("/api/jobs")
def api_jobs():
    return JOBS


@app.post("/api/prefill")
async def api_prefill(request: Request, data: str = Form(...), resume: Optional[UploadFile] = File(None)):
    if not hmac.compare_digest(request.headers.get("x-prefill-secret", ""), PREFILL_SECRET):
        raise HTTPException(403, "bad secret")
    d = json.loads(data)
    job_id = d.get("job_id")
    if job_id not in JOBS_BY_ID: raise HTTPException(400, "unknown job")
    token = secrets.token_urlsafe(16)
    resume_name = ""
    if resume is not None:
        resume_name = f"pf-{token}.pdf"; (DATA / "resumes" / resume_name).write_bytes(await resume.read())
    with db() as c:
        c.execute("INSERT INTO prefills VALUES(?,?,?,?,?)", (token, job_id, json.dumps(d), resume_name, time.time()))
    return {"token": token, "path": f"/jobs/{job_id}?prefill={token}"}


@app.get("/healthz")
def health():
    return {"ok": True}


def _404():
    raise HTTPException(404, "Not found")
