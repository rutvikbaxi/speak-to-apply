"""Transparent fit score out of 10: 60% requirements match + 40% preference match."""
import json

SECTOR_WORDS = {
    "Fintech": ["fintech", "bank", "payment", "credit", "lending", "finance", "financial", "american express", "amex", "insurance", "risk"],
    "Healthtech": ["health", "medical", "clinic", "patient", "pharma", "hospital"],
    "E-commerce": ["e-commerce", "ecommerce", "retail", "marketplace", "checkout", "shop", "consumer"],
    "B2B SaaS": ["saas", "b2b", "enterprise", "platform", "software", "erp", "crm"],
    "Mobility": ["logistics", "delivery", "supply chain", "transport", "mobility", "fleet", "delhivery"],
    "AI / ML": [" ai", "ai ", "machine learning", " ml", "llm", "rlhf", "data scien", "model", "evals", "nlp"],
    "Luxury & Retail": ["luxury", "fashion", "retail", "beauty", "premium", "omnichannel"],
    "Energy & Climate": ["energy", "climate", "sustainab", "solar", "grid", "carbon", "iot"],
}
LEVEL_KEYS = {"Associate Product Manager": "APM", "Product Manager": "PM", "Senior Product Manager": "Senior PM", "Group Product Manager": "Group PM"}
FRENCH_RANK = {"none": 0, "basic": 1, "b2": 2, "c1": 3, "native": 3}


def _french_needed(lang: str) -> int:
    l = lang.lower()
    return 3 if "c1" in l else 2 if "b2" in l else 0


def _french_have(prefs) -> int:
    v = (prefs.get("french") or "").lower()
    return 3 if ("c1" in v or "native" in v) else 2 if "b2" in v else 1 if "basic" in v or "a1" in v or "a2" in v else 0


def _status(s):  # s 0-10
    return "good" if s >= 8 else "ok" if s >= 5 else "bad"


def score_job(profile: dict, prefs: dict, job: dict) -> dict:
    text = json.dumps(profile).lower()
    yrs = float(profile.get("total_years_experience") or 0)
    f = []

    # ---- requirements (60%) ----
    lo, hi = job["min_years"], job["max_years"]
    mid = (lo + hi) / 2
    if lo <= yrs <= hi + 1: s, note = (10 if abs(yrs - mid) <= (hi - lo) / 4 + 0.5 else 8.5), f"{yrs:g} yrs fits {lo}–{hi}"
    elif yrs < lo: s, note = (6 if lo - yrs <= 1 else 3 if lo - yrs <= 2.5 else 1), f"{yrs:g} yrs vs {lo}+ needed"
    else: s, note = (7 if yrs - hi <= 3 else 4), f"{yrs:g} yrs, may be over-qualified"
    f.append(dict(key="exp", label="Experience", group="req", w=0.40, score=s, note=note))

    words = SECTOR_WORDS.get(job["sector"], [])
    hits = [w.strip() for w in words if w in f" {text} "]
    pm = any(k in text for k in ["product manager", "product owner", "project manager", "product lead", "apm", "product analyst"])
    req_text = " ".join(job["requirements"] + job["nice_to_have"] + [job["title"]]).lower()
    skill_hits = [k for k in ["sql", "a/b", "b2b", "discovery", "llm", "data", "technical", "payments", "checkout", "onboarding", "growth", "mobile", "pricing", "marketplace", "platform", "integrations", "personalisation"]
                  if k in req_text and k in text]
    s = (3 if not hits else 5.5 if len(hits) == 1 else 7) + (2 if pm else 0) + min(len(skill_hits), 2) * 0.5
    f.append(dict(key="domain", label="Domain & skills", group="req", w=0.30, score=min(s, 10),
                  note=(f"{job['sector']} experience" if hits else f"No {job['sector']} background") + (" · product role" if pm else "")))

    top = (profile.get("education_tier") == "top")
    ped = job["pedigree"]
    s = 10 if ped == "none" or top else (6 if ped == "preferred" else 2)
    f.append(dict(key="pedigree", label="Education / pedigree", group="req", w=0.15, score=s,
                  note={"none": "No school requirement", "preferred": "Top school preferred", "required": "Top school required"}[ped] + (" ✓" if top and ped != "none" else "")))

    need, have = _french_needed(job["language"]), _french_have(prefs)
    s = 10 if have >= need else (5 if have == need - 1 else 1)
    f.append(dict(key="lang", label="Language", group="req", w=0.15, score=s,
                  note=job["language"] if need == 0 else f'{job["language"]} needed · you: {prefs.get("french") or "not set"}'))

    # ---- preferences (40%) ----
    want_sal = int(prefs.get("min_salary") or 0)
    s = 10 if not want_sal or job["salary_min"] >= want_sal else 8 if job["salary_max"] >= want_sal else (4 if job["salary_max"] >= 0.9 * want_sal else 0)
    f.append(dict(key="pay", label="Pay", group="pref", w=0.25, score=s, note=f"€{job['salary_min']}–{job['salary_max']}k" + (f" vs €{want_sal}k+" if want_sal else "")))

    locs = prefs.get("locations") or []
    if not locs or "Anywhere in France" in locs or job["city"] in locs: ls = 10
    elif job["work_mode"] == "Remote": ls = 9
    else: ls = 0
    f.append(dict(key="loc", label="Location", group="pref", w=0.20, score=ls, note=job["location"]))

    modes = prefs.get("work_modes") or []
    f.append(dict(key="mode", label="Remote / office", group="pref", w=0.20 if modes else 0, score=10 if not modes or job["work_mode"] in modes else 1, note=job["work_mode_label"]))

    sizes = prefs.get("sizes") or []
    f.append(dict(key="size", label="Company size", group="pref", w=0.15 if sizes else 0, score=10 if not sizes or job["company_size"] in sizes else 3, note=job["company_size_label"]))

    ctype = prefs.get("company_type") or "Either"
    f.append(dict(key="type", label="Startup / MNC", group="pref", w=0.10 if ctype != "Either" else 0, score=10 if ctype == "Either" or ctype == job["company_type"] else 3, note=job["company_type"]))

    lvl = prefs.get("target_level")
    if lvl and lvl != "Not sure":
        s = 10 if LEVEL_KEYS[job["level"]] == lvl else 4
        f.append(dict(key="level", label="Target level", group="pref", w=0.25, score=s, note=job["level"]))

    def group(g):
        items = [x for x in f if x["group"] == g and x["w"] > 0]; tw = sum(x["w"] for x in items)
        return sum(x["score"] * x["w"] for x in items) / tw
    req, pref = group("req"), group("pref")
    total = round(0.6 * req + 0.4 * pref, 1)
    for x in f: x["status"] = _status(x["score"])
    good = [x["label"].lower() for x in f if x["status"] == "good"][:3]
    bad = [x["label"].lower() for x in f if x["status"] == "bad"][:2]
    reason = ("Strong on " + ", ".join(good) if good else "Partial match") + ("; gaps: " + ", ".join(bad) if bad else "") + "."
    return {"job": job, "score": total, "req_score": round(req, 1), "pref_score": round(pref, 1), "factors": f, "reason": reason}


def rank_jobs(profile, prefs, jobs):
    ranked = sorted((score_job(profile, prefs, j) for j in jobs), key=lambda r: -r["score"])
    seen, out, rest = set(), [], []
    for r in ranked:  # one job per company first, so the top 5 is diverse
        (rest if r["job"]["company"] in seen else out).append(r); seen.add(r["job"]["company"])
    return out + rest
