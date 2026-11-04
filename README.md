# Speak-to-Apply (MVP)

A voice-first resume builder that recommends jobs and pre-fills applications. **You always click Submit yourself.**

Built as a lean-startup course prototype. Two web apps:

| App | Port | What it does |
|---|---|---|
| `speak/` **Speak-to-Apply** | 8002 | Paste LinkedIn text, upload a PDF, or dictate → 0–3 multiple-choice follow-ups + job preferences → voice "anything new?" → editable resume + PDF → top 5 jobs with a fit score out of 10 → pre-filled application |
| `hirehub/` **HireHub** | 8001 | Fictional job portal with 30 Product Manager jobs in France. Application form, pre-fill API, confirmation email (Brevo), recruiter view at `/recruiter` |

**Fit score** = 60% requirements match (experience, domain and skills, education, language) + 40% preference match (pay, location, remote/office, company size, startup/MNC, level).

## Stack (open-weight models, free tiers)
- FastAPI + vanilla JS, SQLite
- Groq: **Whisper-large-v3-turbo** (speech-to-text), **gpt-oss-120b** (structuring, follow-ups, tailoring)
- PyMuPDF (PDF reading and resume PDF), Brevo (email)

## Run on a Mac
1. Put your keys in `../hirehub-keys/keys.env` (next to this folder):
   ```
   GROQ_API_KEY=...
   BREVO_API_KEY=...
   BREVO_SENDER_EMAIL=you@example.com
   ```
2. Double-click `start.command` (or run `./start.command`). It opens http://localhost:8002.

Offline test without keys: `cd speak && MOCK_LLM=1 uvicorn app:app --port 8002` (with HireHub running on 8001).

## Other pages
- Recruiter view: http://localhost:8001/recruiter (user `recruiter`, password `hirehub-demo`)
- Build-measure-learn metrics: http://localhost:8002/stats

## Hosting
Each app has a `Dockerfile`. `deploy.py` deploys both to Hugging Face Docker Spaces, which now needs an HF PRO plan.

See `NEXT_ITERATION.md` for planned changes. All companies and jobs in HireHub are fictional.
