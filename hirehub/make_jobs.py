"""Generates 30 fictional Product Manager jobs in France with varied factors."""
import json, random
random.seed(7)

SECTORS = {
  "Fintech": ("payments, lending and finance tools", ["Experience with payments, banking or regulated products", "Comfort with KPIs like conversion, fraud rate and NPS"]),
  "Healthtech": ("digital health for patients and clinicians", ["Understanding of regulated environments (GDPR, health data)", "Empathy for clinical users and patient journeys"]),
  "E-commerce": ("online retail and marketplaces", ["Strong A/B testing and funnel optimisation skills", "Experience with checkout, search or recommendations"]),
  "B2B SaaS": ("software for businesses", ["Experience with B2B discovery and customer interviews", "Ability to work with sales and customer success on roadmap"]),
  "Mobility": ("transport, logistics and delivery", ["Experience with operations-heavy or logistics products", "Comfort with data on routing, supply and demand"]),
  "AI / ML": ("AI-native products and LLM tools", ["Hands-on familiarity with LLMs, evals or ML products", "Ability to define quality metrics for AI features"]),
  "Luxury & Retail": ("premium retail and clienteling", ["Taste for premium customer experience", "Experience with omnichannel (store + online) journeys"]),
  "Energy & Climate": ("energy transition and climate tech", ["Interest in sustainability and energy markets", "Experience with IoT or data-heavy platforms"]),
}

COMPANIES = [
  ("Lumio Pay", "Fintech", "seriesAB", "startup"), ("Banque Azur Digital", "Fintech", "large", "MNC"),
  ("Créditel", "Fintech", "scaleup", "startup"), ("Vitalis Santé", "Healthtech", "seriesAB", "startup"),
  ("MedOrbit", "Healthtech", "seed", "startup"), ("Pharmalys Group", "Healthtech", "large", "MNC"),
  ("Panier Vert", "E-commerce", "scaleup", "startup"), ("Marché Plus", "E-commerce", "large", "MNC"),
  ("Atelier Nova", "B2B SaaS", "seriesAB", "startup"), ("Fluxa", "B2B SaaS", "scaleup", "startup"),
  ("Quantaro Systems", "B2B SaaS", "large", "MNC"), ("Mobilia", "Mobility", "scaleup", "startup"),
  ("TransEuropa Logistics", "Mobility", "large", "MNC"), ("Cobalt Labs", "AI / ML", "seed", "startup"),
  ("Sablier AI", "AI / ML", "seriesAB", "startup"), ("Neuronis", "AI / ML", "scaleup", "startup"),
  ("Maison Orée", "Luxury & Retail", "large", "MNC"), ("Rive Gauche Retail", "Luxury & Retail", "scaleup", "MNC"),
  ("Solenne Energy", "Energy & Climate", "seriesAB", "startup"), ("Voltaire Grid", "Energy & Climate", "large", "MNC"),
]
SIZE_LABEL = {"seed": "Seed (under 20 people)", "seriesAB": "Series A–B (50–200)", "scaleup": "Scale-up (200–1,000)", "large": "Large company (1,000+)"}

LEVELS = [  # title, min_y, max_y, salary band
  ("Associate Product Manager", 0, 2, (40, 55)),
  ("Product Manager", 2, 5, (55, 75)),
  ("Senior Product Manager", 5, 8, (75, 100)),
  ("Group Product Manager", 8, 15, (100, 135)),
]
CITIES = ["Paris"] * 9 + ["Lyon", "Lyon", "Toulouse", "Bordeaux", "Lille", "Nantes", "Sophia Antipolis", "Marseille"]
MODES = ["Remote (France)", "Hybrid (2 days office)", "Hybrid (3 days office)", "On-site"]
FOCUS = ["Payments & checkout", "Onboarding & growth", "Core platform", "Data & insights", "Mobile app", "Pricing & monetisation",
         "Marketplace", "AI assistant", "Partner integrations", "Customer experience", "Internal tools", "Personalisation"]

jobs = []
for i in range(30):
    comp, sector, size, ctype = COMPANIES[i % len(COMPANIES)]
    lvl = LEVELS[[0, 1, 1, 2, 1, 2, 3, 0, 1, 2][i % 10]]
    title, miny, maxy, (smin, smax) = lvl
    focus = FOCUS[i % len(FOCUS)]
    city = CITIES[(i * 5) % len(CITIES)]
    mode = MODES[(i * 3 + (1 if ctype == "MNC" else 0)) % 4]
    if mode.startswith("Remote"):
        city_display = f"Remote · {city} HQ"
    else:
        city_display = city
    # salary tweaks: Paris & MNC pay more, seed less
    bump = (5 if city == "Paris" else 0) + (5 if ctype == "MNC" else 0) - (8 if size == "seed" else 0)
    sal = (smin + bump, smax + bump)
    pedigree = ["none", "preferred", "none", "required", "preferred"][i % 5]
    if ctype == "MNC" and pedigree == "none":
        pedigree = "preferred"
    french = ["English only", "French B2", "French C1 / native", "English only", "French B2"][(i * 2) % 5]
    if ctype == "startup" and sector in ("AI / ML", "B2B SaaS"):
        french = "English only"
    blurb, sector_reqs = SECTORS[sector]
    reqs = [f"{miny}+ years of product management experience" if miny else "0–2 years in product, consulting, engineering or analytics",
            sector_reqs[0], "Strong analytical skills: SQL or comfort with dashboards",
            "Excellent written communication and stakeholder management"]
    if pedigree == "required":
        reqs.append("Degree from a top engineering or business school (Grande École, IIT/IIM or equivalent) required")
    elif pedigree == "preferred":
        reqs.append("Grande École / top-tier engineering or business degree preferred")
    if french != "English only":
        reqs.append(f"{french} French (team language is French)")
    else:
        reqs.append("Fluent English (team language is English); French is a plus")
    if miny >= 8:
        reqs.append("Experience managing a team of PMs")
    nice = [sector_reqs[1], "Technical background (engineering, data science) is a plus"]
    resp = [f"Own the roadmap for {focus.lower()} end to end",
            "Run discovery with users and turn insights into clear specs",
            "Work daily with engineering, design and data to ship fast",
            "Define success metrics and report impact to leadership"]
    jobs.append({
        "id": f"pm-{i+1:02d}",
        "title": f"{title} – {focus}",
        "level": title, "min_years": miny, "max_years": maxy,
        "company": comp, "sector": sector, "company_blurb": f"{comp} builds {blurb} in France and across Europe.",
        "company_size": size, "company_size_label": SIZE_LABEL[size], "company_type": ctype,
        "city": city, "location": city_display, "work_mode": mode.split(" (")[0], "work_mode_label": mode,
        "salary_min": sal[0], "salary_max": sal[1],
        "pedigree": pedigree, "language": french,
        "requirements": reqs, "nice_to_have": nice, "responsibilities": resp,
        "screening": ["Are you authorised to work in France (or need visa sponsorship)?",
                      "What is your French language level?",
                      f"Why are you interested in {comp}?"],
        "posted_days_ago": (i * 7) % 21 + 1,
    })

json.dump(jobs, open("jobs.json", "w"), indent=1, ensure_ascii=False)
from collections import Counter
for k in ["level", "work_mode", "company_size", "company_type", "city", "pedigree", "language", "sector"]:
    print(k, dict(Counter(j[k] for j in jobs)))
