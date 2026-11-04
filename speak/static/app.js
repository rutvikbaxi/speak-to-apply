const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const S = { sid: Math.random().toString(36).slice(2), li: "", pdf: "", dictation: "", addendum: "", prefs: {}, profile: null, draft: null, questions: [], answers: {}, changes: [], diff: {} };
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;

function track(name, props = {}) { fetch("/api/event", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({sid:S.sid, name, props})}).catch(()=>{}); }
async function api(path, body) {
  const r = await fetch(path, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m } catch(e){} throw new Error(m); }
  return r.json();
}
function showErr(id, e) { $(id).innerHTML = e ? `<div class="err">⚠ ${esc(e.message || e)}</div>` : ""; }
function go(n) {
  for (let i = 1; i <= 5; i++) $("#s" + i).classList.toggle("hidden", i !== n);
  [...$("#stepper").children].forEach((d, i) => { d.className = i + 1 === n ? "on" : i + 1 < n ? "done" : ""; });
  window.scrollTo({top: 0, behavior: "smooth"});
}
document.querySelectorAll("[data-back]").forEach(b => b.onclick = () => go(+b.dataset.back));

/* ---------------- recorder ---------------- */
function Recorder(el, {max = 600, onText, label = "Tap to start talking"}) {
  el.innerHTML = `<button class="mic" title="Record">🎙️</button><div class="timer">${label}</div><div class="transcript hidden"></div>`;
  const btn = el.querySelector(".mic"), tm = el.querySelector(".timer"), tr = el.querySelector(".transcript");
  let mr, chunks = [], t0, iv, stream;
  const fmt = s => `${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,"0")}`;
  async function start() {
    try { stream = await navigator.mediaDevices.getUserMedia({audio: true}); }
    catch (e) { tm.textContent = "Microphone blocked. Allow mic access in your browser and try again."; return; }
    const type = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"].find(t => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || "";
    mr = new MediaRecorder(stream, type ? {mimeType: type} : {}); chunks = [];
    mr.ondataavailable = e => e.data.size && chunks.push(e.data);
    mr.onstop = upload; mr.start(1000); t0 = Date.now(); btn.classList.add("live"); btn.textContent = "■";
    iv = setInterval(() => { const s = (Date.now() - t0) / 1000; tm.textContent = `Recording ${fmt(s)} / ${fmt(max)} · tap to stop`; if (s >= max) stop(); }, 250);
  }
  function stop() { clearInterval(iv); mr && mr.state !== "inactive" && mr.stop(); stream && stream.getTracks().forEach(t => t.stop()); btn.classList.remove("live"); btn.textContent = "🎙️"; }
  async function upload() {
    const type = mr.mimeType || "audio/webm"; const ext = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
    const blob = new Blob(chunks, {type}); btn.disabled = true;
    tm.innerHTML = `<span class="loading"><span class="spin"></span>Transcribing ${fmt((Date.now()-t0)/1000)} of audio…</span>`;
    const fd = new FormData(); fd.append("audio", blob, "recording." + ext);
    try {
      const r = await fetch("/api/transcribe", {method: "POST", body: fd});
      if (!r.ok) throw new Error((await r.json()).detail || "Transcription failed");
      const {text} = await r.json();
      const prev = tr.dataset.text ? tr.dataset.text + "\n\n" : ""; tr.dataset.text = prev + text;
      tr.textContent = tr.dataset.text; tr.classList.remove("hidden");
      tm.innerHTML = `<span class="ok-chip">✓ Transcribed</span> <span>Tap the mic to add more</span>`;
      onText(tr.dataset.text);
    } catch (e) { tm.textContent = "⚠ " + e.message; }
    btn.disabled = false;
  }
  btn.onclick = () => (mr && mr.state === "recording") ? stop() : start();
}

/* ---------------- step 1: sources ---------------- */
function refresh1() {
  $("#c-li").classList.toggle("filled", !!S.li.trim()); $("#c-pdf").classList.toggle("filled", !!S.pdf);
  $("#c-dict").classList.toggle("filled", !!S.dictation); $("#go1").disabled = !(S.li.trim() || S.pdf || S.dictation);
}
$("#li").oninput = e => { S.li = e.target.value; refresh1(); };
$("#pdf").onchange = async e => {
  const f = e.target.files[0]; if (!f) return;
  $("#pdfname").textContent = f.name; $("#pdfstatus").innerHTML = `<span class="loading"><span class="spin"></span>Reading PDF…</span>`;
  const fd = new FormData(); fd.append("file", f);
  try { const r = await fetch("/api/pdf-text", {method:"POST", body: fd}); if (!r.ok) throw new Error((await r.json()).detail);
    const d = await r.json(); S.pdf = d.text; $("#pdfstatus").innerHTML = `<span class="ok-chip">✓ Read ${d.pages} page${d.pages>1?"s":""}</span>`; }
  catch (err) { S.pdf = ""; $("#pdfstatus").textContent = "⚠ " + err.message; }
  refresh1();
};
Recorder($("#rec1"), {onText: t => { S.dictation = t; refresh1(); }});
track("start");
$("#go1").onclick = () => go(2);

/* ---------------- step 2: anything new (voice only) ---------------- */
Recorder($("#rec2"), {label: "Tap the mic and tell us what's new", onText: t => { S.addendum = t; $("#go2").disabled = false; }});
$("#skip2").onclick = () => { S.addendum = ""; toQuestions(); };
$("#go2").onclick = toQuestions;

/* ---------------- step 3: preferences + follow-ups ---------------- */
const PREFS = [
  {k: "min_salary", q: "Minimum pay (gross / year)", opts: [["Any", 0], ["€45k+", 45], ["€60k+", 60], ["€75k+", 75], ["€100k+", 100]], one: true},
  {k: "locations", q: "Where can you work?", sub: "pick any", opts: ["Paris", "Lyon", "Toulouse", "Bordeaux", "Lille", "Nantes", "Sophia Antipolis", "Marseille", "Anywhere in France"]},
  {k: "work_modes", q: "Remote or office?", sub: "pick any", opts: ["Remote", "Hybrid", "On-site"]},
  {k: "sizes", q: "Company size", sub: "pick any", opts: [["Early startup (<20)", "seed"], ["Startup (50–200)", "seriesAB"], ["Scale-up (200–1,000)", "scaleup"], ["Large company / MNC (1,000+)", "large"]]},
  {k: "french", q: "Your French level", opts: ["None", "Basic (A1–B1)", "B2", "C1 / Native"], one: true},
  {k: "work_auth", q: "Work authorisation in France", opts: ["Authorised to work", "Need visa sponsorship"], one: true},
];
function toQuestions() {
  go(3); renderPrefs(); S.answers = {}; $("#go3").disabled = true; showErr("#err3");
  $("#fups").innerHTML = `<div class="loading"><div class="spin"></div>Reading your information and checking for gaps…</div>`;
  const sources = [S.li.trim() && "linkedin", S.pdf && "pdf", S.dictation && "voice", S.addendum && "new-info-voice"].filter(Boolean);
  api("/api/analyze", {linkedin: S.li, pdf: S.pdf, dictation: S.dictation, addendum: S.addendum, prefs: S.prefs}).then(d => {
    S.draft = d.profile; S.questions = d.questions || []; renderFups(); $("#go3").disabled = false;
    track("intake_done", {sources, questions: S.questions.length});
  }).catch(e => { $("#fups").innerHTML = ""; showErr("#err3", e); });
}
function renderPrefs() {
  $("#prefs").innerHTML = PREFS.map(p => `<div class="q"><div class="ql">${p.q} ${p.sub ? `<span class="sub">(${p.sub})</span>` : ""}</div><div class="chips" data-k="${p.k}">` +
    p.opts.map(o => { const [l, v] = Array.isArray(o) ? o : [o, o]; const cur = S.prefs[p.k];
      const on = p.one ? cur === v : (cur || []).includes(v); return `<span class="chip ${on ? "on" : ""}" data-v='${JSON.stringify(v)}'>${esc(l)}</span>`; }).join("") + `</div></div>`).join("");
  $("#prefs").querySelectorAll(".chips").forEach(box => {
    const p = PREFS.find(x => x.k === box.dataset.k);
    box.onclick = e => { const c = e.target.closest(".chip"); if (!c) return; const v = JSON.parse(c.dataset.v);
      if (p.one) { S.prefs[p.k] = v; box.querySelectorAll(".chip").forEach(x => x.classList.toggle("on", x === c)); }
      else { const arr = S.prefs[p.k] || []; S.prefs[p.k] = arr.includes(v) ? arr.filter(x => x !== v) : [...arr, v]; c.classList.toggle("on"); } };
  });
}
function renderFups() {
  if (!S.questions.length) { $("#fups").innerHTML = `<p><span class="ok-chip">✓ Looks complete</span> <span class="muted" style="font-size:14px">No follow-ups needed. Your information covers the essentials.</span></p>`; return; }
  $("#fups").innerHTML = S.questions.map(q => `<div class="q"><div class="ql">${esc(q.question)}</div><div class="chips" data-q="${esc(q.id)}">` +
    q.options.map(o => `<span class="chip">${esc(o)}</span>`).join("") + `</div></div>`).join("");
  $("#fups").querySelectorAll(".chips").forEach(box => box.onclick = e => { const c = e.target.closest(".chip"); if (!c) return;
    S.answers[box.dataset.q] = c.textContent; box.querySelectorAll(".chip").forEach(x => x.classList.toggle("on", x === c)); });
}
$("#go3").onclick = () => { track("prefs_done", {prefs: S.prefs}); build(); };

/* ---------------- step 4: resume + change highlights ---------------- */
async function build() {
  go(4); $("#building").classList.remove("hidden"); $("#resumewrap").classList.add("hidden"); $("#go4").disabled = true; showErr("#err4");
  const answers = S.questions.map(q => ({question: q.question, answer: S.answers[q.id] || "Skip"}));
  try {
    const d = await api("/api/build", {profile: S.draft, answers, addendum: S.addendum, prefs: S.prefs});
    S.profile = d.profile; S.changes = d.changes || []; S.diff = diffProfiles(S.draft || {}, S.profile);
    fillEmail(); renderResume(); $("#go4").disabled = false;
    track("resume_built", {had_addendum: !!S.addendum, changes: S.changes.length});
  } catch (e) { showErr("#err4", e); } finally { $("#building").classList.add("hidden"); }
}

// word-overlap similarity, used to match "before" and "after" lines
const words = s => new Set(String(s || "").toLowerCase().replace(/[^a-z0-9%€$ ]+/g, " ").split(/\s+/).filter(w => w.length > 2));
function sim(a, b) { const A = words(a), B = words(b); if (!A.size || !B.size) return 0; let n = 0; A.forEach(w => B.has(w) && n++); return n / Math.max(A.size, B.size); }
const norm = s => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");

function diffProfiles(before, after) {
  const D = {}; // path -> {type: "add"|"edit", old}
  ["headline", "summary"].forEach(k => { if (after[k] && norm(after[k]) !== norm(before[k])) D[k] = {type: before[k] ? "edit" : "add", old: before[k] || ""}; });
  ["email", "phone", "location"].forEach(k => { if (after[k] && !before[k]) D[k] = {type: "add"}; });
  const bx = before.experience || [];
  (after.experience || []).forEach((e, i) => {
    const m = bx.find(x => norm(x.company) === norm(e.company) && (sim(x.title, e.title) > 0.3 || norm(x.title) === norm(e.title)))
           || bx.find(x => norm(x.company) === norm(e.company));
    if (!m) { D[`experience.${i}`] = {type: "add"}; return; }
    if (norm(m.title) !== norm(e.title)) D[`experience.${i}.title`] = {type: "edit", old: m.title};
    if (norm(m.end) !== norm(e.end)) D[`experience.${i}.end`] = {type: "edit", old: m.end};
    if (norm(m.start) !== norm(e.start)) D[`experience.${i}.start`] = {type: "edit", old: m.start};
    (e.bullets || []).forEach((b, j) => {
      const best = Math.max(0, ...(m.bullets || []).map(x => sim(x, b)));
      if (best >= 0.85) return;
      const old = (m.bullets || []).reduce((acc, x) => sim(x, b) > sim(acc, b) ? x : acc, "");
      D[`experience.${i}.bullets.${j}`] = best >= 0.35 ? {type: "edit", old} : {type: "add"};
    });
  });
  const bs = new Set((before.skills || []).map(norm));
  const newSkills = (after.skills || []).filter(s => !bs.has(norm(s)));
  if (newSkills.length) D.skills = {type: "add", items: newSkills};
  const be = before.education || [];
  (after.education || []).forEach((e, i) => { if (!be.some(x => norm(x.school) === norm(e.school))) D[`education.${i}`] = {type: "add"}; });
  return D;
}
function cls(path) { const d = S.diff[path]; return d ? (d.type === "add" ? "chg-add" : "chg-edit") : ""; }
function ed(path, val, tag = "span", extra = "") {
  const d = S.diff[path]; const title = d && d.old ? ` title="Before: ${esc(d.old)}"` : "";
  return `<${tag} contenteditable data-p="${path}" class="${cls(path)} ${extra}"${title}>${esc(val)}</${tag}>`;
}
function renderResume() {
  const p = S.profile; $("#resumewrap").classList.remove("hidden");
  const contact = ["location", "email", "phone", "linkedin"].filter(k => p[k]).map(k => ed(k, p[k])).join(" · ");
  let h = `<h1>${ed("name", p.name || "Your Name")}</h1><div class="hl">${ed("headline", p.headline || "")}</div><div class="ct">${contact}</div>`;
  if (p.summary) h += `<h4>Summary</h4>${ed("summary", p.summary, "div")}`;
  if ((p.experience || []).length) { h += `<h4>Experience</h4>`; p.experience.forEach((e, i) => {
    const isNew = S.diff[`experience.${i}`]; const wrapOpen = isNew ? `<div class="chg-add">` : `<div>`;
    h += `${wrapOpen}<div class="rl"><div><b>${ed(`experience.${i}.title`, e.title)}</b>${isNew ? '<span class="chg-tag">New</span>' : ""} · ${ed(`experience.${i}.company`, e.company)}${e.location ? ", " + ed(`experience.${i}.location`, e.location) : ""}</div><div class="muted">${ed(`experience.${i}.start`, e.start)} – ${ed(`experience.${i}.end`, e.end)}</div></div>`;
    h += `<ul>${(e.bullets || []).map((b, j) => `<li class="${isNew ? "" : cls(`experience.${i}.bullets.${j}`)}"${S.diff[`experience.${i}.bullets.${j}`]?.old ? ` title="Before: ${esc(S.diff[`experience.${i}.bullets.${j}`].old)}"` : ""}>${ed(`experience.${i}.bullets.${j}`, b).replace(/class="[^"]*"/, 'class=""')}</li>`).join("")}</ul></div>`; }); }
  if ((p.education || []).length) { h += `<h4>Education</h4>`; p.education.forEach((e, i) => h += `<div class="rl ${cls(`education.${i}`)}"><div><b>${ed(`education.${i}.degree`, e.degree)}</b> · ${ed(`education.${i}.school`, e.school)}</div><div class="muted">${ed(`education.${i}.year`, e.year)}</div></div>`); }
  if ((p.skills || []).length) h += `<h4>Skills</h4>${ed("skills", p.skills.join(", "), "div")}`;
  if ((p.languages || []).length) h += `<h4>Languages</h4>${ed("languages", p.languages.join(", "), "div")}`;
  if ((p.achievements || []).length) h += `<h4>Achievements</h4><ul>${p.achievements.map((a, j) => `<li>${ed(`achievements.${j}`, a)}</li>`).join("")}</ul>`;
  $("#paper").innerHTML = h;
  $("#paper").querySelectorAll("[contenteditable]").forEach(el => el.oninput = () => setPath(el.dataset.p, el.innerText.trim()));
  renderChanges();
}
function renderChanges() {
  const items = [];
  S.changes.forEach(c => { const what = typeof c === "string" ? c : c.what; const src = typeof c === "string" ? "" : c.source;
    items.push(`<li class="${/add/i.test(what) ? "add" : ""}">${esc(what)}${src ? `<span class="src-note">From ${esc(src)}</span>` : ""}</li>`); });
  if (S.diff.skills) items.push(`<li class="add">Skills added: ${esc(S.diff.skills.items.join(", "))}</li>`);
  const edits = Object.entries(S.diff).filter(([k, d]) => d.type === "edit" && d.old && k.includes("bullets")).slice(0, 4);
  edits.forEach(([k, d]) => items.push(`<li>Reworded: <span class="old">${esc(d.old)}</span></li>`));
  $("#changes").innerHTML = items.length ? items.join("") : `<li class="muted">Built from your sources as-is.</li>`;
}
$("#showchg").onchange = e => $("#paper").classList.toggle("no-hl", !e.target.checked);
function setPath(path, val) {
  const ks = path.split("."); let o = S.profile;
  for (let i = 0; i < ks.length - 1; i++) o = o[ks[i]];
  const last = ks[ks.length - 1]; o[last] = (path === "skills" || path === "languages") ? val.split(",").map(s => s.trim()).filter(Boolean) : val;
  if (path === "email") fillEmail(true);
}
function fillEmail(force) {
  let e = (S.profile.email || "").trim();
  if (!EMAIL_RE.test(e)) { const m = [S.pdf, S.li, S.dictation, S.addendum].join("\n").match(EMAIL_RE); e = m ? m[0] : ""; if (e && !S.profile.email) S.profile.email = e; }
  if (force || !$("#appemail").value) $("#appemail").value = e;
  $("#emailnote").innerHTML = e ? "" : `<span class="warn">No email found in your resume or profile. Add one here so HireHub can send your confirmation.</span>`;
}
$("#dl").onclick = async () => {
  $("#dl").disabled = true; $("#dl").textContent = "Preparing PDF…";
  try { const r = await fetch("/api/resume.pdf", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({profile: S.profile})});
    const b = await r.blob(); const a = document.createElement("a"); a.href = URL.createObjectURL(b);
    a.download = (S.profile.name || "resume").replace(/\W+/g, "_") + "_Resume.pdf"; a.click(); track("resume_downloaded"); }
  finally { $("#dl").disabled = false; $("#dl").textContent = "⬇ Download PDF"; }
};

/* ---------------- step 5: jobs ---------------- */
$("#go4").onclick = async () => {
  go(5); showErr("#err5"); fillEmail();
  $("#jobs").innerHTML = `<div class="card center"><div class="loading" style="justify-content:center"><div class="spin"></div>Scoring 30 open roles…</div></div>`;
  try { const d = await api("/api/recommend", {profile: S.profile, prefs: S.prefs}); renderJobs(d.jobs); track("jobs_viewed", {top: d.jobs.map(j => j.score)}); }
  catch (e) { $("#jobs").innerHTML = ""; showErr("#err5", e); }
};
$("#appemail").oninput = () => { $("#emailnote").innerHTML = EMAIL_RE.test($("#appemail").value) ? "" : `<span class="warn">Add a valid email so HireHub can send your confirmation.</span>`; };
const ringCls = s => s >= 7.5 ? "good" : s >= 5 ? "ok" : "bad";
const icon = {good: "✓", ok: "~", bad: "✗"};
function renderJobs(list) {
  $("#jobs").innerHTML = list.map((r, i) => { const j = r.job; return `<div class="card job">
   <div class="ring ${ringCls(r.score)}">${r.score.toFixed(1)}<small>/10</small></div>
   <div><h3>${esc(j.title)}</h3><div class="co">${esc(j.company)} · ${esc(j.location)}</div>
    <div class="tags"><span class="tag pay">€${j.salary_min}k–${j.salary_max}k</span><span class="tag">${j.min_years}–${j.max_years} yrs experience</span><span class="tag">${esc(j.work_mode_label)}</span><span class="tag">${esc(j.company_size_label)}</span><span class="tag">${esc(j.language)}</span></div>
    <div class="reason">${esc(r.reason)}</div><span class="why" data-i="${i}">See score breakdown ▾</span></div>
   <div class="act"><button class="btn" data-apply="${esc(j.id)}">Apply →</button></div>
   <div class="factors" id="f${i}"><div class="factor head">Requirements match <b>&nbsp;${r.req_score}/10</b>&nbsp;× 60% + Preference match <b>&nbsp;${r.pref_score}/10</b>&nbsp;× 40%</div>
    ${r.factors.filter(f => f.w > 0).map(f => `<div class="factor ${f.status}">${icon[f.status]} <div><b>${esc(f.label)}</b><br>${esc(f.note)}</div></div>`).join("")}</div></div>`; }).join("");
  $("#jobs").querySelectorAll(".why").forEach(w => w.onclick = () => $("#f" + w.dataset.i).classList.toggle("open"));
  $("#jobs").querySelectorAll("[data-apply]").forEach(b => b.onclick = () => applyTo(b));
}
async function applyTo(b) {
  const email = $("#appemail").value.trim();
  if (!EMAIL_RE.test(email)) { $("#emailnote").innerHTML = `<span class="warn">Add a valid email first. Your confirmation goes there.</span>`; $("#appemail").focus(); return; }
  const win = window.open("", "_blank");  // open synchronously so popup blockers allow it
  if (win) win.document.write(`<p style="font-family:Georgia,serif;padding:40px;color:#6b6b6b;background:#FFFBF4">Tailoring your resume and cover note for this job…</p>`);
  b.disabled = true; const old = b.innerHTML; b.innerHTML = `<span class="spin" style="border-color:#ffffff66;border-top-color:#fff"></span> Preparing…`;
  try {
    const d = await api("/api/apply", {profile: S.profile, prefs: S.prefs, job_id: b.dataset.apply, email});
    track("apply_clicked", {job: b.dataset.apply});
    if (win) win.location = d.url; else location.href = d.url;
    b.innerHTML = "✓ Opened. Review &amp; submit there";
  } catch (e) { if (win) win.close(); showErr("#err5", e); b.innerHTML = old; b.disabled = false; }
}
