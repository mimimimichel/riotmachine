"use strict";

/* Régie Riot Machine — page unique, sans dépendance.
   Pages : Studio (les clips), un clip (Plans, Dossier, Découpage, Journal),
   Personnages, Nouveau clip. Le détail d'un plan s'ouvre dans un panneau. */

/* ---------- vocabulaire ---------- */

const STEPS = [
  { key: "image", label: "Visuel draft", kinds: ["image"], gate: "images" },
  { key: "hd", label: "Visuel HD", kinds: ["image_hd"], gate: "hd" },
  { key: "plan", label: "Plan vidéo", kinds: [], gate: "videoplan" },
  { key: "draft", label: "Vidéo draft", kinds: ["draft"], gate: "drafts" },
  { key: "final", label: "Vidéo HD", kinds: ["final"], gate: "finals" },
  { key: "lipsync", label: "Lip-sync", kinds: ["lipsync"], gate: "finals", singing: true },
];
const STEP_INDEX = Object.fromEntries(STEPS.map((s, i) => [s.key, i]));

// statut -> [libellé, état, étape]
const STATUS = {
  image_todo: ["Storyboard en préparation", "work", "image"],
  image_gen: ["Visuel en génération", "work", "image"],
  image_qc: ["Contrôle du visuel", "work", "image"],
  image_review: ["Visuel en attente de validation", "review", "image"],
  hd_todo: ["Passage en HD", "work", "hd"],
  hd_gen: ["Passage en HD", "work", "hd"],
  hd_qc: ["Contrôle de la HD", "work", "hd"],
  hd_review: ["HD en attente de validation", "review", "hd"],
  prompt_todo: ["Prompt et modèle en préparation", "work", "plan"],
  video_review: ["Plan vidéo en attente de validation", "review", "plan"],
  draft_todo: ["Vidéo draft lancée", "work", "draft"],
  draft_gen: ["Vidéo draft en génération", "work", "draft"],
  draft_qc: ["Contrôle de la vidéo", "work", "draft"],
  draft_review: ["Vidéo draft en attente de validation", "review", "draft"],
  final_todo: ["Vidéo HD lancée", "work", "final"],
  final_gen: ["Vidéo HD en génération", "work", "final"],
  lipsync_todo: ["Lip-sync lancé", "work", "lipsync"],
  lipsync_gen: ["Lip-sync en génération", "work", "lipsync"],
  final_review: ["Final en attente de validation", "review", "final"],
  done: ["Terminé", "done", "final"],
  change_requested: ["Modif demandée", "change", null],
  failed: ["En échec", "failed", null],
};
const GATE_STEP = { images: "image", hd: "hd", videoplan: "plan", drafts: "draft", finals: "final" };
const KIND_STEP = { image: "image", image_hd: "hd", draft: "draft", final: "final", lipsync: "lipsync" };
const STAGE_LABEL = {
  script: ["Préparation", "wait"],
  decoupage_review: ["Découpage en attente de validation", "review"],
  production: ["En production", "work"],
  done: ["Terminé", "done"],
};
const APPROVE_LABEL = {
  images: ["Valider le visuel", "visuels"],
  hd: ["Valider la HD", "visuels HD"],
  videoplan: ["Valider et lancer la vidéo", "plans vidéo"],
  drafts: ["Valider la vidéo draft", "vidéos draft"],
  finals: ["Valider le final", "finals"],
};
const CHAR_KIND_LABEL = {
  canon: "Candidates canon", sheet: "Feuilles de personnage", turnaround: "Angles", fullbody: "Silhouette", expressions: "Expressions",
  lighting: "Lumières", details: "Détails",
};
const FILE_ICON = { pdf: "PDF", docx: "DOC", md: "MD", txt: "TXT", png: "IMG", jpg: "IMG", jpeg: "IMG", webp: "IMG", mp3: "♪", wav: "♪", m4a: "♪" };

/* ---------- état ---------- */

const state = {
  clip: null, clipJson: "", tab: "plans", shotId: null, step: null, filter: "all", stepFilter: null,
  picked: {}, peaks: {}, timer: null, overview: null, editor: null, editorDirty: false,
  character: null, charVersion: null, tempOpen: {}, confirmKey: null,
};
const $view = document.getElementById("view");
const $drawer = document.getElementById("drawer");
const song = document.createElement("audio");
song.preload = "metadata";
document.body.appendChild(song);

/* ---------- utilitaires ---------- */

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const media = (p) => (p ? "/media/" + p.split("/").map(encodeURIComponent).join("/") : "");
const money = (n) => `${(n || 0).toFixed(2)} $`;
const isVideo = (p) => /\.(mp4|mov|webm)$/i.test(p || "");
function tc(s, digits = 1) {
  if (s == null || isNaN(s)) return "–";
  const m = Math.floor(s / 60);
  const r = (s - m * 60).toFixed(digits).padStart(digits ? 3 + digits : 2, "0");
  return `${m}:${r}`;
}
function durText(s) {
  const a = parseTc(s.t_start), b = parseTc(s.t_end);
  if (a == null || b == null || isNaN(a) || isNaN(b)) return "";
  const d = b - a;
  return d > 0 ? `${d.toFixed(1).replace(".", ",")} s` : "fin avant début";
}

/* modèle vidéo d'un plan et écart de durée (mêmes règles que routing.duration_fit) */
function modelOf(clip, key) { return (clip.video_models || []).find((m) => m.key === (key || clip.video_default)); }
function genSecs(m, secs) {
  const allowed = (m.durations || [5]).slice().sort((a, b) => a - b);
  return allowed.find((d) => d + 1e-6 >= secs) ?? null;
}
function fitFor(clip, key, secs) {
  const m = modelOf(clip, key);
  if (!m || !(secs > 0)) return null;
  const allowed = (m.durations || [5]).slice().sort((a, b) => a - b);
  const max = allowed[allowed.length - 1];
  const gen = genSecs(m, secs);
  const s1 = secs.toFixed(1).replace(".", ",");
  // le modèle branché le moins cher pour ce plan, tout compris (secondes générées × prix)
  const cost = (x) => { const g = genSecs(x, secs); return g == null ? Infinity : g * (x.price_s || 0); };
  const best = (clip.video_models || []).filter((x) => x.usable).sort((a, b) => cost(a) - cost(b))[0];
  const cur = gen == null ? Infinity : cost(m);
  const suggest = best && best.key !== m.key && cost(best) < cur - 0.005 ? { key: best.key, label: best.label, cost: cost(best), from: cur } : null;
  if (gen == null) return { level: "bad", short: `trop long pour ${m.label}`, suggest,
    text: `Plan de ${s1} s, trop long pour ${m.label} (${max} s au plus) : coupe-le en deux ou prends un autre modèle.` };
  const waste = gen - secs;
  if (waste >= 1.5) return { level: "warn", short: `${waste.toFixed(1).replace(".", ",")} s payées en trop`, suggest,
    text: `Plan de ${s1} s, mais ${m.label} fait au moins ${gen} s : ${waste.toFixed(1).replace(".", ",")} s payées en trop (≈ ${money(waste * (m.price_s || 0))}).` };
  return { level: "ok", short: "", suggest, text: `${m.label} génère ${gen} s pour ce plan (≈ ${money(cur)}).` };
}
function fitHtml(f, key) {
  if (!f) return "";
  return `<span class="fit ${f.level}">${esc(f.text)}</span>${f.suggest ? `<div class="row" style="gap:8px;margin-top:6px">
      <button class="btn small go" data-usemodel="${key}:${esc(f.suggest.key)}">Prendre ${esc(f.suggest.label)} · ≈ ${money(f.suggest.cost)} au lieu de ${money(f.suggest.from)}</button></div>` : ""}`;
}
function fitBadge(f) { return f ? `<span class="fit ${f.level}">${esc(f.text)}</span>` : ""; }
function modelSelect(clip, current, attrs) {
  const def = modelOf(clip, null);
  const opt = (m) => `<option value="${m.key}" ${m.key === current ? "selected" : ""} ${m.usable ? "" : "disabled"}>${esc(m.label)}${m.multishot ? " · plusieurs plans par prise" : ""}${m.usable ? "" : " (non branché)"}</option>`;
  const ms = clip.video_models || [];
  return `<select ${attrs}>
      <option value="" ${current ? "" : "selected"}>Par défaut : ${esc(def ? def.label : "?")}</option>
      <optgroup label="Branchés">${ms.filter((m) => m.usable).map(opt).join("")}</optgroup>
      <optgroup label="Non branchés">${ms.filter((m) => !m.usable).map(opt).join("")}</optgroup></select>`;
}
const NOTE_AUTHOR = { michael: "Toi", controleur: "Contrôleur", machine: "Machine", orchestrateur: "Orchestrateur" };

function parseTc(v) {
  v = String(v ?? "").trim().replace(",", ".");
  if (!v) return null;
  const m = v.match(/^(\d+):(\d{1,2}(?:\.\d+)?)$/);
  if (m) return +m[1] * 60 + +m[2];
  const n = Number(v.replace(/s$/, ""));
  return isNaN(n) ? NaN : n;
}
const ext = (p) => (p || "").split(".").pop().toLowerCase();
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

function toast(msg, kind = "ok") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "show " + kind;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.className = ""; }, kind === "err" ? 5000 : 2600);
}

async function api(path, opts = {}) {
  const init = { ...opts };
  if (opts.json !== undefined) {
    init.method = init.method || "POST";
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(opts.json);
    delete init.json;
  }
  const r = await fetch(path, init);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Erreur ${r.status}`);
  return body;
}

function upload(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
    xhr.onload = () => {
      let body = {};
      try { body = JSON.parse(xhr.responseText); } catch (e) { /* réponse vide */ }
      if (xhr.status >= 400) reject(new Error(typeof body.detail === "string" ? body.detail : `Erreur ${xhr.status}`));
      else resolve(body);
    };
    xhr.onerror = () => reject(new Error("Envoi interrompu : vérifie la connexion"));
    xhr.send(formData);
  });
}

function prefs(key, value) {
  try {
    if (value === undefined) return JSON.parse(localStorage.getItem("riot:" + key) || "null");
    localStorage.setItem("riot:" + key, JSON.stringify(value));
  } catch (e) { /* stockage indisponible : sans conséquence */ }
  return null;
}

const led = (cls) => `<span class="led ${cls}"></span>`;
const pill = (label, cls) => `<span class="pill ${cls}">${led(cls)}${esc(label)}</span>`;

function lightbox(src) {
  const box = document.createElement("div");
  box.className = "lightbox";
  box.innerHTML = `<img src="${src}" alt="">`;
  box.addEventListener("click", () => box.remove());
  document.addEventListener("keydown", function k(e) {
    if (e.key === "Escape") { box.remove(); document.removeEventListener("keydown", k); }
  });
  document.body.appendChild(box);
}

/* Deux temps pour les actions groupées : premier appui = « Confirmer ? ». */
function needsConfirm(btn, key) {
  if (state.confirmKey === key) { state.confirmKey = null; return false; }
  state.confirmKey = key;
  const old = btn.innerHTML;
  btn.innerHTML = "Confirmer ?";
  btn.classList.add("go");
  setTimeout(() => {
    if (state.confirmKey === key) { state.confirmKey = null; btn.innerHTML = old; btn.classList.remove("go"); }
  }, 4000);
  return true;
}

function isBusy() {
  const a = document.activeElement;
  if (a && (a.tagName === "TEXTAREA" || (a.tagName === "INPUT" && a.type !== "checkbox" && a.type !== "radio"))) return true;
  if ([...document.querySelectorAll("video")].some((v) => !v.paused)) return true;
  if (document.querySelector(".feedback:not([hidden]) textarea")) return true;
  return false;
}

function compareWidget(leftSrc, rightSrc, leftLabel, rightLabel) {
  return `<div class="compare" data-compare>
      <img src="${rightSrc}" alt="${esc(rightLabel)}">
      <div class="top" style="width:50%"><img src="${leftSrc}" alt="${esc(leftLabel)}"></div>
      <span class="bar" style="left:50%"></span>
      <span class="lab l">${esc(leftLabel)}</span><span class="lab r">${esc(rightLabel)}</span>
    </div>
    <div class="sidebyside">
      <figure><img src="${leftSrc}" data-zoom="${leftSrc}" alt=""><figcaption>${esc(leftLabel)} : touche pour agrandir</figcaption></figure>
      <figure><img src="${rightSrc}" data-zoom="${rightSrc}" alt=""><figcaption>${esc(rightLabel)} : touche pour agrandir</figcaption></figure>
    </div>`;
}

function bindCompare(root) {
  root.querySelectorAll("[data-compare]").forEach((box) => {
    const top = box.querySelector(".top");
    const topImg = top.querySelector("img");
    const bar = box.querySelector(".bar");
    const size = () => { topImg.style.width = box.clientWidth + "px"; topImg.style.height = "auto"; };
    const imgs = box.querySelectorAll("img");
    imgs.forEach((i) => i.addEventListener("load", size));
    size();
    const move = (x) => {
      const r = box.getBoundingClientRect();
      const pct = Math.min(100, Math.max(0, ((x - r.left) / r.width) * 100));
      top.style.width = pct + "%";
      bar.style.left = pct + "%";
    };
    let drag = false;
    box.addEventListener("pointerdown", (e) => { drag = true; box.setPointerCapture(e.pointerId); move(e.clientX); });
    box.addEventListener("pointermove", (e) => { if (drag) move(e.clientX); });
    box.addEventListener("pointerup", () => { drag = false; });
  });
}

function dropZone(name, label, hint, accept, multiple) {
  return `<label class="drop" data-drop="${name}">
      <span class="big">${esc(label)}</span><span class="hint">${esc(hint)}</span>
      <input type="file" name="${name}" ${accept ? `accept="${accept}"` : ""} ${multiple ? "multiple" : ""}>
      <span class="hint picked"></span>
    </label>`;
}

function bindDrops(root, onFiles) {
  root.querySelectorAll("[data-drop]").forEach((zone) => {
    const input = zone.querySelector("input");
    const shown = zone.querySelector(".picked");
    const show = () => {
      const names = [...input.files].map((f) => f.name);
      shown.textContent = names.length ? names.join(" · ") : "";
      if (onFiles && names.length) onFiles(zone.dataset.drop, input.files);
    };
    input.addEventListener("change", show);
    zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("over"));
    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("over");
      if (!e.dataTransfer.files.length) return;
      const dt = new DataTransfer();
      [...(input.multiple ? input.files : []), ...e.dataTransfer.files].forEach((f) => dt.items.add(f));
      input.files = dt.files;
      show();
    });
  });
}

/* ---------- navigation ---------- */

function setNav(name) {
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === name));
}

function stopTimer() { clearInterval(state.timer); state.timer = null; }

function every(ms, fn) {
  stopTimer();
  state.timer = setInterval(() => { if (!document.hidden) fn(); }, ms);
}

let lastRoute = "";
async function router() {
  const hash = location.hash || "#/";
  const parts = hash.slice(2).split("/").map(decodeURIComponent);
  const [page, arg, tab, sub, shot] = parts;
  try {
    if (page === "clip" && arg) {
      setNav("studio");
      const sameView = lastRoute === `clip/${arg}/${tab || ""}` && state.clip && state.clip.slug === arg;
      lastRoute = `clip/${arg}/${tab || ""}`;
      state.shotId = sub === "p" && shot ? +shot : null;
      if (sameView) { renderDrawer(); return; }
      await showClip(arg, tab);
      return;
    }
    lastRoute = hash;
    closeDrawerUi();
    if (page === "personnages" && arg) { setNav("personnages"); await showCharacter(arg); }
    else if (page === "personnages") { setNav("personnages"); await showCharacters(); }
    else if (page === "nouveau") { setNav("studio"); await showNewClip(); }
    else if (page === "fournisseurs") { setNav("fournisseurs"); await showProviders(); }
    else if (page === "depenses") { setNav("depenses"); await showSpend(); }
    else { setNav("studio"); await showStudio(); }
  } catch (e) {
    $view.innerHTML = `<p class="empty">${esc(e.message)}</p>`;
  }
}
window.addEventListener("hashchange", router);

async function refreshSys() {
  try {
    const d = await api("/api/overview");
    state.overview = d;
    const live = d.providers.filter((p) => p.usable);
    const navSpend = document.getElementById("nav-spend-n");
    if (navSpend) navSpend.textContent = d.spend && d.spend.pending ? ` ${d.spend.pending}` : "";
    document.getElementById("sysstat").innerHTML = `
      <span title="Générations en cours chez les fournisseurs">${led(d.jobs_running ? "work" : "wait")}${d.jobs_running} génération${d.jobs_running > 1 ? "s" : ""}</span>
      <span title="Agents Claude au travail">${led(d.agents_running.length ? "work" : "wait")}<span class="long">Agents :</span> ${d.agents_running.length ? "au travail" : "en veille"}</span>
      <a href="#/fournisseurs" title="Fournisseurs branchés (les autres ne génèrent rien)">${led(live.length ? "done" : "failed")}${live.length ? live.map((p) => esc(p.label.replace(/ \(.*\)$/, ""))).join(", ") : "Aucun fournisseur branché"}</a>
      ${d.spend && d.spend.pending ? `<a class="spend-badge" href="#/depenses" title="Générations qui attendent ton accord">💳 ${d.spend.pending} à valider · ${money(d.spend.usd)}</a>` : ""}`;
    return d;
  } catch (e) { return null; }
}
setInterval(() => { if (!document.hidden) refreshSys(); }, 20000);

/* ---------- logique des plans ---------- */

function lastReviewGate(shot) {
  const r = (shot.reviews || []).find((x) => x.decision === "change");
  return r ? r.gate : null;
}

function failedStep(shot) {
  const failed = (shot.assets || []).filter((a) => a.status === "failed").sort((a, b) => b.id - a.id)[0];
  return failed ? KIND_STEP[failed.kind] : "image";
}

function currentStep(shot) {
  const info = STATUS[shot.status];
  if (!info) return "image";
  if (shot.status === "change_requested") return GATE_STEP[lastReviewGate(shot)] || "image";
  if (shot.status === "failed") return failedStep(shot);
  if (shot.status === "final_review" && shot.singing) return "lipsync";
  if (shot.status === "done") return shot.singing ? "lipsync" : "final";
  return info[2];
}

function preProduction() { return state.clip && (state.clip.stage === "script" || state.clip.stage === "decoupage_review"); }

function shotState(shot) {
  if (shot.id && preProduction()) return "wait";
  if (shot.waiting === "spend") return "review";
  if (shot.waiting === "decors" || shot.waiting === "decors_scan") return "wait";
  return (STATUS[shot.status] || ["", "wait"])[1];
}

// ce qui bloque un plan quand ce n'est pas la machine qui travaille
function waitingText(shot) {
  return {
    spend: "En attente de validation : la dépense de ce visuel est dans l'onglet Dépenses.",
    decors_scan: "Attend le repérage des décors, objets et figurants.",
    decors: "Attend une image de référence gardée pour ses décors (onglet Décors).",
  }[shot.waiting] || "";
}

function statusLabel(shot) {
  if (preProduction()) return state.clip.stage === "decoupage_review" ? "Attend la validation du découpage" : "Découpage en préparation";
  if (shot.waiting === "spend") return "En attente de validation (dépense)";
  if (shot.waiting === "decors_scan") return "Attend le repérage des décors";
  if (shot.waiting === "decors") return "Attend les références de décor";
  return (STATUS[shot.status] || [shot.status])[0];
}

function stepStates(shot) {
  const cur = currentStep(shot);
  const curIdx = STEP_INDEX[cur];
  const st = shotState(shot);
  return STEPS.map((s, i) => {
    if (s.singing && !shot.singing) return { ...s, state: "off", text: "Plan non chanté" };
    if (shot.status === "done") return { ...s, state: "done", text: "Validé" };
    if (i < curIdx) return { ...s, state: "done", text: "Validé" };
    if (i === curIdx) {
      return { ...s, state: st, text: statusLabel(shot) };
    }
    if (shot.status === "final_review" && s.key === "final" && shot.singing) return { ...s, state: "done", text: "Prête" };
    return { ...s, state: "wait", text: "À venir" };
  });
}

function assetsOf(shot, kinds) {
  return (shot.assets || [])
    .filter((a) => kinds.includes(a.kind) && a.path && a.status !== "generating")
    .sort((a, b) => a.version - b.version);
}

function bestAsset(shot, kinds) {
  const list = assetsOf(shot, kinds).filter((a) => a.status !== "failed");
  const live = list.filter((a) => !["superseded", "rejected"].includes(a.status));
  return (live.length ? live : list).slice(-1)[0] || null;
}

function thumbOf(shot) {
  return bestAsset(shot, ["image_hd"]) || bestAsset(shot, ["image"]);
}

function gateOf(shot) {
  return { image_review: "images", hd_review: "hd", video_review: "videoplan", draft_review: "drafts", final_review: "finals" }[shot.status] || null;
}

function aspectClass(clip) { return clip.aspect_ratio === "9:16" ? "v916" : clip.aspect_ratio === "1:1" ? "v11" : ""; }

/* ---------- Studio ---------- */

async function showStudio() {
  const d = await refreshSys() || await api("/api/overview");
  const pending = d.clips.reduce((n, c) => n + c.to_review, 0);
  const cards = d.clips.map((c) => {
    const total = c.shots || 1;
    const counts = {};
    Object.entries(c.status_counts).forEach(([s, n]) => { const k = shotState({ status: s }); counts[k] = (counts[k] || 0) + n; });
    const bar = ["done", "review", "work", "change", "failed"].map((k) => counts[k]
      ? `<i class="c-${k}" style="width:${(100 * counts[k]) / total}%"></i>` : "").join("");
    const [stLabel, stCls] = STAGE_LABEL[c.stage] || [c.stage, "wait"];
    return `<a class="clipcard" href="#/clip/${encodeURIComponent(c.slug)}">
      <div class="poster" style="${c.poster ? `background-image:url('${media(c.poster)}')` : ""}">
        ${c.poster ? "" : `<span>${esc(c.aspect_ratio)}</span>`}
        ${c.to_review ? `<span class="badge">${pill(`${c.to_review} à valider`, "review")}</span>` : ""}
      </div>
      <div class="body">
        <div class="row"><span class="title">${esc(c.title)}</span><span class="spacer"></span>${pill(stLabel, stCls)}</div>
        ${c.pitch ? `<p class="pitch">${esc(c.pitch)}</p>` : ""}
        ${c.shots && c.stage !== "script" && c.stage !== "decoupage_review" ? `<div class="pipebar">${bar}</div>` : ""}
        <div class="row hint"><span>${c.shots} plan${c.shots > 1 ? "s" : ""}</span><span class="spacer"></span>
          <span class="mono">${money(c.cost_usd)}${c.budget_usd ? ` / ${c.budget_usd.toFixed(0)} $` : ""}</span></div>
      </div></a>`;
  }).join("");
  const todo = (d.todo || []).length ? `<section class="panel todo"><h2>À faire maintenant</h2>
      <ul>${d.todo.map((x) => `<li><a href="${x.href}">${led("review")}${esc(x.label)}</a></li>`).join("")}</ul></section>` : "";
  $view.innerHTML = `
    ${todo}
    <div class="pagehead"><h1>Studio</h1>
      <span class="sub">${pending ? `<span class="pill review">${led("review")}${pending} en attente de validation</span>` : "Rien en attente de validation"}</span>
      <span class="spacer"></span><a class="btn go" href="#/nouveau">＋ Nouveau clip</a></div>
    <div class="clips">${cards}
      <a class="newcard" href="#/nouveau"><span class="plus">＋</span><b>Nouveau clip</b><span class="hint">Morceau, dossier de réalisation, paroles</span></a>
    </div>
    <div class="legend" style="margin-top:22px">
      <span>${led("review")}en attente de validation</span><span>${led("work")}la machine travaille</span>
      <span>${led("done")}validé</span><span>${led("change")}modif demandée</span><span>${led("failed")}échec</span></div>`;
  every(20000, () => { if (!isBusy()) showStudio(); });
}

/* ---------- Clip ---------- */

function defaultTab(clip) {
  if (clip.stage === "script" || clip.stage === "decoupage_review") {
    return clip.shots.length || clip.stage === "decoupage_review" ? "decoupage" : "dossier";
  }
  return "plans";
}

async function showClip(slug, tab, keep = false) {
  const clip = await api(`/api/clips/${encodeURIComponent(slug)}`);
  const json = JSON.stringify(clip);
  const changed = json !== state.clipJson;
  const newClip = !state.clip || state.clip.slug !== slug;
  state.clipJson = json;
  state.clip = clip;
  if (newClip) {
    state.editor = null; state.editorDirty = false; state.filter = "all"; state.stepFilter = null;
    state.picked = {}; state.tempOpen = {};
    if (song.dataset.clip !== slug) {
      song.pause();
      song.src = clip.song_path ? media(clip.song_path) : "";
      song.dataset.clip = slug;
    }
  }
  state.tab = tab || defaultTab(clip);
  if (keep && !changed) return;
  if (keep && isBusy()) return;
  if (keep && state.tab === "decoupage" && state.editorDirty) { renderDrawer(); return; }
  if (keep && state.tab === "dossier") { renderDrawer(); return; }
  if (keep && state.tab === "decors") { if (!isBusy()) loadDecors(state.clip, true); return; }
  const scroll = window.scrollY;
  renderClip();
  if (keep) window.scrollTo(0, scroll);
  else window.scrollTo(0, 0);
  renderDrawer();
  every(8000, () => showClip(slug, state.tab, true));
}

function clipCounts(clip) {
  const byState = { review: 0, work: 0, done: 0, change: 0, failed: 0 };
  clip.shots.forEach((s) => { byState[shotState(s)] = (byState[shotState(s)] || 0) + 1; });
  return byState;
}

function renderClip() {
  const clip = state.clip;
  const c = clipCounts(clip);
  const [stLabel, stCls] = STAGE_LABEL[clip.stage] || [clip.stage, "wait"];
  const base = `#/clip/${encodeURIComponent(clip.slug)}`;
  const tabs = [
    ["plans", "Plans", c.review ? `<span class="count">${c.review}</span>` : ""],
    ["decoupage", "Découpage", clip.stage === "decoupage_review" ? `<span class="count">à valider</span>` : ""],
    ["decors", "Décors", clip.decors_pending ? `<span class="count">${clip.decors_pending}</span>` : ""],
    ["dossier", "Dossier", ""],
    ["journal", "Journal", ""],
  ];
  const casting = clip.casting.map((x) => `${esc(x.name)} v${x.version}${x.look_slug ? " · " + esc(x.look_slug) : ""}`).join(", ");
  let html = `<div class="cliphead">
      <div class="crumbs"><a href="#/">Studio</a> / ${esc(clip.title)}</div>
      <div class="row"><h1>${esc(clip.title)}</h1>${pill(stLabel, stCls)}</div>
      ${clip.pitch ? `<p class="pitch folded" data-unfold title="Toucher pour tout lire">${esc(clip.pitch)}</p>` : ""}
      <div class="meta"><span>${clip.shots.length} plans · ${clip.blocks.length} blocs</span>
        <span>${esc(clip.aspect_ratio)}</span>${casting ? `<span>${casting}</span>` : ""}
        <span class="mono">${money(clip.cost_usd)}${clip.budget_usd ? ` / ${clip.budget_usd.toFixed(0)} $` : ""}</span></div>
    </div>
    <nav class="tabs">${tabs.map(([k, l, extra]) => `<a href="${base}/${k}" class="${state.tab === k ? "on" : ""}">${l}${extra}</a>`).join("")}</nav>`;
  if (clip.agent_running) {
    html += `<div class="agentbar">${led("work")}Un agent travaille sur ce clip en ce moment. La page se met à jour toute seule.</div>`;
  }
  if (clip.song_path && (state.tab === "plans" || state.tab === "decoupage")) html += renderConsole(clip);
  if (state.tab === "plans") html += renderPlans(clip);
  else if (state.tab === "decoupage") html += renderDecoupageTab(clip);
  else if (state.tab === "dossier") html += renderDossier(clip);
  else if (state.tab === "decors") html += `<div id="decors-tab"><p class="loading">Chargement…</p></div>`;
  else html += renderJournal(clip);
  $view.innerHTML = html;
  bindClip();
  if (state.tab === "decors") loadDecors(clip);
  if (state.tab === "dossier") loadScenario(clip);
}

/* ----- scénariste : brainstorm brut -> propositions à accepter partie par partie ----- */

async function loadScenario(clip) {
  const box = document.getElementById("scenario-box");
  if (!box) return;
  let sc;
  try { sc = await api(`/api/clips/${encodeURIComponent(clip.slug)}/scenario`); } catch (e) { box.innerHTML = ""; return; }
  const prop = sc.proposal;
  const open = prop ? prop.parts.filter((x) => x.status === "proposed") : [];
  const parts = prop ? prop.parts.map((x) => `<div class="scenario-part ${x.status}">
      <div class="row"><b>${esc(x.title)}</b><span class="hint">${esc(sc.kinds[x.kind] || x.kind)}</span><span class="spacer"></span>
        ${x.status === "accepted" ? pill("Acceptée", "done") : x.status === "rejected" ? pill("Écartée", "wait") : ""}</div>
      ${x.why ? `<p class="hint">${esc(x.why)}</p>` : ""}
      ${x.status === "proposed" ? `<textarea rows="4" data-sctext="${esc(x.key)}">${esc(x.text)}</textarea>
        <div class="row"><button class="btn small ok" data-scpick="${esc(x.key)}:accept">Accepter${x.kind === "pitch" || x.kind === "concept" ? ` (remplace ton ${x.kind})` : " (ajouté au dossier)"}</button>
          <button class="btn small ghost" data-scpick="${esc(x.key)}:reject">Écarter</button></div>`
        : `<pre class="text">${esc(x.text)}</pre>`}</div>`).join("") : "";
  box.innerHTML = `<div class="panel-head"><h2>Atelier d'idées</h2>
      <span class="hint">Colle un brainstorm brut (conversation, notes). L'atelier en tire un pitch, un concept,
        des blocs et des idées de plans, en évitant les clichés. Tu acceptes ou écartes chaque partie.</span></div>
    ${sc.status === "requested" ? `<div class="agentbar">${led("work")}L'atelier d'idées lit ton brainstorm. Ses propositions arrivent ici.</div>` : ""}
    ${prop ? `${prop.resume ? `<p>${esc(prop.resume)}</p>` : ""}${open.length ? `<p class="hint">${open.length} partie${open.length > 1 ? "s" : ""} en attente de validation.</p>` : ""}
      <div class="stack" style="gap:10px">${parts}</div>` : ""}
    <details class="fold" ${prop ? "" : "open"}><summary>Coller un brainstorm</summary><div class="stack" style="gap:6px">
      <textarea id="brainstorm" rows="8" placeholder="Colle ici la conversation ou tes notes, telles quelles"></textarea>
      <div class="row"><button class="btn go" data-brainstorm>Envoyer à l'atelier d'idées</button></div></div></details>`;
  fitAll(box);
  box.onclick = async (ev) => {
    const t = ev.target.closest("button");
    if (!t) return;
    try {
      if (t.dataset.brainstorm !== undefined) {
        const text = document.getElementById("brainstorm").value.trim();
        if (!text) { toast("Colle d'abord ton brainstorm", "err"); return; }
        t.disabled = true;
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/brainstorm`, { json: { text } });
        toast("Brainstorm envoyé à l'atelier d'idées");
        return loadScenario(clip);
      }
      if (t.dataset.scpick) {
        const i = t.dataset.scpick.lastIndexOf(":");
        const key = t.dataset.scpick.slice(0, i), decision = t.dataset.scpick.slice(i + 1);
        const ta = box.querySelector(`[data-sctext="${CSS.escape(key)}"]`);
        t.disabled = true;
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/scenario`, { json: { key, decision, text: ta ? ta.value : null } });
        toast(decision === "accept" ? "Partie acceptée" : "Partie écartée");
        return showClip(clip.slug, "dossier", false);
      }
    } catch (e) { t.disabled = false; toast(e.message, "err"); }
  };
}

/* ----- console : transport + timeline ----- */

function songDuration(clip) {
  const last = clip.shots.length ? clip.shots[clip.shots.length - 1].t_end : 0;
  return Math.max(clip.duration_s || 0, last, 1);
}

const TL_ZOOMS = [1, 1.5, 2, 3, 4, 6, 8, 12, 16];
function tlMaxZoom() {
  const vw = document.getElementById("tlview")?.clientWidth || Math.min(window.innerWidth, 1200);
  return Math.max(1, Math.min(16, Math.floor(14000 / vw)));
}
function tlZoom() {
  if (state.tlZoom == null && state.clip) {
    state.tlZoom = prefs("tlzoom:" + state.clip.slug) || 1;
    state.tlScroll = prefs("tlscroll:" + state.clip.slug) || 0;
  }
  return Math.min(state.tlZoom || 1, tlMaxZoom());
}

function renderConsole(clip) {
  const total = songDuration(clip);
  const z = tlZoom();
  const pct = (t) => (100 * t) / total;
  const shotById = Object.fromEntries(clip.shots.map((s) => [s.id, s]));
  const blocks = clip.blocks.map((b, i) => {
    const ss = b.shot_ids.map((id) => shotById[id]).filter(Boolean);
    if (!ss.length) return "";
    const a = ss[0].t_start; const e = ss[ss.length - 1].t_end;
    return `<span class="tl-block ${i % 2 ? "odd" : ""}" data-goblock="${b.id ?? ""}" data-a="${a}" data-z="${e}" style="left:${pct(a)}%;width:${pct(e - a)}%"
      title="${esc(b.name)} · ${tc(a)} → ${tc(e)} · ${ss.length} plans · toucher pour zoomer"><span>${esc(b.name)}</span></span>`;
  }).join("");
  const pre = clip.stage === "script" || clip.stage === "decoupage_review";
  const shots = clip.shots.map((s) => `<span class="tl-shot c-${pre ? "wait" : shotState(s)} ${s.id === state.shotId ? "sel" : ""}" data-openshot="${s.id}"
      style="left:${pct(s.t_start)}%;width:${pct(s.t_end - s.t_start)}%" title="Plan ${s.num} · ${tc(s.t_start)} → ${tc(s.t_end)} · ${esc(s.description || "")}"><b>${s.num}</b></span>`).join("");
  const ll = clip.lyrics_lines || [];
  // chaque vers occupe sa ligne jusqu'au vers suivant de la même ligne (deux lignes alternées)
  const lyrics = ll.map((l, i) => {
    const until = ll[i + 2] ? ll[i + 2].start : total;
    return `<span class="r${i % 2}" style="left:${pct(l.start)}%;width:${pct(Math.max(until - l.start, 0.5))}%" title="${tc(l.start)} : ${esc(l.text)}">${esc(l.text)}</span>`;
  }).join("");
  const step = Math.max(1, [1, 2, 5, 10, 15, 30][[1, 2, 5, 10, 15, 30].findIndex((x) => (x * 100 * z) / total >= 6)] || 30);
  const ticks = [];
  for (let t = 0; t <= total; t += step) ticks.push(`<span style="left:${pct(t)}%">${tc(t).replace(/\.\d$/, "")}</span>`);
  return `<section class="console ${prefs("tlmini") ? "mini" : ""}" id="console">
      <div class="transport">
        <button class="playbtn" data-play aria-label="Lecture">${song.paused ? "▶" : "❚❚"}</button>
        <span class="clock mono" id="clock">${tc(song.currentTime || 0)} <span>/ ${tc(total)}</span></span>
        <span class="now" id="nowshot"></span>
        <span class="tl-tools">
          <button class="zbtn" data-tlzoom="out" aria-label="Dézoomer" ${z <= 1 ? "disabled" : ""}>−</button>
          <span class="mono zval">×${z}</span>
          <button class="zbtn" data-tlzoom="in" aria-label="Zoomer" ${z >= tlMaxZoom() ? "disabled" : ""}>＋</button>
          ${z > 1 ? `<button class="zbtn wide" data-tlzoom="fit">Tout voir</button>` : ""}
          <button class="zbtn wide" data-tlmini title="Réduire ou agrandir le lecteur">${prefs("tlmini") ? "Agrandir" : "Réduire"}</button>
        </span>
      </div>
      <div class="tl-viewport" id="tlview">
        <div class="timeline" id="timeline" data-total="${total}" style="width:${z * 100}%">
          <div class="tl-ticks">${ticks.join("")}</div>
          <div class="tl-blocks">${blocks}</div>
          <div class="tl-wave" id="wave"><canvas id="wave-base"></canvas>
            <div id="wave-played" style="position:absolute;inset:0;width:0;overflow:hidden"><canvas id="wave-top"></canvas></div></div>
          <div class="tl-shots">${shots}</div>
          ${lyrics ? `<div class="tl-lyrics">${lyrics}</div>` : ""}
          <span class="tl-head" id="tlhead"></span>
        </div>
      </div>
      <p class="tl-help">Touche un bloc pour zoomer dessus, un plan pour l'ouvrir. Pince à deux doigts sur la frise pour zoomer.</p>
    </section>`;
}

/* zoom de la frise : redessine seulement la console, garde la position */
function setTlZoom(z, centerT) {
  const clip = state.clip;
  const view = document.getElementById("tlview");
  const total = songDuration(clip);
  if (centerT == null && view) {
    const inner = document.getElementById("timeline").clientWidth;
    centerT = ((view.scrollLeft + view.clientWidth / 2) / inner) * total;
  }
  state.tlZoom = Math.max(1, Math.min(tlMaxZoom(), z));
  prefs("tlzoom:" + clip.slug, state.tlZoom);
  const node = document.getElementById("console");
  if (!node) return;
  node.outerHTML = renderConsole(clip);
  bindTimeline();
  drawWave().then(() => {
    const v = document.getElementById("tlview");
    const inner = document.getElementById("timeline").clientWidth;
    v.scrollLeft = Math.max(0, (centerT / total) * inner - v.clientWidth / 2);
  });
}

function focusRange(a, e) {
  const view = document.getElementById("tlview");
  const total = songDuration(state.clip);
  const z = Math.max(1, Math.min(tlMaxZoom(), (total / Math.max(1, e - a)) / 1.15));
  setTlZoom(Math.round(z * 10) / 10, (a + e) / 2);
  if (!view) return;
}

function bindTimeline() {
  const tl = document.getElementById("timeline");
  const view = document.getElementById("tlview");
  if (!tl || !view) return;
  tl.addEventListener("click", (e) => {
    if (e.target.closest("[data-openshot], [data-goblock]")) return;
    const r = tl.getBoundingClientRect();
    song.currentTime = ((e.clientX - r.left) / r.width) * +tl.dataset.total;
    updateHead();
  });
  const keepScroll = debounce(() => prefs("tlscroll:" + state.clip.slug, state.tlScroll), 400);
  view.addEventListener("scroll", () => { state.tlScroll = view.scrollLeft; keepScroll(); }, { passive: true });
  // pincement à deux doigts (tablette) et ctrl + molette (ordinateur)
  let pinch = null;
  view.addEventListener("touchstart", (e) => {
    if (e.touches.length !== 2) return;
    const [p, q] = e.touches;
    const r = tl.getBoundingClientRect();
    pinch = { d: Math.hypot(p.clientX - q.clientX, p.clientY - q.clientY), z: tlZoom(),
      t: (((p.clientX + q.clientX) / 2 - r.left) / r.width) * +tl.dataset.total, ratio: 1 };
  }, { passive: true });
  view.addEventListener("touchmove", (e) => {
    if (!pinch || e.touches.length !== 2) return;
    e.preventDefault();
    const [p, q] = e.touches;
    pinch.ratio = Math.hypot(p.clientX - q.clientX, p.clientY - q.clientY) / pinch.d;
    tl.style.transformOrigin = "left center";
    tl.style.transform = `scaleX(${pinch.ratio})`;
  }, { passive: false });
  view.addEventListener("touchend", () => {
    if (!pinch) return;
    const p = pinch; pinch = null;
    tl.style.transform = "";
    if (Math.abs(p.ratio - 1) > 0.08) setTlZoom(Math.round(p.z * p.ratio * 10) / 10, p.t);
  });
  view.addEventListener("wheel", (e) => {
    if (!e.ctrlKey) return;
    e.preventDefault();
    const r = tl.getBoundingClientRect();
    const t = ((e.clientX - r.left) / r.width) * +tl.dataset.total;
    setTlZoom(tlZoom() * (e.deltaY < 0 ? 1.5 : 1 / 1.5), t);
  }, { passive: false });
}

async function drawWave() {
  const clip = state.clip;
  const base = document.getElementById("wave-base");
  if (!base || !clip) return;
  let data = state.peaks[clip.slug];
  if (!data) {
    try { data = await api(`/api/clips/${encodeURIComponent(clip.slug)}/waveform`); } catch (e) { data = { peaks: [] }; }
    state.peaks[clip.slug] = data;
  }
  const total = songDuration(clip);
  const wave = document.getElementById("wave");
  const w = wave.clientWidth; const h = wave.clientHeight;
  const dpr = window.devicePixelRatio || 1;
  const paint = (canvas, colors) => {
    canvas.width = w * dpr; canvas.height = h * dpr;
    canvas.style.width = w + "px"; canvas.style.height = h + "px";
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    const grad = ctx.createLinearGradient(0, 0, w, 0);
    grad.addColorStop(0, colors[0]); grad.addColorStop(1, colors[1]);
    ctx.fillStyle = grad;
    const peaks = data.peaks || [];
    const span = (data.duration || total) / total;
    const bars = Math.floor(w / 3);
    for (let i = 0; i < bars; i++) {
      const x = i * 3;
      const p = peaks.length ? peaks[Math.min(peaks.length - 1, Math.floor((i / bars) / span * peaks.length))] || 0 : 0.15;
      const bh = Math.max(2, p * (h - 6));
      ctx.fillRect(x, (h - bh) / 2, 2, bh);
    }
  };
  paint(base, ["#5b3a8f", "#7a3a78"]);
  paint(document.getElementById("wave-top"), ["#b46cff", "#ff3fbf"]);
  const view = document.getElementById("tlview");
  if (view && state.tlScroll && tlZoom() > 1) view.scrollLeft = state.tlScroll;
  updateHead();
}
window.addEventListener("resize", debounce(drawWave, 200));

let stopAt = null;
function updateHead() {
  const tl = document.getElementById("timeline");
  if (!tl || !state.clip) return;
  const total = +tl.dataset.total;
  const pct = Math.min(100, (100 * (song.currentTime || 0)) / total);
  document.getElementById("tlhead").style.left = pct + "%";
  const view = document.getElementById("tlview");
  if (view && !song.paused && tlZoom() > 1) {
    const x = (pct / 100) * tl.clientWidth;
    if (x < view.scrollLeft || x > view.scrollLeft + view.clientWidth - 30) view.scrollLeft = Math.max(0, x - 40);
  }
  const played = document.getElementById("wave-played");
  if (played) played.style.width = pct + "%";
  const clock = document.getElementById("clock");
  if (clock) clock.innerHTML = `${tc(song.currentTime || 0)} <span>/ ${tc(total)}</span>`;
  const now = state.clip.shots.find((s) => song.currentTime >= s.t_start && song.currentTime < s.t_end);
  if (state.tab === "decoupage" && state.editor) markPlaying(now ? now.id : null);
  const nowEl = document.getElementById("nowshot");
  if (nowEl) nowEl.textContent = now ? `Plan ${now.num} · ${now.section || ""} · ${now.description}` : "";
  const btn = document.querySelector("[data-play]");
  if (btn) btn.textContent = song.paused ? "▶" : "❚❚";
}
song.addEventListener("timeupdate", () => {
  updateHead();
  if (stopAt && song.currentTime >= stopAt.end) {
    song.pause();
    stopAt.video?.pause();
    stopAt = null;
  }
});
song.addEventListener("play", updateHead);
song.addEventListener("pause", updateHead);

function playShot(shot) {
  const video = $drawer.querySelector("video");
  document.querySelectorAll("video").forEach((v) => { if (v !== video) v.pause(); });
  song.currentTime = shot.t_start;
  song.play().catch(() => {});
  if (video) { video.muted = true; video.currentTime = 0; video.play().catch(() => {}); }
  stopAt = { end: shot.t_end, video };
}

/* ----- onglet Plans ----- */

function stageSummary(clip) {
  const keys = ["image", "hd", "plan", "draft", "final"];
  const sums = Object.fromEntries(keys.map((k) => [k, { r: 0, w: 0, d: 0 }]));
  clip.shots.forEach((s) => {
    const cur = currentStep(s) === "lipsync" ? "final" : currentStep(s);
    const idx = STEP_INDEX[cur];
    const st = shotState(s);
    keys.forEach((k) => {
      const i = STEP_INDEX[k];
      if (s.status === "done" || i < idx) sums[k].d++;
      else if (i === idx) { if (st === "review") sums[k].r++; else if (st === "work") sums[k].w++; }
    });
  });
  const labels = { image: "Visuel draft", hd: "Visuel HD", plan: "Plan vidéo", draft: "Vidéo draft", final: "Vidéo HD + lip-sync" };
  const cards = keys.map((k) => `<button class="stage ${state.stepFilter === k ? "on" : ""}" data-stepfilter="${k}">
      <span class="name">${labels[k]}</span>
      <span class="nums"><span class="r" title="en attente de validation">● ${sums[k].r}</span><span class="w" title="en cours">● ${sums[k].w}</span><span class="d" title="validés">● ${sums[k].d}</span></span>
    </button>`).join("");
  const done = clip.shots.filter((s) => s.status === "done").length;
  return `<div class="stages">${cards}<div class="stage" style="cursor:default"><span class="name">Terminés</span>
      <span class="nums"><span class="d">${done} / ${clip.shots.length}</span></span></div></div>`;
}

function matchesFilter(s) {
  const st = shotState(s);
  if (state.filter === "review" && st !== "review") return false;
  if (state.filter === "work" && st !== "work") return false;
  if (state.filter === "change" && !["change", "failed"].includes(st)) return false;
  if (state.filter === "done" && st !== "done") return false;
  if (state.stepFilter) {
    const cur = currentStep(s) === "lipsync" ? "final" : currentStep(s);
    if (cur !== state.stepFilter || s.status === "done") return false;
  }
  return true;
}

function openBlocks(clip) {
  const saved = prefs("open:" + clip.slug);
  if (saved) return new Set(saved);
  // par défaut : les blocs où quelque chose t'attend, sinon le premier où ça travaille
  const shotById = Object.fromEntries(clip.shots.map((s) => [s.id, s]));
  const open = clip.blocks.filter((b) => b.shot_ids.some((id) => shotState(shotById[id] || {}) === "review")).map((b) => String(b.id));
  if (!open.length && clip.blocks.length) open.push(String(clip.blocks[0].id));
  return new Set(open);
}

function renderTile(s, clip) {
  const t = thumbOf(s);
  const st = shotState(s);
  const steps = stepStates(s).filter((x) => x.state !== "off")
    .map((x) => `<i class="c-${x.state === "wait" ? "wait" : x.state}" title="${esc(x.label)} : ${esc(x.text)}"></i>`).join("");
  const stepLabel = STEPS[STEP_INDEX[currentStep(s)]].label;
  return `<button class="tile ${st} ${s.id === state.shotId ? "sel" : ""}" data-openshot="${s.id}">
      <div class="thumb ${aspectClass(clip)}" style="${t ? `background-image:url('${media(t.path)}')` : ""}">
        ${t ? "" : "pas encore de visuel"}
        <span class="num">${s.num}</span>${s.singing ? `<span class="sing" title="Plan chanté">♪</span>` : ""}
        <span class="kind">${esc(stepLabel)}</span>
      </div>
      <div class="info">
        <p class="desc">${mentionHtml(s.description)}</p>
        <div class="foot">${clip.stage === "production" ? `${led(st)}<span>${esc(statusLabel(s))}</span>`
          : `${led("wait")}<span>${clip.stage === "decoupage_review" ? "Attend la validation du découpage" : "Découpage en préparation"}</span>`}</div>
        <div class="foot"><span class="mono" style="font-size:11px">${tc(s.t_start)} → ${tc(s.t_end)}</span>
          <span class="steps-mini">${steps}</span></div>
      </div>
    </button>`;
}

function renderPlans(clip) {
  if (!clip.shots.length) {
    return `<div class="panel"><h2>Pas encore de plans</h2><p class="hint" style="margin-top:8px">
      Les plans apparaissent ici une fois le découpage validé. Commence par l'onglet
      <a href="#/clip/${encodeURIComponent(clip.slug)}/decoupage">Découpage</a>.</p></div>`;
  }
  const preBanner = preProduction() ? `<div class="actionbox" style="margin-bottom:16px"><h3>Les plans ne sont pas encore en production</h3>
      <p class="hint">Ici, tu suivras chaque plan de son visuel à sa vidéo finale, avec ses boutons de validation. Ils démarrent quand tu valides le découpage.
        Pour l'instant, relis, modifie et valide les plans dans l'onglet Découpage.</p>
      <div class="row"><a class="btn go" href="#/clip/${encodeURIComponent(clip.slug)}/decoupage">Aller au découpage</a></div></div>` : "";
  const c = clipCounts(clip);
  const filters = [
    ["all", "Tous", clip.shots.length], ["review", "À valider", c.review], ["work", "En cours", c.work],
    ["change", "Retours et échecs", (c.change || 0) + (c.failed || 0)], ["done", "Terminés", c.done],
  ];
  const shotById = Object.fromEntries(clip.shots.map((s) => [s.id, s]));
  const open = openBlocks(clip);
  const filtering = state.filter !== "all" || state.stepFilter;
  const blocks = clip.blocks.map((b) => {
    const shots = b.shot_ids.map((id) => shotById[id]).filter(Boolean);
    const visible = shots.filter(matchesFilter);
    if (filtering && !visible.length) return "";
    const key = String(b.id);
    const isOpen = filtering ? state.tempOpen[key] !== false : open.has(key);
    const toReview = shots.filter((s) => shotState(s) === "review");
    const gates = {};
    toReview.forEach((s) => { const g = gateOf(s); gates[g] = (gates[g] || 0) + 1; });
    const leds = shots.map((s) => `<span class="led ${shotState(s)}" title="Plan ${s.num} · ${esc(statusLabel(s))}"></span>`).join("");
    const a = shots.length ? shots[0].t_start : 0; const z = shots.length ? shots[shots.length - 1].t_end : 0;
    const bulk = Object.entries(gates).filter(([g]) => g !== "hd").map(([g, n]) => {
      const cost = g === "videoplan" ? shots.filter((s) => s.status === "video_review").reduce((t, s) => t + ((s.estimate || {}).cost_total_usd || 0), 0) : 0;
      return `<button class="btn small" data-approveblock="${g}:${b.id ?? ""}">Valider les ${n} ${APPROVE_LABEL[g][1]}${cost ? ` · ~${money(cost)}` : ""}</button>`;
    }).join("");
    return `<section class="block ${isOpen ? "open" : ""} ${toReview.length ? "has-review" : ""}" id="block-${key}">
      <div class="block-head" data-toggleblock="${key}">
        <span class="chev">▶</span>
        <div class="block-title"><div class="name">${esc(b.name)}<span class="mono">${tc(a)} → ${tc(z)} · ${shots.length} plan${shots.length > 1 ? "s" : ""}</span></div>
          ${b.intention ? `<div class="intent">${esc(b.intention)}</div>` : ""}</div>
        <div class="block-side"><div class="leds">${leds}</div>
          ${toReview.length ? pill(`${toReview.length} à valider`, "review") : ""}</div>
      </div>
      <div class="block-body">
        ${bulk ? `<div class="block-actions">${bulk}</div>` : ""}
        <div class="tiles">${(filtering ? visible : shots).map((s) => renderTile(s, clip)).join("")}</div>
      </div>
    </section>`;
  }).join("");
  const nextReview = clip.shots.find((s) => shotState(s) === "review");
  return `${preBanner}${stageSummary(clip)}
    <div class="toolbar">
      ${filters.map(([k, l, n]) => `<button class="chip ${state.filter === k ? "on" : ""}" data-filter="${k}">${l}${n ? `<span class="n">${n}</span>` : ""}</button>`).join("")}
      ${state.stepFilter ? `<button class="chip on" data-stepfilter="">${esc(STEPS[STEP_INDEX[state.stepFilter]].label)} ✕</button>` : ""}
      <span class="spacer"></span>
      ${nextReview ? `<button class="btn small" data-openshot="${nextReview.id}">Prochain à valider →</button>` : ""}
      <button class="btn small ghost" data-allblocks="open">Tout déplier</button>
      <button class="btn small ghost" data-allblocks="close">Tout replier</button>
      <button class="btn small" data-assemble>Monter le clip</button>
      ${clip.montages.length ? `<a class="btn small ghost" href="${media(clip.montages[0])}" target="_blank" rel="noopener">Dernier montage</a>` : ""}
    </div>
    ${blocks || `<p class="empty">Aucun plan dans ce filtre.</p>`}
    <div class="legend" style="margin-top:16px">
      <span>${led("review")}en attente de validation</span><span>${led("work")}la machine travaille</span>
      <span>${led("done")}validé</span><span>${led("change")}modif demandée</span><span>${led("failed")}échec</span><span>${led("wait")}à venir</span></div>`;
}

/* ----- panneau de détail d'un plan ----- */

function shotHref(id) {
  return `#/clip/${encodeURIComponent(state.clip.slug)}/${state.tab}/p/${id}`;
}

function closeDrawerUi() {
  $drawer.hidden = true;
  $drawer.innerHTML = "";
  document.querySelector(".drawer-backdrop")?.remove();
}

function renderDrawer() {
  const clip = state.clip;
  const shot = clip && state.shotId ? clip.shots.find((s) => s.id === state.shotId) : null;
  document.querySelectorAll(".tile.sel, .tl-shot.sel").forEach((n) => n.classList.remove("sel"));
  if (!shot) { closeDrawerUi(); return; }
  document.querySelectorAll(`[data-openshot="${shot.id}"]`).forEach((n) => n.classList.add("sel"));
  if (!$drawer.hidden && $drawer.dataset.shot === String(shot.id) && $drawer.dataset.json === JSON.stringify(shot)) return;
  if (!$drawer.hidden && $drawer.dataset.shot === String(shot.id) && isBusy()) return;
  if ($drawer.dataset.shot !== String(shot.id)) state.step = null;
  const scroll = $drawer.querySelector(".drawer-body")?.scrollTop || 0;
  const sameShot = $drawer.dataset.shot === String(shot.id);
  $drawer.dataset.shot = shot.id;
  $drawer.dataset.json = JSON.stringify(shot);

  const idx = clip.shots.indexOf(shot);
  const prev = clip.shots[idx - 1]; const next = clip.shots[idx + 1];
  const nextReview = clip.shots.slice(idx + 1).concat(clip.shots.slice(0, idx)).find((s) => shotState(s) === "review");
  const steps = stepStates(shot);
  const step = state.step || currentStep(shot);
  const st = shotState(shot);
  const tags = [shot.framing, shot.motion && `mouvement ${shot.motion}`, shot.camera,
    shot.singing ? "♪ chanté" : null, ...(shot.characters || [])].filter(Boolean);

  const pipeline = steps.map((s) => `<button class="pstep ${s.state} ${s.key === step ? "on" : ""}" data-step="${s.key}" ${s.state === "off" ? "disabled" : ""}>
      <span class="lbl">${esc(s.label)}</span><span class="st">${led(s.state === "off" ? "wait" : s.state)}${esc(s.text)}</span></button>`).join("");

  const notes = [];
  if (shot.notes) notes.push(`<p class="note">${esc(shot.notes)}</p>`);
  const hist = shot.historique || [];
  if (hist.length) {
    const last = hist[0];
    notes.push(`<p class="note ${last.author === "michael" ? "michael" : last.author === "controleur" ? "qc" : ""}">
      <b>${esc(NOTE_AUTHOR[last.author] || last.author)} :</b> ${esc(last.text)}</p>`);
    if (hist.length > 1) {
      notes.push(`<details class="fold"><summary>Historique des remarques (${hist.length})</summary><div class="journal">${hist.map((n) =>
        `<div><span class="t">${esc(n.created_at.replace("T", " ").slice(5, 16))}</span><span><b>${esc(NOTE_AUTHOR[n.author] || n.author)}</b> : ${esc(n.text)}</span></div>`).join("")}</div></details>`);
    }
  }
  const wait = waitingText(shot);
  if (wait) notes.unshift(`<p class="note michael">${esc(wait)}</p>`);
  const locked = !["image_todo", "image_gen", "image_qc", "image_review", "hd_todo", "hd_gen", "hd_qc", "hd_review",
    "prompt_todo", "video_review", "change_requested", "failed"].includes(shot.status) && clip.stage === "production";
  const settings = `<div class="shot-settings stack" style="gap:8px">
      <label class="field"><span>Modèle vidéo</span>
        ${locked ? `<b>${esc((shot.video_model || {}).label || "")}</b>` : modelSelect(clip, shot.model_key || "", `data-shotmodel="${shot.id}"`)}</label>
      ${fitBadge(shot.fit)}
      ${shot.lipsync && !shot.lipsync.native ? `<label class="field"><span>Lip-sync</span>
        <select data-shotlipsync="${shot.id}">
          <option value="">Par défaut</option>
          ${(clip.lipsync_models || []).map((m) => `<option value="${m.key}" ${shot.lipsync.chosen && m.key === shot.lipsync.key ? "selected" : ""} ${m.usable ? "" : "disabled"}>${esc(m.label)}${m.usable ? "" : " (non branché)"}</option>`).join("")}
        </select></label>
        ${shot.lipsync.usable ? "" : `<p class="hint" style="color:#ffb547">Aucun lip-sync branché pour l'instant : ce plan s'arrêtera à cette étape.</p>`}` : ""}
      ${shot.lipsync && shot.lipsync.native ? `<p class="hint">Lip-sync fait par le modèle vidéo.</p>` : ""}
    </div>`;
  const detailBox = `<details class="fold" ${shot.detail ? "" : "open"}><summary>Prompt détaillé${shot.detail_edited ? " · écrit par toi" : ""}</summary><div class="stack" style="gap:6px">
      <textarea id="dt-${shot.id}" rows="4" data-mention placeholder="Le plan en détail : sujet, action, décor, lumière, cadrage. Tape @ pour citer un décor.">${esc(shot.detail || "")}</textarea>
      <div class="row"><button class="btn small" data-savedetail="${shot.id}">Enregistrer</button>
        <span class="hint">${(shot.assets || []).some((a) => a.kind === "image") ? "Le visuel déjà fait ne change pas tout seul : demande une modif pour le refaire." : "Le storyboard part de ce texte."}</span></div></div></details>`;

  const linked = new Set((shot.elements || []).map((e) => e.id));
  const elIndex = Object.fromEntries((clip.elements || []).map((e) => [e.id, e]));
  const KLAB = { decor: "Décor", objet: "Objet", figurant: "Figurant" };
  const elTile = (e, attrs, extra = "") => {
    const th = e.ref || (elIndex[e.id] || {}).thumb;
    return `<div class="eltile2 k-${e.kind}" ${attrs}>
        <div class="img" style="${th ? `background-image:url('${media(th)}')` : ""}">${th ? "" : `<span>pas encore d'image</span>`}</div>
        <span class="nm">${esc(e.name)}</span><span class="kd">${KLAB[e.kind] || e.kind}</span>${extra}</div>`;
  };
  const free = (clip.elements || []).filter((e) => !linked.has(e.id));
  const allChars = clip.characters_all || [];
  const inShot = new Set(shot.characters || []);
  const charTile = (c, attrs, extra = "") => `<div class="eltile2 k-perso" ${attrs}>
      <div class="img" style="${c.thumb ? `background-image:url('${media(c.thumb)}')` : ""}">${c.thumb ? "" : `<span>pas encore d'image</span>`}</div>
      <span class="nm">${esc(c.name)}</span><span class="kd">Personnage</span>${extra}</div>`;
  const shotChars = allChars.filter((c) => inShot.has(c.slug));
  const freeChars = allChars.filter((c) => !inShot.has(c.slug));
  const elBox = `<div class="shot-els panel">
      <div class="panel-head"><h3>Personnages, décors, objets et figurants du plan</h3>
        <a class="hint" href="#/clip/${encodeURIComponent(clip.slug)}/decors">tous les décors</a></div>
      <p class="hint">Leur image sert de référence au visuel du plan. Pour en ajouter : touche ＋, ou tape @ dans le prompt détaillé.</p>
      <div class="eltiles2">
        ${shotChars.map((c) => charTile(c, "", `<button class="x" data-charunlink="${esc(c.slug)}" title="Retirer du plan" aria-label="Retirer du plan">✕</button>`)).join("")}
        ${(shot.elements || []).map((e) => elTile(e, "", `<button class="x" data-elunlink="${e.id}" title="Retirer du plan" aria-label="Retirer du plan">✕</button>`)).join("")}
        ${free.length || freeChars.length ? `<button class="eltile2 add" data-elpick><span class="plus">＋</span><span class="nm">Ajouter</span></button>` : ""}
      </div>
      <div class="elpicker" id="elpicker" hidden>
        <p class="hint">Touche ce que tu veux ajouter au plan.</p>
        ${freeChars.length ? `<h4>Personnages</h4><div class="eltiles2">${freeChars.map((c) => charTile(c, `data-charadd="${esc(c.slug)}" role="button" tabindex="0"`)).join("")}</div>` : ""}
        ${["decor", "figurant", "objet"].map((k) => free.filter((e) => e.kind === k)).filter((l) => l.length)
          .map((l) => `<h4>${KLAB[l[0].kind]}s</h4><div class="eltiles2">${l.map((e) => elTile(e, `data-eladd="${e.id}" role="button" tabindex="0"`)).join("")}</div>`).join("")}
      </div></div>`;
  if (!document.querySelector(".drawer-backdrop")) {
    const bd = document.createElement("div");
    bd.className = "drawer-backdrop";
    bd.addEventListener("click", () => { location.hash = `#/clip/${encodeURIComponent(clip.slug)}/${state.tab}`; });
    document.body.appendChild(bd);
  }
  $drawer.hidden = false;
  $drawer.innerHTML = `
    <div class="drawer-head">
      <button class="iconbtn" data-goshot="${prev ? prev.id : ""}" ${prev ? "" : "disabled"} aria-label="Plan précédent">‹</button>
      <button class="iconbtn" data-goshot="${next ? next.id : ""}" ${next ? "" : "disabled"} aria-label="Plan suivant">›</button>
      <div class="title"><b>Plan ${shot.num} · ${esc(shot.section || "")}</b>
        <span class="mono">${tc(shot.t_start)} → ${tc(shot.t_end)} · ${(shot.t_end - shot.t_start).toFixed(1)} s</span></div>
      <span class="spacer"></span>
      ${nextReview ? `<button class="btn small" data-goshot="${nextReview.id}">Prochain à valider</button>` : ""}
      <button class="iconbtn" data-closedrawer aria-label="Fermer">✕</button>
    </div>
    <div class="drawer-body">
      <div class="stack" style="gap:8px">
        <div class="row">${pill(statusLabel(shot), st)}
          <span class="spacer"></span><button class="btn small ghost" data-playshot="${shot.id}">▶ Lire dans le morceau</button></div>
        <p>${mentionHtml(shot.description)}</p>
        <div class="row" style="gap:6px">${tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      </div>
      ${detailBox}
      ${elBox}
      ${settings}
      <div class="pipeline">${pipeline}</div>
      ${notes.join("")}
      ${renderStepPanel(shot, step)}
      ${shot.image_prompt ? `<details class="fold"><summary>Prompt du visuel</summary><div><pre class="text">${esc(shot.image_prompt)}</pre></div></details>` : ""}
      ${(shot.reviews || []).length ? `<details class="fold"><summary>Historique des validations</summary><div class="journal">${shot.reviews.map((r) =>
        `<div><span class="t">${esc(r.created_at.replace("T", " ").slice(5, 16))}</span><span>${esc(APPROVE_LABEL[r.gate]?.[1] || r.gate)} : ${r.decision === "approve" ? "validé" : "modif : " + esc(r.comment || "")}${r.handled_note ? ` <span class="dim">(${esc(r.handled_note)})</span>` : ""}</span></div>`).join("")}</div></details>` : ""}
      <p class="hint mono">Dépensé sur ce plan : ${money(shot.cost_usd)}</p>
    </div>`;
  if (sameShot) $drawer.querySelector(".drawer-body").scrollTop = scroll;
  bindCompare($drawer);
  $drawer.onclick = drawerClick;
  $drawer.onchange = async (ev) => {
    const t = ev.target;
    const reload = () => showClip(clip.slug, state.tab, false);
    try {
      if (t.dataset.shotmodel) {
        if (!t.value) { toast("Choisis un modèle dans la liste", "err"); return; }
        await api(`/api/shots/${t.dataset.shotmodel}/model`, { json: { model_key: t.value } });
        toast("Modèle changé"); return reload();
      }
      if (t.dataset.shotlipsync) {
        await api(`/api/shots/${t.dataset.shotlipsync}/lipsync`, { json: { model_key: t.value || null } });
        toast("Lip-sync changé"); return reload();
      }
    } catch (e) { toast(e.message, "err"); reload(); }
  };
}

function viewerFor(shot, kinds, clip, emptyText) {
  const list = assetsOf(shot, kinds);
  const key = `${shot.id}:${kinds.join(",")}`;
  const picked = list.find((a) => a.id === state.picked[key]) || bestAsset(shot, kinds);
  const generating = (shot.assets || []).some((a) => kinds.includes(a.kind) && a.status === "generating");
  let inner;
  if (!picked) {
    inner = `<div class="none">${generating ? `${led("work")} Génération en cours…` : esc(emptyText)}</div>`;
  } else if (isVideo(picked.path)) {
    const poster = thumbOf(shot);
    inner = `<video src="${media(picked.path)}" controls playsinline preload="metadata" muted ${poster ? `poster="${media(poster.path)}"` : ""}></video>`;
  } else {
    inner = `<img src="${media(picked.path)}" alt="" data-zoom="${media(picked.path)}">`;
  }
  const versions = list.length > 1 || (picked && list.length) ? `<div class="versions">${list.map((a) =>
    `<button class="${a.id === picked?.id ? "on" : ""} ${a.status}" data-pick="${key}|${a.id}" title="${esc(a.status)}${a.error ? " · " + esc(a.error) : ""}">v${a.version}${a.status === "validated" ? " ✓" : ""}</button>`).join("")}
    ${picked && picked.model_key ? `<span class="hint">${esc(picked.model_key)} · ${money(picked.cost_usd)}</span>` : ""}</div>` : "";
  return { html: `<div class="viewer">${inner}</div>${versions}`, asset: picked };
}

function feedbackBox(shot, placeholder) {
  return `<div class="feedback stack" id="fb-${shot.id}" hidden>
      <textarea placeholder="${esc(placeholder)}"></textarea>
      <div class="row"><button class="btn go" data-sendchange="${shot.id}">Envoyer le retour</button>
        <button class="btn ghost" data-cancelchange="${shot.id}">Annuler</button></div>
    </div>`;
}

function renderStepPanel(shot, step) {
  const clip = state.clip;
  const gate = gateOf(shot);
  const isGate = gate && GATE_STEP[gate] === step || (gate === "finals" && step === "lipsync");
  if (step === "plan") return renderPlanVideo(shot, gate === "videoplan");
  const def = STEPS[STEP_INDEX[step]];
  if (step === "hd" && gate === "hd") {
    const work = bestAsset(shot, ["image"]);
    const hd = bestAsset(shot, ["image_hd"]);
    return `<div class="actionbox"><h3>Écart signalé sur la HD</h3>
      <p class="hint">Le contrôleur a trouvé une différence entre le visuel draft que tu as validé et sa version HD.
        Fais glisser le curseur pour comparer.</p>
      ${work && hd ? compareWidget(media(work.path), media(hd.path), "Visuel draft validé", "Visuel HD") : ""}
      <div class="row">
        <button class="btn ok" data-approve="${shot.id}">Valider la HD</button>
        <button class="btn" data-decision="${shot.id}:use_work_image">Partir du visuel draft</button>
        <button class="btn ghost" data-openchange="${shot.id}">Demander une modif</button>
      </div>
      ${feedbackBox(shot, "Ce que la HD a perdu ou changé (boucles, regard, grain de peau…)")}
    </div>`;
  }
  const v = viewerFor(shot, def.kinds, clip, {
    image: "Le storyboard prépare ce visuel.",
    hd: "La HD part dès que le visuel draft est validé.",
    draft: "La vidéo draft part dès que le plan vidéo est validé.",
    final: "La vidéo HD part dès que la vidéo draft est validée.",
    lipsync: "Le lip-sync se fait après la vidéo HD.",
  }[step]);
  let html = v.html;
  if (isGate) {
    const label = step === "lipsync" || step === "final" ? APPROVE_LABEL.finals[0] : APPROVE_LABEL[gate][0];
    const ph = {
      images: "Ce qui ne va pas et ce que tu veux à la place (cadrage, pose, lumière, tenue, décor…)",
      drafts: "Mouvement, rythme, caméra, rendu : ce que tu veux changer",
      finals: "Ce qui ne va pas sur la vidéo HD ou le lip-sync",
    }[gate];
    html += `<div class="actionbox"><h3>À toi de valider</h3>
      <div class="row">
        <button class="btn ok" data-approve="${shot.id}">${esc(label)}</button>
        <button class="btn ghost" data-openchange="${shot.id}">Demander une modif</button>
      </div>
      ${feedbackBox(shot, ph)}</div>`;
  }
  if (step === "hd" && shot.status !== "hd_review") {
    const work = bestAsset(shot, ["image"]);
    const hd = bestAsset(shot, ["image_hd"]);
    if (work && hd) html += `<details class="fold"><summary>Comparer avec le visuel draft</summary><div>${compareWidget(media(work.path), media(hd.path), "Visuel draft", "Visuel HD")}</div></details>`;
  }
  if (shot.status === "failed") {
    html += `<div class="actionbox" style="border-color:#ff4d6688"><h3 style="color:var(--red)">Échec</h3>
      <p class="hint">L'orchestrateur va tenter de relancer. Tu peux aussi le faire toi-même.</p>
      <div class="row"><button class="btn" data-retry="${shot.id}">Relancer l'étape</button></div></div>`;
  }
  return html;
}

function renderPlanVideo(shot, isGate) {
  const est = shot.estimate;
  if (!shot.model_key && !shot.video_prompt) {
    return `<div class="viewer"><div class="none">${shot.status === "prompt_todo" ? `${led("work")} Le routeur choisit le modèle, le prompteur écrit le prompt.` : "Le plan vidéo se prépare une fois le visuel HD prêt."}</div></div>`;
  }
  const hd = bestAsset(shot, ["image_hd"]) || bestAsset(shot, ["image"]);
  const costs = est ? `<div class="costline">
      <span>Vidéo draft <b>${money(est.cost_draft_usd)}</b></span>
      <span>Vidéo HD <b>${est.final_mode === "keep" ? "incluse" : money(est.cost_final_usd)}</b></span>
      ${shot.singing ? `<span>Lip-sync <b>${money(est.cost_lipsync_usd)}</b></span>` : ""}
      <span>Total estimé <b>${money(est.cost_total_usd)}</b></span>
      <span>Durée générée <b>${est.duration} s</b> pour un plan de ${est.shot_seconds} s</span></div>` : "";
  const providers = state.clip.providers || [];
  const provLabel = (k) => (providers.find((p) => p.key === k) || { label: k }).label;
  let modelHtml;
  if (isGate && shot.model_options) {
    const opts = shot.model_options.slice().sort((a, b) => (b.usable - a.usable) || (a.effective_usd - b.effective_usd) || (a.cost_total_usd - b.cost_total_usd));
    const card = (m) => `<label class="model ${m.key === shot.model_key ? "on" : ""} ${m.usable ? "" : "off"}">
        <input type="radio" name="model-${shot.id}" value="${m.key}" ${m.key === shot.model_key ? "checked" : ""} ${m.usable ? "" : "disabled"} data-model="${shot.id}">
        <span><span class="nm">${esc(m.label)}</span> <span class="hint">· ${esc(provLabel(m.provider))}${m.usable ? "" : " (clé manquante)"}</span>
          ${m.to_test ? `<span class="pill work" style="margin-left:6px">à tester</span>` : ""}<br>
          <span class="uf">${esc(m.use_for)}</span></span>
        <span class="cost">${m.on_credits ? `<span style="color:var(--led)">crédits</span><small>valeur ~${money(m.cost_total_usd)}</small>` : `~${money(m.cost_total_usd)}`}<small>${m.duration} s générées</small></span></label>`;
    const fit = opts.filter((m) => m.fits); const other = opts.filter((m) => !m.fits);
    modelHtml = `<div class="models">${fit.map(card).join("")}</div>
      ${other.length ? `<details class="fold"><summary>Autres modèles (moins adaptés à ce plan, ou format et durée non tenus) : ${other.length}</summary><div class="models">${other.map(card).join("")}</div></details>` : ""}
      ${providers.filter((p) => !p.usable).length ? `<p class="hint">Sans clé pour l'instant : ${providers.filter((p) => !p.usable).map((p) => esc(p.label)).join(", ")}. Voir la page <a href="#/fournisseurs">Fournisseurs</a>.</p>` : ""}`;
  } else {
    modelHtml = est ? `<dl class="kv"><dt>Fournisseur</dt><dd>${esc(provLabel(est.provider))}</dd><dt>Modèle</dt><dd>${esc(est.model_label)}</dd></dl>` : "";
  }
  return `<div class="two-col">
      <div>${hd ? `<div class="viewer"><img src="${media(hd.path)}" data-zoom="${media(hd.path)}" alt=""></div><p class="hint" style="margin-top:6px">Image de départ de la vidéo</p>` : ""}</div>
      <div class="stack" style="gap:10px">
        <h3>Choix du modèle</h3>
        ${shot.route_reason ? `<p class="note">Raison du routeur : ${esc(shot.route_reason)}</p>` : ""}
        ${isGate ? "" : modelHtml}
      </div>
    </div>
    ${isGate ? modelHtml : ""}
    ${costs}
    <div class="stack" style="gap:6px">
      <h3>Prompt vidéo</h3>
      ${isGate ? `<textarea id="vp-${shot.id}" rows="6">${esc(shot.video_prompt || "")}</textarea>
        <div class="row"><button class="btn small" data-saveprompt="${shot.id}">Enregistrer le prompt</button>
        <span class="hint">Le prompt est en anglais, c'est la langue des modèles.</span></div>`
        : `<pre class="text">${esc(shot.video_prompt || "")}</pre>`}
      ${shot.negative_prompt ? `<p class="hint">À éviter : ${esc(shot.negative_prompt)}</p>` : ""}
    </div>
    ${isGate ? `<div class="actionbox"><h3>À toi de valider</h3>
      <p class="hint">Rien n'est dépensé tant que tu n'as pas validé. Ensuite la vidéo draft part, puis la vidéo HD
        ${shot.singing ? "et le lip-sync " : ""}après ta validation de la draft.</p>
      <div class="row">
        <button class="btn ok" data-approve="${shot.id}">Valider et lancer la vidéo${est ? ` · ~${money(est.cost_draft_usd)}` : ""}</button>
        <button class="btn ghost" data-openchange="${shot.id}">Demander une modif</button>
      </div>
      ${feedbackBox(shot, "Mouvement, caméra, action, ou modèle à reconsidérer")}</div>` : ""}`;
}

async function drawerClick(ev) {
  const t = ev.target.closest("button, [data-zoom], input[data-model], [data-eladd], [data-charadd]");
  if (ev.target.matches && ev.target.matches("select")) return;
  if (!t) return;
  const d = t.dataset;
  const clip = state.clip;
  const reload = () => showClip(clip.slug, state.tab, false);
  try {
    if (d.zoom) return lightbox(d.zoom);
    if (d.closedrawer !== undefined) { location.hash = `#/clip/${encodeURIComponent(clip.slug)}/${state.tab}`; return; }
    if (d.goshot) { location.hash = shotHref(d.goshot); return; }
    if (d.step) { state.step = d.step; $drawer.dataset.json = ""; renderDrawer(); return; }
    if (d.pick) {
      const [key, id] = d.pick.split("|");
      state.picked[key] = +id; $drawer.dataset.json = ""; renderDrawer(); return;
    }
    if (d.playshot) return playShot(clip.shots.find((s) => s.id === +d.playshot));
    if (d.openchange) {
      const fb = document.getElementById("fb-" + d.openchange);
      fb.hidden = false; fb.querySelector("textarea").focus(); return;
    }
    if (d.cancelchange) { document.getElementById("fb-" + d.cancelchange).hidden = true; return; }
    if (d.model) {
      await api(`/api/shots/${d.model}/model`, { json: { model_key: t.value } });
      toast("Modèle changé");
      return reload();
    }
    if (d.elpick !== undefined) {
      const pk = document.getElementById("elpicker");
      pk.hidden = !pk.hidden;
      if (!pk.hidden) pk.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }
    if (d.charadd || d.charunlink) {
      await api(`/api/shots/${state.shotId}/characters`, { json: { slug: d.charadd || d.charunlink, remove: !!d.charunlink } });
      toast(d.charadd ? "Ajouté au plan (et casté dans le clip si besoin)" : "Retiré du plan"); return reload();
    }
    if (d.eladd) {
      await api(`/api/shots/${state.shotId}/elements`, { json: { element_id: +d.eladd } });
      toast("Ajouté au plan"); return reload();
    }
    if (d.elunlink) {
      await api(`/api/shots/${state.shotId}/elements`, { json: { element_id: +d.elunlink, remove: true } });
      toast("Retiré du plan"); return reload();
    }
    if (d.savedetail) {
      const text = document.getElementById("dt-" + d.savedetail).value;
      await api(`/api/shots/${d.savedetail}/detail`, { json: { text } });
      toast("Prompt détaillé enregistré");
      return reload();
    }
    if (d.saveprompt) {
      const text = document.getElementById("vp-" + d.saveprompt).value;
      await api(`/api/shots/${d.saveprompt}/video-prompt`, { json: { text } });
      toast("Prompt enregistré");
      return reload();
    }
    if (d.approve) {
      const sid = +d.approve;
      const shot = clip.shots.find((s) => s.id === sid);
      const gate = gateOf(shot);
      const kinds = gate === "images" ? ["image"] : gate === "drafts" ? ["draft"] : null;
      const assetId = kinds ? state.picked[`${sid}:${kinds.join(",")}`] || null : null;
      const vp = document.getElementById("vp-" + sid);
      if (vp && vp.value.trim() !== (shot.video_prompt || "").trim()) {
        await api(`/api/shots/${sid}/video-prompt`, { json: { text: vp.value } });
      }
      t.disabled = true;
      await api(`/api/shots/${sid}/review`, { json: { decision: "approve", asset_id: assetId } });
      toast(`Plan ${shot.num} validé`);
      state.step = null;
      const next = clip.shots.slice(clip.shots.indexOf(shot) + 1).find((s) => shotState(s) === "review" && s.id !== sid);
      await showClip(clip.slug, state.tab, false);
      if (next) location.hash = shotHref(next.id);
      return;
    }
    if (d.decision) {
      const [sid, decision] = d.decision.split(":");
      await api(`/api/shots/${sid}/review`, { json: { decision } });
      toast("C'est noté");
      return reload();
    }
    if (d.sendchange) {
      const sid = +d.sendchange;
      const text = document.querySelector(`#fb-${sid} textarea`).value.trim();
      if (!text) { toast("Explique la modification souhaitée", "err"); return; }
      t.disabled = true;
      await api(`/api/shots/${sid}/review`, { json: { decision: "change", comment: text } });
      toast("Retour envoyé à l'orchestrateur");
      return reload();
    }
    if (d.retry) {
      await api(`/api/shots/${d.retry}/retry`, { method: "POST" });
      toast("Étape relancée");
      return reload();
    }
  } catch (e) {
    t.disabled = false;
    toast(e.message, "err");
  }
}

/* ----- onglet Découpage ----- */

function editorFromClip(clip) {
  const shotById = Object.fromEntries(clip.shots.map((s) => [s.id, s]));
  const blocks = clip.blocks.map((b) => ({
    name: b.name, intention: b.intention || "", look: b.look || "",
    shots: b.shot_ids.map((id) => shotById[id]).filter(Boolean).map((s) => ({
      id: s.id, t_start: tc(s.t_start), t_end: tc(s.t_end), description: s.description, detail: s.detail || "",
      detail_edited: !!s.detail_edited, model_key: s.model_key || "", singing: !!s.singing, cut_ok: !!s.cut_ok,
      pending: (clip.pending_reviews || []).filter((r) => r.gate === "decoupage" && r.shot_id === s.id).map((r) => r.comment),
      framing: s.framing, motion: s.motion, camera: s.camera, characters: s.characters, notes: s.notes,
    })),
  }));
  if (!blocks.length) blocks.push({ name: "Intro", intention: "", shots: [{ t_start: "0:00.0", t_end: "", description: "", singing: false, characters: defaultCast(clip) }] });
  const open = new Set(prefs("decopen:" + clip.slug) || []);
  const wasOpen = new Set((state.editor || []).flatMap((b) => b.shots.filter((x) => x._open && x.id).map((x) => x.id)));
  blocks.forEach((b, i) => { b._open = open.has(i); b.shots.forEach((x) => { x._open = wasOpen.has(x.id); }); });
  return blocks;
}

function defaultCast(clip) { return clip.casting.map((c) => c.character_slug); }

function renderDecoupageTab(clip) {
  const editable = clip.stage === "script" || clip.stage === "decoupage_review";
  if (!editable) return renderDecoupageRead(clip);
  if (!state.editor || !state.editorDirty) state.editor = editorFromClip(clip);
  let head = "";
  const allShots = state.editor.flatMap((b) => b.shots);
  const fits = allShots.map((s) => fitFor(clip, s.model_key, parseTc(s.t_end) - parseTc(s.t_start)));
  const nWarn = fits.filter((f) => f && f.level === "warn").length;
  const nBad = fits.filter((f) => f && f.level === "bad").length;
  const incomplete = (clip.incomplete || []).length;
  const summary = clip.shots.length ? `<div class="panel dec-summary" style="margin-bottom:16px">
      <div class="row" style="gap:14px">
        <span>${incomplete ? `${pill(`${incomplete} plan${incomplete > 1 ? "s" : ""} incomplet${incomplete > 1 ? "s" : ""}`, "review")}` : pill("Tous les plans sont complets", "done")}</span>
        ${incomplete ? `<button class="btn small" data-complete>Faire compléter par le scénariste</button>` : ""}
        <span class="spacer"></span>
        <span class="mono">Vidéo estimée : ~${money(clip.video_cost_usd)}</span>
      </div>
      <p class="hint" style="margin-top:6px">Un plan complet a « ce qu'on voit », son prompt détaillé, son cadrage et son mouvement.
        ${nWarn ? `<b>${nWarn}</b> plan${nWarn > 1 ? "s" : ""} plus court${nWarn > 1 ? "s" : ""} que ce que le modèle génère (payé${nWarn > 1 ? "s" : ""} en trop).` : ""}
        ${nBad ? `<b style="color:var(--red)">${nBad}</b> plan${nBad > 1 ? "s" : ""} trop long${nBad > 1 ? "s" : ""} pour son modèle.` : ""}
        Veo ne sait pas faire plusieurs plans dans une même prise : fusionner deux plans courts voisins coûte moins cher.</p>
    </div>` : "";
  if (clip.stage === "decoupage_review") {
    head = `<div class="actionbox" style="margin-bottom:16px"><h3>Découpage à valider</h3>
      <p class="hint">Relis chaque plan : ce qu'on voit, son prompt détaillé, son modèle vidéo, et écoute-le avec ▶ (le lecteur reste en haut). Corrige directement
        ci-dessous, enregistre, puis valide pour lancer le storyboard. Les plans incomplets et les durées mal adaptées
        au modèle sont signalés.</p>
      ${clip.script_notes ? `<details class="fold"><summary>Notes de relecture du scénariste</summary><div><pre class="text">${esc(clip.script_notes)}</pre></div></details>` : ""}
      <div class="row"><button class="btn ok" data-cut="approve">Valider le découpage</button>
        <button class="btn ghost" data-cut="open">Demander des changements</button></div>
      <div class="feedback stack" id="fb-cut" hidden>
        <textarea placeholder="Ex. : fusionner les plans 4 et 5, le refrain commence sur un plan large…"></textarea>
        <div class="row"><button class="btn go" data-cut="change">Envoyer au scénariste</button></div></div>
    </div>`;
  } else {
    head = `<div class="panel" style="margin-bottom:16px"><div class="panel-head"><h2>Ton découpage</h2></div>
      <p class="hint">Saisis tes blocs (intro, couplet, refrain…) et les plans de chaque bloc avec leurs timecodes,
        en écoutant le morceau. Format des temps : <span class="mono">1:04.2</span> ou <span class="mono">64.2</span>.
        Tu peux aussi déposer ton découpage dans le dossier de réalisation : le scénariste le reprendra.
        Une fois prêt, envoie le tout depuis l'onglet <a href="#/clip/${encodeURIComponent(clip.slug)}/dossier">Dossier</a>.</p>
      ${clip.script_notes ? `<details class="fold" style="margin-top:10px" open><summary>Notes du scénariste</summary><div><pre class="text">${esc(clip.script_notes)}</pre></div></details>` : ""}
    </div>`;
  }
  let n = 0;
  const nOpen = state.editor.filter((b) => b._open).length;
  const tools = `<div class="dec-tools">
      <span class="hint">${state.editor.length} blocs · ${allShots.length} plans · <b>${allShots.filter((x) => x.cut_ok).length} validés</b></span><span class="spacer"></span>
      <button class="btn small ghost" data-decall="open" ${nOpen === state.editor.length ? "disabled" : ""}>Tout déplier</button>
      <button class="btn small ghost" data-decall="close" ${nOpen ? "" : "disabled"}>Tout replier</button>
    </div>`;
  const blocks = state.editor.map((b, bi) => {
    const first = n + 1;
    const a = b.shots.length ? parseTc(b.shots[0].t_start) : null;
    const e = b.shots.length ? parseTc(b.shots[b.shots.length - 1].t_end) : null;
    const todo = b.shots.filter((s) => !(s.detail && s.framing && s.motion)).length;
    const shotsHtml = b.shots.map((s, si) => {
      n++;
      const key = `${bi}:${si}`;
      const fit = fitFor(clip, s.model_key, parseTc(s.t_end) - parseTc(s.t_start));
      const tech = [FRAMING_FR[s.framing] || s.framing, s.motion && `mouvement ${MOTION_FR[s.motion] || s.motion}`, s.camera].filter(Boolean).join(" · ");
      const complete = s.detail && s.framing && s.motion;
      const pend = (s.pending || []).length;
      return `<div class="dshot ${s._open ? "open" : ""} ${bi % 2 ? "alt" : ""} ${s.cut_ok ? "ok" : ""}" id="dshot-${key}">
        <div class="dshot-head" data-toggleshot="${key}">
          <span class="dshot-n">${n}</span>
          ${s.cut_ok ? `<span class="pill done">validé</span>` : ""}
          ${pend ? `<span class="pill work">modif en cours</span>` : ""}
          <span class="dshot-tc mono">${esc(s.t_start || "?")} → ${esc(s.t_end || "?")}</span>
          <span class="dshot-dur mono" data-dur="${key}">${durText(s)}</span>
          ${clip.song_path ? `<button class="iconbtn playmini" data-decplay="${key}" title="Écouter ce plan" aria-label="Écouter ce plan">▶</button>` : ""}
          ${s.singing ? `<span class="dshot-sing" title="Plan chanté : lip-sync">♪</span>` : ""}
          <span class="dshot-model hint">${esc((modelOf(clip, s.model_key) || {}).label || "")}</span>
          <span data-fit="${key}">${fit && fit.level !== "ok" ? `<span class="fit ${fit.level}">${esc(fit.short)}</span>` : ""}</span>
          <span class="spacer"></span>
          ${complete || pend ? "" : `<span class="pill review">à compléter</span>`}
          <span class="chev">›</span>
        </div>
        <div class="dshot-sum" data-toggleshot="${key}">
          <p class="dshot-desc" data-desc="${key}">${mentionHtml(s.description) || `<i class="hint">Pas encore de description</i>`}</p>
          ${tech ? `<p class="dshot-tech">${esc(tech)}</p>` : ""}
        </div>
        <div class="dshot-body">
          <label class="field"><span>Modèle vidéo</span>${modelSelect(clip, s.model_key, `data-sf="${key}:model_key" aria-label="Modèle vidéo"`)}</label>
          <div data-fitfull="${key}">${fitHtml(fit, key)}</div>
          <div class="dshot-row">
            <label class="field"><span>Début</span><input class="tc" type="text" inputmode="decimal" value="${esc(s.t_start)}" data-sf="${key}:t_start" placeholder="0:00.0"></label>
            <label class="field"><span>Fin</span><input class="tc" type="text" inputmode="decimal" value="${esc(s.t_end)}" data-sf="${key}:t_end" placeholder="0:04.0"></label>
            <label class="sing" title="Plan chanté face caméra : lip-sync"><input type="checkbox" ${s.singing ? "checked" : ""} data-sf="${key}:singing"> ♪ chanté</label>
          </div>
          <label class="field"><span>Ce qu'on voit : ton idée, aussi détaillée que tu veux</span>
            <textarea rows="3" data-mention data-sf="${key}:description" placeholder="Décris le plan comme tu le vois : action, émotion, cadrage, détails qui comptent. Tape @ pour citer un personnage ou un décor.">${esc(s.description)}</textarea></label>
          <label class="field"><span>Prompt détaillé${s.detail_edited ? " · écrit par toi" : s.detail ? " · écrit par le scénariste" : " · à écrire"}</span>
            <textarea rows="5" data-mention data-sf="${key}:detail" placeholder="Le plan en détail : sujet, action, décor, lumière, cadrage. Le scénariste le remplit, tu peux le réécrire.">${esc(s.detail || "")}</textarea></label>
          ${pend ? `<div class="agentbar">${led("work")}Modif demandée au scénariste : « ${esc(s.pending[s.pending.length - 1])} ». Il s'en occupe.</div>` : ""}
          <div class="row dshot-main" style="gap:8px">
            <button class="btn small" data-savedec>Enregistrer</button>
            ${s.id ? `<button class="btn small ${s.cut_ok ? "ghost" : "ok"}" data-cutok="${s.id}:${s.cut_ok ? "0" : "1"}">${s.cut_ok ? "Retirer la validation" : "Valider ce plan"}</button>
              <button class="btn small ghost" data-cutask="${key}">Demander une modif au scénariste</button>` : ""}
          </div>
          <div class="feedback stack" id="cutask-${key}" hidden>
            <textarea rows="2" placeholder="Ce que tu veux changer dans ce plan"></textarea>
            <div class="row"><button class="btn small go" data-cutsend="${key}:${s.id || ""}">Envoyer au scénariste</button></div></div>
          <div class="dshot-acts">
            ${si < b.shots.length - 1 ? `<button class="btn small ghost" data-mergeshot="${key}">Fusionner avec le plan suivant</button>` : ""}
            <button class="btn small ghost" data-splitshot="${key}">Couper en deux</button>
            <button class="btn small ghost danger" data-delshot="${key}">Supprimer le plan</button>
          </div>
        </div>
      </div>`;
    }).join("");
    return `<section class="dblock ${b._open ? "open" : ""} ${bi % 2 ? "alt" : ""}" id="decblock-${bi}">
      <div class="dblock-head" data-toggledec="${bi}">
        <span class="chev">›</span>
        <span class="dblock-num">Bloc ${bi + 1}</span>
        <span class="dblock-title">
          <b>${esc(b.name || "Sans nom")}</b>
          <span class="mono">${a != null && !isNaN(a) ? tc(a) : "?"} → ${e != null && !isNaN(e) ? tc(e) : "?"} · ${b.shots.length ? `plans ${first} à ${n}` : "aucun plan"}${a != null && e != null && !isNaN(a) && !isNaN(e) ? ` · ${(e - a).toFixed(0)} s` : ""}</span>
          ${b.intention ? `<span class="dblock-int">${esc(b.intention)}</span>` : ""}
        </span>
        ${(() => { const okN = b.shots.filter((x) => x.cut_ok).length;
          return b.shots.length && okN === b.shots.length ? `<span class="pill done">${okN}/${b.shots.length} validés</span>`
            : `<span class="pill ${okN ? "work" : "wait"}">${okN}/${b.shots.length} validés</span>`; })()}
        ${todo ? `<span class="pill review">${todo} à compléter</span>` : ""}
      </div>
      <div class="dblock-body">
        <details class="fold dblock-set"><summary>Nom, intention et lumière du bloc</summary><div class="stack" style="gap:8px">
          <label class="field"><span>Nom</span><input type="text" value="${esc(b.name)}" data-bf="${bi}:name" placeholder="Nom du bloc (couplet 1…)"></label>
          <label class="field"><span>Intention</span><textarea rows="2" data-bf="${bi}:intention" placeholder="Ce que raconte ce bloc">${esc(b.intention)}</textarea></label>
          <label class="field"><span>Lumière et étalonnage (en anglais)</span><textarea rows="2" data-bf="${bi}:look" placeholder="Lumière commune à tous les plans du bloc" title="Les plans du bloc partagent cette lumière. Le premier visuel validé du bloc sert de référence aux autres.">${esc(b.look || "")}</textarea></label>
          <div class="row"><button class="btn small ghost danger" data-delblock="${bi}">Supprimer le bloc</button></div>
        </div></details>
        <div class="dshots">${shotsHtml}</div>
        <div class="row" style="margin-top:10px"><button class="btn small" data-addshot="${bi}">＋ Plan</button></div>
      </div>
    </section>`;
  }).join("");
  return `${head}${summary}${renderDaBox(clip, true)}${renderSourcesBox(clip, true)}${tools}${blocks}
    <div class="row" style="position:sticky;bottom:12px;z-index:5;background:#0a0911ee;padding:10px;border-radius:12px;border:1px solid var(--line)">
      <button class="btn" data-addblock>＋ Bloc</button><span class="spacer"></span>
      <span class="hint" id="dec-status">${state.editorDirty ? "Modifications non enregistrées" : `${n} plans`}</span>
      <button class="btn go" data-savedec>Enregistrer le découpage</button>
    </div>`;
}

const FRAMING_FR = { ECU: "très gros plan", CU: "gros plan", MCU: "plan rapproché", MS: "plan taille", MWS: "plan américain",
  WS: "plan large", EWS: "plan très large" };
const MOTION_FR = { static: "aucun", low: "faible", medium: "moyen", high: "fort" };

function decIndexOf(shotId) {
  for (let bi = 0; bi < (state.editor || []).length; bi++) {
    const si = state.editor[bi].shots.findIndex((x) => x.id === shotId);
    if (si >= 0) return [bi, si];
  }
  return null;
}
function focusDecShot(shotId, open) {
  const at = decIndexOf(shotId);
  if (!at) return;
  const [bi, si] = at;
  const b = state.editor[bi];
  if (!b._open) { b._open = true; document.getElementById("decblock-" + bi)?.classList.add("open"); saveDecOpen(state.clip); }
  if (open) { b.shots[si]._open = true; document.getElementById(`dshot-${bi}:${si}`)?.classList.add("open"); }
  document.getElementById(`dshot-${bi}:${si}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
}
let playingId = null;
function markPlaying(shotId) {
  if (shotId === playingId) return;
  document.querySelectorAll(".dshot.playing").forEach((n) => n.classList.remove("playing"));
  playingId = shotId;
  const at = shotId != null && decIndexOf(shotId);
  if (!at) return;
  const node = document.getElementById(`dshot-${at[0]}:${at[1]}`);
  if (node) {
    node.classList.add("playing");
    // pendant la lecture, la liste suit le plan joué si son bloc est ouvert
    const r = node.getBoundingClientRect();
    const top = (document.getElementById("console")?.getBoundingClientRect().bottom || 0) + 8;
    if (!song.paused && node.offsetParent && (r.top < top || r.bottom > innerHeight)) node.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function saveDecOpen(clip) {
  prefs("decopen:" + clip.slug, (state.editor || []).map((b, i) => (b._open ? i : null)).filter((x) => x !== null));
}

function renderDecoupageRead(clip) {
  const shotById = Object.fromEntries(clip.shots.map((s) => [s.id, s]));
  return clip.blocks.map((b) => {
    const shots = b.shot_ids.map((id) => shotById[id]).filter(Boolean);
    return `<div class="dec-block"><div class="row" style="margin-bottom:8px"><h2>${esc(b.name)}</h2>
        <span class="hint">${esc(b.intention || "")}</span></div>
      ${b.look ? `<p class="hint" style="margin-bottom:8px">Lumière du bloc : ${esc(b.look)}</p>` : ""}
      ${shots.map((s) => `<div class="dec-shot" style="grid-template-columns:34px 170px 1fr auto">
        <span class="n">${s.num}</span><span class="mono" style="padding-top:2px">${tc(s.t_start)} → ${tc(s.t_end)} · ${durText({ t_start: s.t_start, t_end: s.t_end })}</span>
        <span><a href="${shotHref(s.id)}">${mentionHtml(s.description)}</a><br><span class="hint">${esc([s.framing, s.motion, s.camera].filter(Boolean).join(" · "))}</span>
          <br>${fitBadge(s.fit)}</span>
        <span>${s.singing ? "♪" : ""}</span></div>`).join("")}</div>`;
  }).join("") + `<p class="hint">Le découpage est validé : pour changer un plan, ouvre-le et demande une modif.</p>`;
}

function collectEditor() {
  const blocks = state.editor.map((b, bi) => ({
    name: b.name.trim(), intention: b.intention.trim() || null, look: (b.look || "").trim() || null,
    shots: b.shots.map((s, si) => {
      const a = parseTc(s.t_start); const z = parseTc(s.t_end);
      if (a == null || isNaN(a)) throw new Error(`Bloc « ${b.name || bi + 1} », plan ${si + 1} : début illisible`);
      if (z == null || isNaN(z)) throw new Error(`Bloc « ${b.name || bi + 1} », plan ${si + 1} : fin illisible`);
      const out = { t_start: a, t_end: z, description: s.description.trim(), singing: !!s.singing,
        detail: (s.detail || "").trim() };
      ["id", "framing", "motion", "camera", "notes", "model_key", "split_from"].forEach((k) => { if (s[k]) out[k] = s[k]; });
      out.characters = s.characters || [];
      return out;
    }),
  }));
  return blocks;
}

/* ----- onglet Dossier ----- */

function fileRow(f, removable = true) {
  const e = ext(f.path);
  return `<div class="file"><span class="ico">${esc(FILE_ICON[e] || e.toUpperCase().slice(0, 3))}</span>
    <span class="nm">${esc(f.label)}</span>
    <a href="${media(f.path)}" target="_blank" rel="noopener">ouvrir</a>
    ${removable ? `<button class="iconbtn" data-rmfile="${f.id}" title="Retirer">✕</button>` : ""}</div>`;
}

function renderDossier(clip) {
  const files = clip.files || [];
  const of = (k) => files.filter((f) => f.kind === k);
  const lyricsTyped = of("lyrics").find((f) => f.path.endsWith("script/paroles.md"));
  const lyricsFiles = of("lyrics").filter((f) => f !== lyricsTyped);
  const spent = clip.cost_usd || 0;
  let cta = "";
  if (clip.stage === "script") {
    const hasDec = clip.shots.length > 0;
    const hasDocs = of("dossier").length || of("lyrics").length;
    const ready = clip.song_path && (hasDec || hasDocs);
    cta = clip.brief_ready
      ? `<div class="agentbar">${led("work")}Dossier envoyé au scénariste. Il prépare le découpage ; tu seras prévenu.
          Si tu ajoutes un fichier ou modifies ton découpage, il le reprendra.</div>`
      : `<div class="actionbox" style="margin-bottom:16px"><h3>Prêt pour le découpage ?</h3>
        <div class="checklist">
          <div>${led(clip.song_path ? "done" : "wait")}Morceau ${clip.song_path ? "déposé" : "manquant"}</div>
          <div>${led(hasDec ? "done" : "wait")}Découpage saisi ${hasDec ? `(${clip.shots.length} plans)` : "(facultatif si ton dossier le contient)"}</div>
          <div>${led(of("dossier").length ? "done" : "wait")}Dossier de réalisation ${of("dossier").length ? `(${of("dossier").length} fichier${of("dossier").length > 1 ? "s" : ""})` : "(facultatif)"}</div>
          <div>${led(of("lyrics").length ? "done" : "wait")}Paroles ${of("lyrics").length ? "déposées" : "(recommandées pour le timing et les plans chantés)"}</div>
        </div>
        <p class="hint">Le scénariste reprend tes timecodes tels quels, puis complète chaque plan
          (cadrage, mouvement, caméra, plan chanté). Il ne crée ni ne déplace aucun plan.</p>
        <div class="row"><button class="btn go" data-submitbrief ${ready ? "" : "disabled"}>Envoyer au scénariste</button></div>
      </div>`;
  }
  const formats = [["16:9", "Horizontal", "YouTube, écran", 48, 27], ["9:16", "Vertical", "Reels, TikTok, Shorts", 22, 39], ["1:1", "Carré", "Posts", 34, 34]];
  const formatLocked = clip.stage !== "script" && clip.stage !== "decoupage_review";
  return `${cta}
    ${renderDaBox(clip, false)}
    ${renderSourcesBox(clip, false)}
    <div id="scenario-box" class="panel stack" style="margin-bottom:16px"><p class="loading">Chargement…</p></div>
    <div class="two-col">
      <div class="panel stack">
        <div class="panel-head"><h2>Concept</h2></div>
        <label class="field">Titre<input type="text" id="b-title" value="${esc(clip.title)}"></label>
        <label class="field">Pitch <span class="hint">L'idée du clip en une ou deux phrases.</span>
          <textarea id="b-pitch" rows="2">${esc(clip.pitch || "")}</textarea></label>
        <label class="field">Concept <span class="hint">Histoire, univers, direction artistique, ce qui compte pour toi.</span>
          <textarea id="b-concept" rows="9">${esc(clip.concept || "")}</textarea></label>
        <div class="row"><button class="btn go" data-savebrief>Enregistrer</button></div>
      </div>
      <div class="stack">
        <div class="panel stack">
          <div class="panel-head"><h2>Morceau</h2></div>
          ${of("song").map((f) => fileRow(f, false)).join("") || `<p class="hint">Pas encore de morceau.</p>`}
          ${dropZone("song", clip.song_path ? "Remplacer le morceau" : "Déposer le morceau", "mp3 ou wav exporté de Suno", "audio/*", false)}
          <h3 style="margin-top:6px">Voix isolée</h3>
          <p class="hint">Le stem « vocals » de Suno. Il sert au lip-sync des plans chantés : sans lui, le lip-sync se cale sur le morceau complet, moins précis.</p>
          ${of("vocals").map((f) => fileRow(f)).join("")}
          ${dropZone("vocals", of("vocals").length ? "Remplacer la voix isolée" : "Déposer la voix isolée", "mp3 ou wav", "audio/*", false)}
        </div>
        <div class="panel stack">
          <div class="panel-head"><h2>Dossier de réalisation</h2></div>
          <p class="hint">Direction artistique, storytelling, plans, références, infos clés. PDF, Word, texte ou images.
            Les agents lisent tout avant de travailler.</p>
          <div class="files">${of("dossier").map((f) => fileRow(f)).join("") + of("reference").map((f) => fileRow(f)).join("")}</div>
          ${dropZone("dossier", "Ajouter des fichiers", "Glisse-les ici ou touche pour choisir", "", true)}
        </div>
      </div>
    </div>
    <div class="panel stack" style="margin-top:16px">
      <div class="panel-head"><h2>Paroles</h2><span class="hint">Indispensables pour bien caler les plans chantés.</span></div>
      <div class="two-col">
        <div class="stack"><textarea id="lyrics" rows="12" placeholder="[Couplet 1]&#10;…&#10;&#10;[Refrain]&#10;…">${esc(state.lyricsText || "")}</textarea>
          <div class="row"><button class="btn" data-savelyrics>Enregistrer les paroles</button></div></div>
        <div class="stack"><div class="files">${lyricsFiles.map((f) => fileRow(f)).join("")}</div>
          ${dropZone("lyrics", "Ou déposer un fichier de paroles", "txt, md, pdf, docx, lrc (paroles horodatées)", "", true)}</div>
      </div>
    </div>
    <div class="two-col" style="margin-top:16px">
      <div class="panel stack">
        <div class="panel-head"><h2>Format de l'image</h2></div>
        <p class="hint">La forme de la vidéo finale. Tous les visuels et vidéos sont générés dans ce format.${formatLocked ? " Il ne se change plus une fois la production lancée." : ""}</p>
        <div class="formats">${formats.map(([v, n, u, w, h]) => `<button class="format ${clip.aspect_ratio === v ? "on" : ""}" data-format="${v}" ${formatLocked ? "disabled" : ""}>
          <span class="shape" style="width:${w}px;height:${h}px"></span><b>${n} ${v}</b><span>${u}</span></button>`).join("")}</div>
      </div>
      <div class="panel stack">
        <div class="panel-head"><h2>Budget de génération</h2></div>
        <p class="hint">Le plafond de dépense chez les fournisseurs (fal.ai) pour ce clip. Avant chaque génération,
          la machine vérifie qu'elle ne le dépasse pas ; sinon elle s'arrête et te prévient. Tu peux le relever à tout moment.</p>
        <div class="progress"><i style="width:${clip.budget_usd ? Math.min(100, (100 * spent) / clip.budget_usd) : 0}%"></i></div>
        <p class="mono">${money(spent)} dépensés${clip.budget_usd ? ` sur ${clip.budget_usd.toFixed(0)} $` : ""}</p>
        <div class="row"><input type="number" id="b-budget" min="1" step="1" value="${clip.budget_usd || 80}" style="max-width:140px"> <span>$</span>
          <button class="btn" data-savebudget>Mettre à jour</button></div>
      </div>
    </div>
    <div class="panel" style="margin-top:16px"><div class="panel-head"><h2>Casting</h2></div>
      ${clip.casting.length ? clip.casting.map((c) => `<div class="row"><a href="#/personnages/${encodeURIComponent(c.character_slug)}"><b>${esc(c.name)}</b></a>
        <span class="hint">version ${c.version}${c.look_slug ? " · look " + esc(c.look_slug) : ""}</span></div>`).join("") : `<p class="hint">Aucun personnage.</p>`}
    </div>`;
}

/* ----- direction artistique : écrite par Michael, fait foi sur tout ----- */
function renderDaBox(clip, folded) {
  const da = (clip.da || "").trim();
  const body = `<p class="hint">Quelques lignes, à toi : le ton, le niveau de réalisme, qui sont les personnages (âge, métier, style),
      leurs tenues, les lieux, la lumière, et ce que tu ne veux jamais voir. Elle passe avant le dossier, les sources et tout ce
      qu'une IA a proposé. Chaque agent la reçoit à chaque tâche.</p>
    <textarea id="da-text" rows="7" placeholder="Ex. : ambiance vraie vie, pas de look rock. JJ, jeune directrice dans un cabinet de conseil : tailleur sobre, escarpins ou mocassins, jamais de Doc Martens. Bureaux réalistes de cabinet, pas de plateau stylisé hors des scènes dansées.">${esc(da)}</textarea>
    <div class="row" style="gap:8px"><button class="btn" data-saveda>Enregistrer</button>
      <button class="btn go" data-applyda>Enregistrer et faire tout réaligner</button>
      <span class="hint">${clip.stage === "script" || clip.stage === "decoupage_review" ? "Le scénariste relit chaque plan et la mémoire, le décorateur ses fiches." : "Les prochains visuels et vidéos la suivent."}</span></div>`;
  if (folded) {
    return `<details class="panel fold dabox" ${da ? "" : "open"}><summary><b>Direction artistique</b> <span class="pill done">fait foi</span>
        <span class="hint">${da ? esc(da.split("\n")[0].slice(0, 90)) + (da.length > 90 ? "…" : "") : "pas encore écrite"}</span></summary>
      <div class="stack">${body}</div></details>`;
  }
  return `<div class="panel stack dabox" style="margin-bottom:16px"><div class="panel-head"><h2>Direction artistique</h2><span class="pill done">fait foi</span></div>${body}</div>`;
}

/* ----- sources du scénariste et mémoire de réalisation ----- */

function sizeText(n) {
  if (!n) return "";
  const k = Math.round(n / 1000);
  return k >= 1 ? `≈ ${k.toLocaleString("fr-FR")} 000 caractères` : `${n} caractères`;
}

function renderSourcesBox(clip, inDecoupage) {
  const sources = (clip.files || []).filter((f) => f.kind === "source");
  const unread = new Set(clip.sources_unread || []);
  const nNew = sources.filter((f) => unread.has(f.id)).length;
  const working = clip.memoire_status === "requested" || (clip.needs_agent || []).some((r) => r.includes("sources à relire"));
  const rows = sources.map((f) => `<div class="file"><span class="ico">TXT</span>
      <span class="nm">${esc(f.label)}<br><span class="hint">${sizeText(f.size)}</span></span>
      ${unread.has(f.id) ? pill("pas encore lue", "review") : pill("lue", "done")}
      <a href="${media(f.path)}" target="_blank" rel="noopener">ouvrir</a>
      <button class="iconbtn" data-rmfile="${f.id}" title="Retirer">✕</button></div>`).join("");
  const memo = clip.memoire || "";
  const body = `
    <p class="hint">Colle ou dépose tout ce qui a nourri le clip : conversations entières avec d'autres IA,
      transcriptions audio, notes. Aucune limite de taille. Le scénariste les lit en entier et en tire la
      mémoire de réalisation : tes décisions, ce que tu as écarté et pourquoi. Tous les agents la lisent, pour ne
      jamais te reproposer une idée refusée.</p>
    <div class="files">${rows || `<p class="hint">Aucune source pour l'instant.</p>`}</div>
    ${working ? `<div class="agentbar">${led("work")}Le scénariste relit tes sources et met à jour la mémoire${clip.stage === "script" || clip.stage === "decoupage_review" ? " et les plans" : ""}.</div>`
      : nNew ? `<div class="row"><button class="btn go" data-askmemoire>Faire lire ${nNew > 1 ? `ces ${nNew} sources` : "cette source"} au scénariste</button>
          <span class="hint">${clip.stage === "script" || clip.stage === "decoupage_review" ? "Il met à jour la mémoire, puis reprend les plans concernés." : "Il met à jour la mémoire ; les plans déjà validés ne bougent pas."}</span></div>` : ""}
    <details class="fold" ${sources.length ? "" : "open"}><summary>Coller un texte</summary><div class="stack" style="gap:8px">
      <input type="text" id="src-label" placeholder="Titre (ex. : conversation avec ChatGPT du 29 octobre)">
      <textarea id="src-text" rows="8" placeholder="Colle ici la conversation ou la transcription entière, telle quelle"></textarea>
      <div class="row"><button class="btn" data-addsource>Ajouter cette source</button></div></div></details>
    ${dropZone("source", "Ou déposer des fichiers", "txt, md, pdf, docx, srt : conversations exportées, transcriptions", "", true)}
    <h3 style="margin-top:6px">Mémoire de réalisation</h3>
    ${memo ? `<details class="fold"><summary>Lire et corriger la mémoire (${memo.split("\n").filter((l) => l.trim()).length} lignes)</summary><div class="stack" style="gap:8px">
        <textarea id="memoire" rows="18">${esc(memo)}</textarea>
        <div class="row"><button class="btn" data-savememoire>Enregistrer ma correction</button></div></div></details>`
      : `<p class="hint">Pas encore écrite : elle apparaît ici quand le scénariste a lu tes sources.</p>`}`;
  if (inDecoupage) {
    return `<details class="panel fold sources-box" id="sources" ${nNew || working ? "open" : ""}>
      <summary><b>Sources et mémoire du scénariste</b> <span class="hint">${sources.length} source${sources.length > 1 ? "s" : ""}${nNew ? ` · ${nNew} pas encore lue${nNew > 1 ? "s" : ""}` : ""}${memo ? " · mémoire écrite" : ""}</span></summary>
      <div class="stack">${body}</div></details>`;
  }
  return `<div class="panel stack sources-box" id="sources" style="margin-bottom:16px">
      <div class="panel-head"><h2>Sources du scénariste</h2></div>${body}</div>`;
}

async function loadLyrics(clip) {
  const typed = (clip.files || []).find((f) => f.kind === "lyrics" && f.path.endsWith("script/paroles.md"));
  state.lyricsText = "";
  if (!typed) return;
  try { state.lyricsText = await (await fetch(media(typed.path))).text(); } catch (e) { /* pas grave */ }
  const ta = document.getElementById("lyrics");
  if (ta && !ta.value) ta.value = state.lyricsText;
}

/* ----- onglet Journal ----- */

function renderJournal(clip) {
  return `<div class="panel"><div class="panel-head"><h2>Journal</h2><span class="hint">Les 30 derniers événements</span></div>
    <div class="journal">${clip.events.map((e) => `<div><span class="t">${esc(e.created_at.replace("T", " ").slice(5, 16))}</span><span>${esc(e.message)}</span></div>`).join("") || `<p class="hint">Rien pour l'instant.</p>`}</div></div>`;
}

/* ----- interactions de la page clip ----- */

function bindClip() {
  const clip = state.clip;
  drawWave();
  bindCompare($view);
  if (state.tab === "dossier" || state.tab === "decoupage") {
    if (state.tab === "dossier") loadLyrics(clip);
    bindDrops($view, async (kind, files) => {
      const fd = new FormData();
      fd.set("kind", kind);
      [...files].forEach((f) => fd.append("files", f));
      toast("Envoi en cours…");
      try {
        await upload(`/api/clips/${encodeURIComponent(clip.slug)}/files`, fd, (p) => toast(`Envoi : ${Math.round(p * 100)} %`));
        toast("Fichier ajouté");
        if (kind === "song") delete state.peaks[clip.slug];
        await showClip(clip.slug, state.tab);
      } catch (e) { toast(e.message, "err"); }
    });
  }
  bindTimeline();
  $view.oninput = (e) => {
    const t = e.target;
    if (t.dataset.sf) {
      const [bi, si, f] = t.dataset.sf.split(":");
      state.editor[+bi].shots[+si][f] = t.type === "checkbox" ? t.checked : t.value;
      const sh = state.editor[+bi].shots[+si];
      if (f === "t_start" || f === "t_end" || f === "model_key") {
        const el = $view.querySelector(`[data-dur="${bi}:${si}"]`);
        if (el) el.textContent = durText(sh);
        const fit = fitFor(clip, sh.model_key, parseTc(sh.t_end) - parseTc(sh.t_start));
        const fe = $view.querySelector(`[data-fit="${bi}:${si}"]`);
        if (fe) fe.innerHTML = fit && fit.level !== "ok" ? `<span class="fit ${fit.level}">${esc(fit.short)}</span>` : "";
        const ff = $view.querySelector(`[data-fitfull="${bi}:${si}"]`);
        if (ff) ff.innerHTML = fitHtml(fit, `${bi}:${si}`);
        const tcEl = $view.querySelector(`#dshot-${bi}\\:${si} .dshot-tc`);
        if (tcEl) tcEl.textContent = `${sh.t_start || "?"} → ${sh.t_end || "?"}`;
      }
      if (f === "description") {
        const de = $view.querySelector(`[data-desc="${bi}:${si}"]`);
        if (de) de.innerHTML = mentionHtml(sh.description);
      }
      markDirty();
    } else if (t.dataset.bf) {
      const [bi, f] = t.dataset.bf.split(":");
      state.editor[+bi][f] = t.value;
      markDirty();
    }
  };
  $view.onclick = async (ev) => {
    const t = ev.target.closest("button, [data-openshot], [data-goblock], [data-toggleblock], [data-zoom], [data-unfold], [data-toggledec], [data-toggleshot]");
    if (!t) return;
    const d = t.dataset;
    const reload = (tab = state.tab) => showClip(clip.slug, tab, false);
    try {
      if (d.zoom) return lightbox(d.zoom);
      if (d.unfold !== undefined) { t.classList.toggle("folded"); return; }
      if (d.play !== undefined) { if (song.paused) song.play().catch(() => {}); else song.pause(); return; }
      if (d.openshot && state.tab === "decoupage" && state.editor) {
        const shot = clip.shots.find((s) => s.id === +d.openshot);
        if (shot) { song.currentTime = shot.t_start; updateHead(); }
        focusDecShot(+d.openshot, true);
        return;
      }
      if (d.decplay) {
        const [bi, si] = d.decplay.split(":").map(Number);
        const sh = state.editor[bi].shots[si];
        const a = parseTc(sh.t_start), b = parseTc(sh.t_end);
        if (a == null || b == null || isNaN(a) || isNaN(b)) { toast("Timecodes illisibles", "err"); return; }
        song.currentTime = a; song.play().catch(() => {}); stopAt = { end: b };
        return;
      }
      if (d.openshot) {
        const shot = clip.shots.find((s) => s.id === +d.openshot);
        if (shot && t.classList.contains("tl-shot")) { song.currentTime = shot.t_start; updateHead(); }
        location.hash = shotHref(d.openshot);
        return;
      }
      if (d.tlmini !== undefined) {
        const mini = !prefs("tlmini"); prefs("tlmini", mini);
        document.getElementById("console").classList.toggle("mini", mini);
        t.textContent = mini ? "Agrandir" : "Réduire";
        return drawWave();
      }
      if (d.tlzoom) {
        const z = tlZoom();
        if (d.tlzoom === "fit") return setTlZoom(1);
        const next = d.tlzoom === "in" ? TL_ZOOMS.find((x) => x > z) || z : [...TL_ZOOMS].reverse().find((x) => x < z) || 1;
        return setTlZoom(next);
      }
      if (d.goblock !== undefined) {
        // un bloc touché dans la frise : on zoome dessus, et on ouvre ce bloc dans la liste
        if (t.classList.contains("tl-block")) focusRange(+d.a, +d.z);
        if (state.tab === "decoupage") {
          const bi = clip.blocks.findIndex((b) => String(b.id) === d.goblock);
          if (bi >= 0 && state.editor && state.editor[bi]) {
            state.editor[bi]._open = true;
            const node = document.getElementById("decblock-" + bi);
            if (node) { node.classList.add("open"); saveDecOpen(clip); node.scrollIntoView({ behavior: "smooth", block: "start" }); }
          }
          return;
        }
        if (state.tab !== "plans") return;
        const open = openBlocks(clip); open.add(d.goblock); prefs("open:" + clip.slug, [...open]);
        const node = document.getElementById("block-" + d.goblock);
        if (node) { node.classList.add("open"); node.scrollIntoView({ behavior: "smooth", block: "start" }); }
        return;
      }
      if (d.toggleblock) {
        const filtering = state.filter !== "all" || state.stepFilter;
        const node = document.getElementById("block-" + d.toggleblock);
        const willOpen = !node.classList.contains("open");
        node.classList.toggle("open", willOpen);
        if (filtering) state.tempOpen[d.toggleblock] = willOpen;
        else {
          const open = openBlocks(clip);
          if (willOpen) open.add(d.toggleblock); else open.delete(d.toggleblock);
          prefs("open:" + clip.slug, [...open]);
        }
        return;
      }
      if (d.allblocks) {
        const ids = clip.blocks.map((b) => String(b.id));
        prefs("open:" + clip.slug, d.allblocks === "open" ? ids : []);
        ids.forEach((id) => { state.tempOpen[id] = d.allblocks === "open"; });
        return renderClip();
      }
      if (d.filter) { state.filter = d.filter; state.tempOpen = {}; return renderClip(); }
      if (d.stepfilter !== undefined) {
        state.stepFilter = d.stepfilter && state.stepFilter !== d.stepfilter ? d.stepfilter : null;
        state.tempOpen = {};
        return renderClip();
      }
      if (d.approveblock) {
        const [gate, block] = d.approveblock.split(":");
        if (needsConfirm(t, d.approveblock)) return;
        const r = await api(`/api/clips/${encodeURIComponent(clip.slug)}/approve-all/${gate}${block ? `?block=${block}` : ""}`, { method: "POST" });
        toast(`${r.approved} plan${r.approved > 1 ? "s" : ""} validé${r.approved > 1 ? "s" : ""}`);
        return reload();
      }
      if (d.assemble !== undefined) {
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/assemble`, { method: "POST" });
        toast("Montage lancé : il apparaît dans une à deux minutes");
        return;
      }
      // découpage
      if (d.toggledec !== undefined) {
        const b = state.editor[+d.toggledec];
        b._open = !b._open;
        document.getElementById("decblock-" + d.toggledec)?.classList.toggle("open", b._open);
        saveDecOpen(clip);
        return;
      }
      if (d.toggleshot) {
        if (ev.target.closest("a, .mention")) return;
        const [bi, si] = d.toggleshot.split(":").map(Number);
        const sh = state.editor[bi].shots[si];
        sh._open = !sh._open;
        document.getElementById(`dshot-${bi}:${si}`)?.classList.toggle("open", sh._open);
        if (sh._open) fitAll(document.getElementById(`dshot-${bi}:${si}`));
        return;
      }
      if (d.cutok) {
        if (state.editorDirty) { toast("Enregistre d'abord tes modifications", "err"); return; }
        const [sid, on] = d.cutok.split(":");
        await api(`/api/shots/${sid}/cut-ok`, { json: { ok: on === "1" } });
        toast(on === "1" ? "Plan validé" : "Validation retirée"); return reload("decoupage");
      }
      if (d.cutask) {
        const fb = document.getElementById("cutask-" + d.cutask); fb.hidden = !fb.hidden;
        if (!fb.hidden) fb.querySelector("textarea").focus(); return;
      }
      if (d.cutsend) {
        const [bi, si, sid] = d.cutsend.split(":");
        const text = document.querySelector(`#cutask-${bi}\\:${si} textarea`).value.trim();
        if (!text) { toast("Écris ce que tu veux changer", "err"); return; }
        if (state.editorDirty) { toast("Enregistre d'abord tes modifications", "err"); return; }
        await api(`/api/shots/${sid}/cut-change`, { json: { comment: text } });
        toast("Envoyé au scénariste : il reprend ce plan"); return reload("decoupage");
      }
      if (d.usemodel) {
        const [bi, si, mk] = d.usemodel.split(":");
        state.editor[+bi].shots[+si].model_key = mk;
        state.editor[+bi].shots[+si]._open = true;
        markDirty(); toast("Modèle changé : pense à enregistrer le découpage"); return renderClip();
      }
      if (d.decall) {
        state.editor.forEach((b) => { b._open = d.decall === "open"; });
        saveDecOpen(clip);
        return renderClip();
      }
      if (d.addshot) {
        const b = state.editor[+d.addshot];
        const last = b.shots[b.shots.length - 1];
        b.shots.push({ t_start: last ? last.t_end : "", t_end: "", description: "", singing: false, characters: defaultCast(clip), _open: true });
        markDirty(); return renderClip();
      }
      if (d.addblock !== undefined) {
        const lastB = state.editor[state.editor.length - 1];
        const lastS = lastB && lastB.shots[lastB.shots.length - 1];
        state.editor.push({ name: "", intention: "", _open: true, shots: [{ t_start: lastS ? lastS.t_end : "0:00.0", t_end: "", description: "", singing: false, characters: defaultCast(clip), _open: true }] });
        saveDecOpen(clip);
        markDirty(); return renderClip();
      }
      if (d.mergeshot) {
        const [bi, si] = d.mergeshot.split(":").map(Number);
        const shots = state.editor[bi].shots, a = shots[si], b = shots[si + 1];
        a.t_end = b.t_end;
        a.description = `${a.description.trim()} Puis : ${b.description.trim()}`;
        if (b.detail) a.detail = [a.detail, b.detail].filter(Boolean).join(" Then: ");
        a.singing = a.singing || b.singing;
        a.characters = [...new Set([...(a.characters || []), ...(b.characters || [])])];
        shots.splice(si + 1, 1);
        markDirty(); return renderClip();
      }
      if (d.splitshot) {
        const [bi, si] = d.splitshot.split(":").map(Number);
        const shots = state.editor[bi].shots, a = shots[si];
        const t0 = parseTc(a.t_start), t1 = parseTc(a.t_end);
        if (t0 == null || t1 == null || isNaN(t0) || isNaN(t1) || t1 - t0 < 1) { toast("Plan trop court pour être coupé", "err"); return; }
        const mid = tc(t0 + (t1 - t0) / 2);
        shots.splice(si + 1, 0, { ...a, id: null, split_from: a.id || null, t_start: mid, description: "", detail: a.detail, detail_edited: false, _open: true });
        a.t_end = mid;
        markDirty(); return renderClip();
      }
      if (d.delshot) {
        const [bi, si] = d.delshot.split(":").map(Number);
        state.editor[bi].shots.splice(si, 1);
        markDirty(); return renderClip();
      }
      if (d.delblock) {
        if (needsConfirm(t, "delblock" + d.delblock)) return;
        state.editor.splice(+d.delblock, 1);
        markDirty(); return renderClip();
      }
      if (d.complete !== undefined) {
        if (state.editorDirty) { toast("Enregistre d'abord tes modifications du découpage", "err"); return; }
        t.disabled = true;
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/complete`, { method: "POST" });
        toast("Le scénariste complète les plans");
        return reload("decoupage");
      }
      if (d.savedec !== undefined) {
        const blocks = collectEditor();
        t.disabled = true;
        const r = await api(`/api/clips/${encodeURIComponent(clip.slug)}/decoupage-edit`, { json: { blocks } });
        state.editorDirty = false;
        toast(`Découpage enregistré : ${r.shots} plans`);
        return reload("decoupage");
      }
      if (d.cut === "open") { const fb = document.getElementById("fb-cut"); fb.hidden = false; fb.querySelector("textarea").focus(); return; }
      if (d.cut === "approve" || d.cut === "change") {
        if (state.editorDirty) { toast("Enregistre d'abord tes modifications du découpage", "err"); return; }
        const comment = d.cut === "change" ? document.querySelector("#fb-cut textarea").value.trim() : "";
        if (d.cut === "change" && !comment) { toast("Explique les changements voulus", "err"); return; }
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/decoupage`, { json: { decision: d.cut, comment } });
        toast(d.cut === "approve" ? "Découpage validé : le storyboard démarre" : "Retour envoyé au scénariste");
        return reload(d.cut === "approve" ? "plans" : "decoupage");
      }
      // direction artistique
      if (d.saveda !== undefined || d.applyda !== undefined) {
        if (d.applyda !== undefined && state.editorDirty) { toast("Enregistre d'abord tes modifications du découpage", "err"); return; }
        t.disabled = true;
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/da`, { json: { text: document.getElementById("da-text").value } });
        if (d.applyda !== undefined) {
          const r = await api(`/api/clips/${encodeURIComponent(clip.slug)}/da/apply`, { method: "POST" });
          toast(`Direction artistique enregistrée : ${r.where}`);
        } else toast("Direction artistique enregistrée");
        return reload();
      }
      // sources et mémoire
      if (d.addsource !== undefined) {
        const text = document.getElementById("src-text").value;
        if (!text.trim()) { toast("Colle d'abord le texte", "err"); return; }
        t.disabled = true;
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/sources`, { json: { label: document.getElementById("src-label").value, text } });
        toast("Source ajoutée");
        return reload();
      }
      if (d.askmemoire !== undefined) {
        t.disabled = true;
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/memoire/request`, { method: "POST" });
        toast("Le scénariste va lire tes sources");
        return reload();
      }
      if (d.savememoire !== undefined) {
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/memoire`, { json: { text: document.getElementById("memoire").value } });
        toast("Mémoire enregistrée");
        return reload();
      }
      // dossier
      if (d.savebrief !== undefined) {
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/brief`, { json: {
          title: document.getElementById("b-title").value, pitch: document.getElementById("b-pitch").value,
          concept: document.getElementById("b-concept").value } });
        toast("Concept enregistré");
        return reload();
      }
      if (d.savelyrics !== undefined) {
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/lyrics`, { json: { text: document.getElementById("lyrics").value } });
        toast("Paroles enregistrées");
        return reload();
      }
      if (d.savebudget !== undefined) {
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/brief`, { json: { budget_usd: parseFloat(document.getElementById("b-budget").value) } });
        toast("Budget mis à jour");
        return reload();
      }
      if (d.format) {
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/brief`, { json: { aspect: d.format } });
        toast(`Format ${d.format}`);
        return reload();
      }
      if (d.rmfile) {
        if (needsConfirm(t, "rm" + d.rmfile)) return;
        await api(`/api/files/${d.rmfile}`, { method: "DELETE" });
        toast("Fichier retiré (gardé dans le dossier « retires »)");
        return reload();
      }
      if (d.submitbrief !== undefined) {
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/submit-brief`, { method: "POST" });
        toast("Envoyé au scénariste");
        return reload();
      }
    } catch (e) {
      t.disabled = false;
      toast(e.message, "err");
    }
  };
}

function markDirty() {
  state.editorDirty = true;
  const s = document.getElementById("dec-status");
  if (s) s.textContent = "Modifications non enregistrées";
}

/* ---------- Nouveau clip ---------- */

async function showNewClip() {
  stopTimer();
  const d = await api("/api/overview");
  const castable = d.characters.filter((c) => c.canon_version);
  const formats = [["16:9", "Horizontal", "YouTube, écran", 48, 27], ["9:16", "Vertical", "Reels, TikTok, Shorts", 22, 39], ["1:1", "Carré", "Posts", 34, 34]];
  $view.innerHTML = `
    <div class="pagehead"><h1>Nouveau clip</h1></div>
    <form class="stack" id="newclip" style="gap:16px">
      <div class="panel stack">
        <div class="row"><span class="step-num">1</span><h2>Le morceau</h2></div>
        <label class="field">Titre du clip<input type="text" name="title" required placeholder="Titre du morceau"></label>
        <div class="formgrid">
          <div class="stack">${dropZone("song", "Morceau", "mp3 ou wav exporté de Suno (obligatoire)", "audio/*", false)}</div>
          <div class="stack">${dropZone("vocals", "Voix isolée", "Le stem « vocals » de Suno, pour un lip-sync précis (facultatif)", "audio/*", false)}</div>
        </div>
      </div>
      <div class="panel stack">
        <div class="row"><span class="step-num">2</span><h2>Le concept</h2></div>
        <label class="field">Pitch <span class="hint">L'idée du clip en une ou deux phrases.</span><textarea name="pitch" rows="2"></textarea></label>
        <label class="field">Concept <span class="hint">Histoire, univers, direction artistique. Tu peux aussi tout mettre dans le dossier ci-dessous.</span>
          <textarea name="concept" rows="5"></textarea></label>
      </div>
      <div class="panel stack">
        <div class="row"><span class="step-num">3</span><h2>Dossier de réalisation</h2></div>
        <p class="hint">Direction artistique, storytelling, plans, références, infos clés. PDF, Word, texte ou images, autant de fichiers que tu veux.</p>
        ${dropZone("dossier", "Déposer les fichiers du dossier", "Glisse-les ici ou touche pour choisir", "", true)}
      </div>
      <div class="panel stack">
        <div class="row"><span class="step-num">4</span><h2>Paroles</h2></div>
        <p class="hint">Elles servent à caler les plans chantés et à comprendre ce que chaque plan doit montrer.</p>
        <div class="formgrid">
          <textarea name="lyrics_text" rows="8" placeholder="Colle les paroles ici&#10;&#10;[Couplet 1]&#10;…"></textarea>
          <div>${dropZone("lyrics", "Ou un fichier de paroles", "txt, md, pdf, docx, lrc", "", true)}</div>
        </div>
      </div>
      <div class="panel stack">
        <div class="row"><span class="step-num">5</span><h2>Casting et réglages</h2></div>
        <div class="row">${castable.map((c, i) => `<label class="chip ${i === 0 ? "on" : ""}" style="display:inline-flex;gap:8px;align-items:center">
          <input type="checkbox" name="characters" value="${esc(c.slug)}" ${i === 0 ? "checked" : ""}> ${esc(c.name)} <span class="hint">v${c.canon_version}</span></label>`).join("") || `<span class="hint">Aucun personnage validé.</span>`}</div>
        <div class="formgrid">
          <div class="stack"><b>Format de l'image</b><span class="hint">La forme de la vidéo finale : tout est généré dans ce format.</span>
            <div class="formats">${formats.map(([v, n, u, w, h], i) => `<button type="button" class="format ${i === 0 ? "on" : ""}" data-format="${v}">
              <span class="shape" style="width:${w}px;height:${h}px"></span><b>${n} ${v}</b><span>${u}</span></button>`).join("")}</div>
            <input type="hidden" name="aspect" value="16:9"></div>
          <div class="stack"><b>Budget de génération</b>
            <span class="hint">Plafond de dépense chez les fournisseurs (fal.ai) pour ce clip. La machine s'arrête et te prévient avant de le dépasser. Modifiable à tout moment.</span>
            <div class="row"><input type="number" name="budget" min="1" step="1" value="80" style="max-width:140px"> <span>$</span></div></div>
        </div>
      </div>
      <div class="panel stack">
        <div class="progress" id="up-bar" hidden><i></i></div>
        <div class="row"><button class="btn go" type="submit">Créer le clip</button>
          <span class="hint" id="up-msg">Ensuite, tu saisis ton découpage (blocs et plans) ou tu laisses le scénariste le tirer de ton dossier.</span></div>
      </div>
    </form>`;
  const form = document.getElementById("newclip");
  bindDrops(form);
  form.addEventListener("click", (e) => {
    const f = e.target.closest("[data-format]");
    if (f) {
      form.querySelectorAll("[data-format]").forEach((x) => x.classList.toggle("on", x === f));
      form.aspect.value = f.dataset.format;
    }
    const chip = e.target.closest("label.chip");
    if (chip) setTimeout(() => chip.classList.toggle("on", chip.querySelector("input").checked));
  });
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(form);
    if (!fd.get("song")?.size) { toast("Ajoute le morceau", "err"); return; }
    const chars = fd.getAll("characters");
    fd.delete("characters");
    fd.set("characters", chars.join(","));
    if (!fd.get("vocals")?.size) fd.delete("vocals");
    ["dossier", "lyrics"].forEach((k) => {
      const list = fd.getAll(k).filter((f) => f.size);
      fd.delete(k);
      list.forEach((f) => fd.append(k, f));
    });
    const btn = form.querySelector("button[type=submit]");
    const bar = document.getElementById("up-bar");
    btn.disabled = true;
    bar.hidden = false;
    document.getElementById("up-msg").textContent = "Envoi des fichiers…";
    try {
      const r = await upload("/api/clips", fd, (p) => { bar.firstElementChild.style.width = `${Math.round(p * 100)}%`; });
      toast("Clip créé");
      location.hash = `#/clip/${encodeURIComponent(r.slug)}/decoupage`;
    } catch (e) {
      btn.disabled = false;
      document.getElementById("up-msg").textContent = "";
      toast(e.message, "err");
    }
  };
}

/* ---------- Personnages ---------- */

async function showCharacters() {
  const d = await api("/api/overview");
  $view.innerHTML = `<div class="pagehead"><h1>Personnages</h1>
      <span class="sub">Chaque personnage a des versions. Seule une version validée peut jouer dans un clip.</span></div>
    <div class="cast">${d.characters.map((c) => `<a class="castcard" href="#/personnages/${encodeURIComponent(c.slug)}">
      <div class="face" style="${c.canon_path ? `background-image:url('${media(c.canon_path)}')` : ""}">${c.canon_path ? "" : "pas encore de canon"}</div>
      <div class="cap"><b>${esc(c.name)}</b><span class="hint">${c.canon_version ? `canon v${c.canon_version}` : "aucune version validée"}</span>
        ${c.hd_to_review ? pill("canon HD à vérifier", "review") : ""}
        ${c.to_review ? pill(`${c.to_review} image${c.to_review > 1 ? "s" : ""} à trier`, "review") : ""}</div></a>`).join("")}
      <div class="newcard" style="min-height:300px;padding:18px">
        <span class="plus">＋</span><b>Nouveau personnage</b>
        <input type="text" id="newchar" placeholder="Nom du personnage" style="max-width:220px">
        <button class="btn small go" data-newchar>Créer</button>
      </div></div>`;
  $view.onclick = async (e) => {
    if (!e.target.closest("[data-newchar]")) return;
    const name = document.getElementById("newchar").value.trim();
    if (!name) { toast("Donne un nom", "err"); return; }
    try {
      const r = await api("/api/characters", { json: { name } });
      location.hash = `#/personnages/${encodeURIComponent(r.slug)}`;
    } catch (err) { toast(err.message, "err"); }
  };
  every(30000, () => { if (!isBusy()) showCharacters(); });
}

async function showCharacter(slug, keep = false) {
  const ch = await api(`/api/characters/${encodeURIComponent(slug)}`);
  const json = JSON.stringify(ch);
  if (keep && (json === state.charJson || isBusy())) return;
  state.charJson = json;
  if (!state.character || state.character.slug !== slug) state.charVersion = null;
  state.character = ch;
  const scroll = window.scrollY;
  const drafts = ch.versions.filter((v) => v.status === "draft");
  const vnum = state.charVersion || (drafts[0] || ch.versions.find((v) => v.version === ch.canon_version) || ch.versions[0] || {}).version;
  const v = ch.versions.find((x) => x.version === vnum);
  const vtabs = ch.versions.map((x) => `<button class="chip ${x.version === vnum ? "on" : ""}" data-version="${x.version}">
      v${x.version} · ${x.status === "draft" ? "brouillon" : x.status === "validated" ? "validée" : "archivée"}${x.version === ch.canon_version ? " · canon actuelle" : ""}</button>`).join("");
  $view.innerHTML = `<div class="cliphead"><div class="crumbs"><a href="#/personnages">Personnages</a> / ${esc(ch.name)}</div>
      <div class="row"><h1>${esc(ch.name)}</h1></div>
      <div class="meta"><span>${ch.clips.length ? "Joue dans : " + ch.clips.map((c) => `${esc(c.clip_slug)} (v${c.version})`).join(", ") : "Dans aucun clip"}</span>
        ${ch.looks.length ? `<span>Tenues : ${ch.looks.map((l) => esc(l.slug)).join(", ")}</span>` : ""}</div></div>
    <div class="toolbar">${vtabs}<span class="spacer"></span>
      ${drafts.length ? "" : `<button class="btn small" data-newversion>Faire évoluer : nouvelle version</button>`}</div>
    ${v ? renderVersion(ch, v) : `<p class="empty">Aucune version.</p>`}`;
  if (keep) window.scrollTo(0, scroll);
  bindCompare($view);
  bindDrops($view, async (kind, files) => {
    const fd = new FormData();
    try {
      if (kind.startsWith("look:")) {
        [...files].forEach((f) => fd.append("files", f));
        toast("Envoi des photos…");
        await upload(`/api/characters/${encodeURIComponent(slug)}/looks/${encodeURIComponent(kind.slice(5))}/images`, fd);
        toast("Photos ajoutées à la tenue");
      } else if (kind === "pack") {
        [...files].forEach((f) => fd.append("files", f));
        fd.set("kind", document.getElementById("pack-kind").value);
        toast("Envoi des images…");
        await upload(`/api/characters/${encodeURIComponent(slug)}/versions/${v.version}/pack-images`, fd);
        toast("Ajoutées au pack, telles quelles");
      } else {
        fd.set("file", files[0]);
        toast("Envoi du brouillon…");
        await upload(`/api/characters/${encodeURIComponent(slug)}/versions/${v.version}/canon-draft`, fd);
        toast("Brouillon déposé : prends-le tel quel, ou valide la dépense pour une version réaliste");
      }
      showCharacter(slug);
    } catch (e) { toast(e.message, "err"); }
  });
  $view.onclick = (e) => characterClick(e, ch, v);
  $view.onchange = async (e) => {
    const t = e.target;
    if (!t.dataset || !t.dataset.assetkind) return;
    try { await api(`/api/character-assets/${t.dataset.assetkind}/kind`, { json: { kind: t.value } }); toast("Catégorie changée"); }
    catch (err) { toast(err.message, "err"); }
  };
  every(10000, () => showCharacter(slug, true));
}

function charPanel(title, help, body, extra = "") {
  return `<section class="panel stack charsec"><div class="panel-head"><h2>${title}</h2><span class="spacer"></span>${extra}</div>
    <p class="hint helptext">${help}</p>${body}</section>`;
}

function spendRows(list) {
  if (!list.length) return "";
  const total = list.reduce((a, r) => a + r.est_usd, 0);
  return `<div class="spendbox">
    <p><b>En attente de ton accord</b> : ${list.length} image${list.length > 1 ? "s" : ""}, environ ${money(total)}
      (${list.every((r) => r.funding === "credits") ? "payé sur les crédits gratuits" : "payé en argent"}).</p>
    <ul class="hint">${list.slice(0, 8).map((r) => `<li>${esc(r.label)} · ${money(r.est_usd)}</li>`).join("")}${list.length > 8 ? `<li>…</li>` : ""}</ul>
    <div class="row"><button class="btn go" data-spenddo="approve" data-ids="${list.map((r) => r.id).join(",")}">Lancer · ${money(total)}</button>
      <button class="btn" data-spenddo="refuse" data-ids="${list.map((r) => r.id).join(",")}">Ne pas lancer</button></div></div>`;
}

function mediaGrid(items) {
  return `<div class="packgrid">${items.map((m) => `<div class="packitem">
      ${m.type === "video" ? `<video src="${media(m.path)}" controls muted loop playsinline preload="metadata"></video>`
        : `<img src="${media(m.path)}" data-zoom="${media(m.path)}" alt="">`}
      <div class="pi"><span class="hint">${esc(m.caption || m.path.split("/").pop())}</span></div></div>`).join("")}</div>`;
}

function packSection(v, editable) {
  const pack = v.assets.filter((a) => !["canon", "canon_draft"].includes(a.kind) && a.status !== "failed"
    && (editable || a.status === "kept") && a.path);
  const byKind = {};
  pack.forEach((a) => { (byKind[a.kind] = byKind[a.kind] || []).push(a); });
  return Object.entries(byKind).map(([k, list]) => `<h3 style="margin:14px 0 8px">${esc(CHAR_KIND_LABEL[k] || k)}</h3>
    <div class="packgrid">${list.map((a) => `<div class="packitem ${a.status}">
      ${a.status === "generating" ? `<div class="none" style="aspect-ratio:3/4;display:grid;place-items:center">${led("work")}</div>` : `<img src="${media(a.path)}" data-zoom="${media(a.path)}" alt="">`}
      <div class="pi"><span>${esc(a.label || "")}${a.status === "kept" && editable ? " · gardée" : a.status === "rejected" ? " · écartée" : ""}</span>
        ${a.comment ? `<span class="hint">« ${esc(a.comment)} »</span>` : ""}
        ${editable && a.status === "proposed" ? `<input type="text" data-cm="${a.id}" placeholder="Pourquoi, si tu l'écartes" style="padding:6px 8px;font-size:12px">
          <div class="row" style="gap:6px"><button class="btn small ok" data-pickasset="${a.id}:keep">Garder</button>
          <button class="btn small" data-pickasset="${a.id}:reject">Écarter</button></div>` : ""}
      </div></div>`).join("")}</div>`).join("");
}

function looksSection(ch) {
  const looks = ch.looks.map((lk) => `<div class="lookcard">
      <div class="row"><b>${esc(lk.slug)}</b><span class="spacer"></span>
        <span class="hint">${lk.clips.length ? "Dans : " + lk.clips.map(esc).join(", ") : "Dans aucun clip pour l'instant"}</span></div>
      ${lk.description ? `<p class="hint">${esc(lk.description)}</p>` : ""}
      ${lk.images.length ? mediaGrid(lk.images.map((p) => ({ path: p, type: "image" }))) : ""}
      ${dropZone("look:" + lk.slug, "Ajouter des photos de cette tenue", "png, jpg ou webp, plusieurs à la fois", "image/*", true)}
    </div>`).join("");
  return charPanel("Tenues",
    `Les tenues que ${esc(ch.name)} porte dans les clips. Chaque tenue a un nom, une description et quelques photos.
     Une tenue sert de référence pour les plans où elle la porte. Elle se réutilise d'un clip à l'autre.`,
    `${looks || `<p class="hint">Aucune tenue pour l'instant.</p>`}
     <div class="lookcard"><b>Nouvelle tenue</b>
       <input type="text" id="look-name" placeholder="Nom (ex. tailleur de bureau)">
       <textarea id="look-desc" rows="3" placeholder="Description (ex. tailleur gris anthracite, chemisier blanc, escarpins noirs)"></textarea>
       <div class="row"><button class="btn go" data-newlook>Créer la tenue</button></div></div>`);
}

function renderVersion(ch, v) {
  const editable = v.status === "draft";
  const canon = v.assets.filter((a) => a.kind === "canon" && a.status === "kept").pop();
  const candidates = v.assets.filter((a) => a.kind === "canon" && ["proposed", "generating"].includes(a.status));
  const draft = v.assets.filter((a) => a.kind === "canon_draft" && a.status === "kept").pop();
  const spendHd = ch.spend.filter((r) => r.action === "canon_hd");
  const spendPack = ch.spend.filter((r) => r.action === "character_asset");
  const intro = editable
    ? `<p class="hint">Version ${v.version} en préparation. Tant qu'elle n'est pas validée, les clips utilisent la version ${ch.canon_version || "validée"}.</p>`
    : `<p class="hint">Version ${v.version}, validée${v.version === ch.canon_version ? " : c'est la référence actuelle de " + esc(ch.name) : ""}. Elle ne se modifie plus ; pour faire évoluer le personnage, crée une nouvelle version.</p>`;

  const nWords = (t) => (t || "").trim().split(/\s+/).filter(Boolean).length;
  const adnBody = editable
    ? `<details class="fold" ${v.adn ? "" : "open"}><summary>${v.adn ? `Lire et modifier la fiche (${nWords(v.adn)} mots)` : "Écrire la fiche"}</summary><div class="stack" style="gap:8px">
       <textarea id="adn" rows="14">${esc(v.adn || "")}</textarea>
       <div class="row"><button class="btn" data-saveadn>Enregistrer la fiche</button>
         <span class="hint">${nWords(v.adn)} mots · idéal : 300 à 600${nWords(v.adn) > 700 ? " (au-delà, les redites et les détails secondaires brouillent les agents)" : ""}</span></div>
       <details class="fold"><summary>Comment écrire une bonne fiche</summary><div><p class="hint">
         300 à 600 mots, en anglais ou en français, en 6 parties courtes, sans redire la même chose deux fois :
         <b>1. Identité</b> (qui, âge, gabarit) · <b>2. Apparence</b> (tête, yeux, peau ou pelage, cheveux, couleurs exactes) ·
         <b>3. Signes distinctifs</b> (ce qui le rend unique) · <b>4. Caractère</b> (3 à 5 traits, avec à quoi on les voit) ·
         <b>5. Façon de bouger</b> · <b>6. Toujours / Jamais</b> (5 à 8 règles en tout).
         Évite les comportements qui, sortis du contexte, donnent une image fausse (« montre les dents » peut produire un chien agressif) :
         dis plutôt dans quelle situation ils arrivent. Le résumé visuel, lui, fait 60 à 120 mots en anglais.</p></div></details>
       </div></details>
       <h3 style="margin-top:8px">Résumé visuel</h3>
       <p class="hint">Le seul texte envoyé tel quel aux modèles d'image, en anglais, 60 à 120 mots : ce qui se voit et doit toujours être identique.
         La fiche complète, elle, est lue par les agents, qui en tirent ce qu'il faut pour chaque plan.</p>
       <textarea id="resume" rows="5">${esc(v.resume || "")}</textarea>
       <div class="row"><button class="btn" data-saveresume>Enregistrer le résumé</button><span class="hint">${nWords(v.resume)} mots</span></div>`
    : (v.adn ? `<details class="fold"><summary>Lire la fiche (${nWords(v.adn)} mots)</summary><div><pre class="text">${esc(v.adn)}</pre></div></details>${v.resume ? `<h3>Résumé visuel</h3><pre class="text">${esc(v.resume)}</pre>` : ""}` : `<p class="hint">Pas de fiche écrite pour cette version.</p>`);

  const packHtml = packSection(v, editable);
  const KLABEL = { canon: "canon", sheet: "référence (feuille, photo)", turnaround: "angle", fullbody: "en pied",
    expressions: "expression", lighting: "lumière", details: "détail", canon_draft: "à classer" };
  const mine = v.assets.filter((a) => a.status === "kept" && a.path && a.kind !== "canon"
    && (a.comment === "image de Michael" || a.kind === "canon_draft"));
  const refsBody = `<div class="two-col">
      <div>${canon ? `<img class="canonbig" src="${media(canon.path)}" data-zoom="${media(canon.path)}" alt="Canon">
          <p class="hint">La canon : l'image principale, envoyée en premier à chaque génération.</p>
          ${editable ? `<div class="row" style="gap:8px"><button class="btn small" data-canonhd ${ch.canon_hd.usable ? "" : "disabled"}>Générer une version HD réaliste · ${money(ch.canon_hd.cost_usd)}</button>
            <span class="hint">${ch.canon_hd.usable ? "Elle arrive dans les candidates : tu choisis ensuite laquelle est la canon." : `Pas encore branché : ${esc(ch.canon_hd.model)} demande une clé fal (page Fournisseurs).`}</span></div>` : ""}`
        : `<p class="empty">Pas encore de canon : choisis-la parmi tes images (bouton « En faire la canon »).</p>`}</div>
      <div class="stack">
        ${mine.length ? `<div class="packgrid">${mine.map((a) => `<div class="packitem kept">
            <img src="${media(a.path)}" data-zoom="${media(a.path)}" alt="">
            <div class="pi">${editable && a.kind !== "canon_draft" ? `<select data-assetkind="${a.id}" aria-label="Catégorie">${["sheet", "turnaround", "fullbody", "expressions", "lighting", "details"]
                .map((k) => `<option value="${k}" ${k === a.kind ? "selected" : ""}>${esc(KLABEL[k])}</option>`).join("")}</select>`
                : `<span class="hint">${esc(KLABEL[a.kind] || a.kind)}</span>`}
              ${editable ? `<div class="row" style="gap:6px"><button class="btn small" data-draftto="${a.id}:canon">En faire la canon</button>
                ${a.kind === "canon_draft" ? `<button class="btn small" data-draftto="${a.id}:sheet">Garder comme référence</button>` : ""}
                <button class="btn small ghost" data-pickasset="${a.id}:reject">Retirer</button></div>` : ""}</div></div>`).join("")}</div>`
          : `<p class="hint">Aucune image déposée pour l'instant.</p>`}
        ${candidates.length ? `<h3>Candidates générées</h3><div class="packgrid">${candidates.map((a) => `<div class="packitem">
          ${a.status === "generating" ? `<div class="none" style="aspect-ratio:3/4;display:grid;place-items:center">${led("work")} en cours</div>` : `<img src="${media(a.path)}" data-zoom="${media(a.path)}" alt="">`}
          <div class="pi">${a.status === "proposed" ? `<div class="row" style="gap:6px"><button class="btn small ok" data-pickasset="${a.id}:canon">Choisir comme canon</button>
            <button class="btn small" data-pickasset="${a.id}:reject">Écarter</button></div>` : ""}</div></div>`).join("")}</div>` : ""}
        ${editable ? `<label class="field"><span>Ce que tu déposes</span><select id="pack-kind">
            <option value="sheet">Image de référence (feuille, photo, vues…)</option><option value="canon">La canon (image principale)</option>
            <option value="turnaround">Angles</option><option value="fullbody">En pied</option><option value="expressions">Expressions</option>
            <option value="lighting">Lumières</option><option value="details">Détails</option></select></label>
          ${dropZone("pack", "Déposer tes images", "png, jpg ou webp, plusieurs à la fois", "image/*", true)}` : ""}
      </div></div>`;

  const genBody = editable ? `
      <p class="hint">Facultatif. Si ton pack ne suffit pas, l'agent de casting peut générer des images en plus à partir de la canon (payant, avec ton accord).</p>
      <textarea id="instructions" rows="5" placeholder="Ex. : 2 plans en pied supplémentaires, expressions rire et colère">${esc(v.instructions || "")}</textarea>
      <div class="row"><button class="btn" data-saveinstr>Enregistrer</button>
        <button class="btn" data-pack ${canon ? "" : "disabled"}>Faire générer ces images</button>
        ${canon ? "" : `<span class="hint">Choisis d'abord une canon.</span>`}</div>
      ${v.pack_status === "requested" ? `<p>${led("work")} L'agent de casting prépare les demandes d'images.</p>` : ""}
      ${spendRows(spendPack)}
      ${packSection({ ...v, assets: v.assets.filter((a) => a.comment !== "image de Michael") }, editable)}
      <details class="fold"><summary>Version HD réaliste d'une image (payante)</summary><div class="stack" style="gap:8px">
        <p class="hint">Si ton image est un dessin ou un rendu peu réaliste, la machine peut en tirer une photo réaliste HD, avec le même personnage. Le résultat arrive dans les candidates.</p>
        ${spendRows(spendHd)}
        ${dropZone("canon", "Déposer l'image à rendre réaliste", "png, jpg ou webp", "image/*", false)}</div></details>`
    : (packHtml || "");

  return `${intro}
    ${charPanel("Tes images de référence",
      `Tout ce que tu déposes ici sert de référence telle quelle dans les clips : la canon (l'image principale) et le reste du pack.
       Rien n'est généré, rien n'est payé.`, refsBody)}
    ${charPanel("Fiche du personnage",
      `Qui est ${esc(ch.name)} : apparence, caractère, façon de bouger, ce qu'il faut toujours respecter et ne jamais faire. Les agents la lisent en entier : le casting, le storyboard et le prompteur, qui reprennent seulement ce qui sert la scène. Le résumé visuel, plus bas, est le seul texte envoyé tel quel aux modèles d'image.`, adnBody)}
    ${editable ? charPanel("Compléter par génération (facultatif)", `Des images en plus, générées à partir de la canon.`, genBody)
      : (packHtml ? charPanel("Images générées", "", packHtml) : "")}
    ${charPanel("Essais et tests",
      `Ce qui a été réussi pour cette version en dehors du pack : tests de modèles concluants, vidéos d'essai, bonnes images. On le garde pour capitaliser sur l'identité du personnage.`,
      v.essais.length ? mediaGrid(v.essais) : `<p class="hint">Aucun essai pour l'instant.</p>`)}
    ${looksSection(ch)}
    ${editable ? `<section class="panel row" style="margin-top:16px"><p class="hint" style="flex:1">Quand la canon, la fiche et le pack te conviennent, valide la version ${v.version}.
        Elle devient la référence de ${esc(ch.name)} pour les prochains clips.</p>
        <button class="btn ok" data-validate="${v.version}" ${canon ? "" : "disabled"}>Valider la version ${v.version}</button></section>` : ""}`;
}

async function characterClick(e, ch, v) {
  const t = e.target.closest("button, [data-zoom]");
  if (!t) return;
  const d = t.dataset;
  const slug = ch.slug;
  const base = `/api/characters/${encodeURIComponent(slug)}`;
  const reload = () => showCharacter(slug);
  try {
    if (d.zoom) return lightbox(d.zoom);
    if (d.version) { state.charVersion = +d.version; return reload(); }
    if (d.newversion !== undefined) {
      const r = await api(`${base}/versions`, { method: "POST" });
      state.charVersion = r.version;
      toast(`Version ${r.version} créée`);
      return reload();
    }
    if (d.spenddo) {
      t.disabled = true;
      await api("/api/spend/decide", { json: { ids: d.ids.split(",").map(Number), decision: d.spenddo } });
      toast(d.spenddo === "approve" ? "Lancé : les images arrivent dans une à deux minutes" : "Pas lancé");
      refreshSys();
      return reload();
    }
    if (d.canonhd !== undefined) {
      if (needsConfirm(t, "canonhd")) return;
      t.disabled = true;
      await api(`${base}/versions/${v.version}/canon-hd`, { method: "POST" });
      toast("Version HD lancée : elle arrive dans les candidates dans une à deux minutes");
      refreshSys(); return reload();
    }
    if (d.draftto) {
      const [asset_id, kind] = d.draftto.split(":");
      await api(`${base}/versions/${v.version}/draft-to`, { json: { asset_id: +asset_id, kind } });
      toast(kind === "canon" ? "Le brouillon est la canon, tel quel" : "Rangé dans le pack, tel quel");
      return reload();
    }
    if (d.saveresume !== undefined) {
      await api(`${base}/versions/${v.version}/resume`, { json: { text: document.getElementById("resume").value } });
      toast("Résumé enregistré");
      return reload();
    }
    if (d.saveadn !== undefined) {
      await api(`${base}/versions/${v.version}/adn`, { json: { text: document.getElementById("adn").value } });
      toast("Fiche enregistrée");
      return reload();
    }
    if (d.newlook !== undefined) {
      const name = document.getElementById("look-name").value.trim();
      if (!name) { toast("Donne un nom à la tenue", "err"); return; }
      await api(`${base}/looks`, { json: { name, description: document.getElementById("look-desc").value } });
      toast("Tenue créée : ajoute-lui des photos");
      return reload();
    }
    if (d.saveinstr !== undefined || d.pack !== undefined) {
      await api(`${base}/versions/${v.version}/instructions`, { json: { text: document.getElementById("instructions").value } });
      if (d.pack !== undefined) {
        await api(`${base}/versions/${v.version}/pack`, { method: "POST" });
        toast("L'agent prépare les demandes : elles apparaîtront ici pour ton accord");
      } else toast("Instructions enregistrées");
      return reload();
    }
    if (d.pickasset) {
      const [id, decision] = d.pickasset.split(":");
      const comment = decision === "reject" ? ($view.querySelector(`[data-cm="${id}"]`)?.value || "").trim() : "";
      await api(`/api/character-assets/${id}`, { json: { decision, comment } });
      toast({ keep: "Image gardée", reject: "Image écartée", canon: "C'est la nouvelle canon" }[decision]);
      return reload();
    }
    if (d.validate) {
      if (needsConfirm(t, "validate" + d.validate)) return;
      await api(`${base}/versions/${d.validate}/validate`, { method: "POST" });
      toast("Version validée : elle devient la référence des prochains clips");
      return reload();
    }
  } catch (err) { toast(err.message, "err"); }
}

/* ---------- Fournisseurs ---------- */

async function showProviders() {
  const d = await api("/api/providers");
  const provLabel = Object.fromEntries(d.providers.map((p) => [p.key, p.label]));
  const provs = d.providers.map((p) => {
    const st = !p.implemented ? ["pas encore dans le code", "wait"] : !p.enabled ? ["désactivé", "wait"]
      : p.has_key ? ["branché", "done"] : p.simulated ? ["simulation", "review"] : ["clé manquante", "review"];
    const cr = d.credits[p.key];
    const keys = p.keys.map((k) => `<div class="pkey">
        <div class="row" style="gap:6px"><span class="mono">${esc(k.name)}</span>
          ${p.any_of.includes(k.name) && p.any_of.length > 1 ? `<span class="hint">(une des ${p.any_of.length} suffit)</span>` : ""}
          ${k.optional ? `<span class="hint">(facultative)</span>` : ""}
          <span class="spacer"></span>${k.masked ? `<span class="mono hint">${esc(k.masked)}</span>` : `<span class="hint">absente</span>`}</div>
        <div class="row" style="gap:6px">
          <input type="password" autocomplete="off" data-pkeyval="${esc(p.key)}:${esc(k.name)}" placeholder="${k.masked ? "Nouvelle valeur pour la changer" : "Colle la clé ici"}" style="flex:1;min-width:150px">
          <button class="btn small" data-pkeyset="${esc(p.key)}:${esc(k.name)}">${k.masked ? "Changer" : "Ajouter"}</button>
          ${k.masked ? `<button class="btn small ghost danger" data-pkeyrm="${esc(p.key)}:${esc(k.name)}">Retirer</button>` : ""}
        </div></div>`).join("");
    return `<div class="panel stack prov ${p.enabled ? "" : "off"}" style="gap:8px">
      <div class="row"><b>${esc(p.label)}</b><span class="spacer"></span>${pill(st[0], st[1])}</div>
      <p class="hint">${esc(p.note)}</p>
      ${cr ? `<div class="progress"><i style="width:${Math.min(100, (100 * cr.spent) / cr.usd)}%"></i></div>
        <p class="mono" style="font-size:13px">${esc(cr.label)} : ${money(cr.remaining)} restants sur ${cr.usd.toFixed(0)} $${cr.expires ? ` · jusqu'au ${esc(cr.expires)}` : ""}</p>` : ""}
      <details class="fold" ${p.implemented && p.enabled && !p.has_key ? "open" : ""}><summary>Clés${p.has_key ? (p.keys.some((k) => k.optional && !k.masked) ? " · facultative" : "") : " · à renseigner"}</summary><div class="stack" style="gap:10px">${keys}
        <p class="hint">La clé est rangée sur le PC (fichier .env) et n'est jamais réaffichée : seuls ses 4 derniers caractères le sont.</p></div></details>
      <div class="row"><button class="btn small ${p.enabled ? "ghost" : "go"}" data-penable="${esc(p.key)}:${p.enabled ? "0" : "1"}">${p.enabled ? "Désactiver" : "Activer"}</button>
        <span class="hint">${p.enabled ? "Une fois désactivé, il n'est plus utilisé, même avec ses clés." : "Il n'est pas utilisé tant qu'il est désactivé."}</span></div>
    </div>`;
  }).join("");
  const rows = d.video_models.map((m) => `<tr style="${m.usable ? "" : "opacity:.5"}">
      <td><b>${esc(m.label)}</b>${m.to_test ? ` <span class="pill work">à tester</span>` : ""}<br><span class="hint">${esc(m.use_for)}</span></td>
      <td>${esc(provLabel[m.provider] || m.provider)}</td>
      <td class="mono">${m.per_second_usd.toFixed(3)} $</td>
      <td>${m.tiers.map((t) => `<span class="tag">${esc(t)}</span>`).join(" ")}</td>
      <td class="hint">${esc(m.duration_range)}${m.aspects ? `<br>${m.aspects.map(esc).join(", ")}` : ""}</td></tr>`).join("");
  const rod = d.rodage.length ? d.rodage.map((r) => `<tr><td><b>${esc(r.model)}</b></td><td class="mono">${r.drafts}</td>
      <td class="mono">${r.taux_premier_coup == null ? "–" : Math.round(r.taux_premier_coup * 100) + " %"}</td>
      <td class="mono">${r.refaits}</td><td class="mono">${r.echecs}</td>
      <td class="hint">${r.retours.slice(-3).map(esc).join("<br>")}</td></tr>`).join("")
    : `<tr><td colspan="6" class="hint">Pas encore de vidéo jugée.</td></tr>`;
  $view.innerHTML = `<div class="pagehead"><h1>Fournisseurs</h1>
      <span class="sub">Règle : le moins cher qui est adapté au plan, crédits gratuits d'abord. Détail dans docs/PROCESS.md et docs/FOURNISSEURS.md.</span></div>
    <div class="clips" style="grid-template-columns:repeat(auto-fill,minmax(280px,1fr))">${provs}</div>
    <div class="panel" style="margin-top:18px;overflow-x:auto"><div class="panel-head"><h2>Offres vidéo</h2>
      <span class="hint">Coût par seconde de plan, tout compris (vidéo draft, vidéo HD), sans son. Classées du moins cher au plus cher.</span></div>
      <table class="cut" style="width:100%;border-collapse:collapse;font-size:14px">
        <thead><tr><th align="left">Modèle</th><th align="left">Fournisseur</th><th align="left">$/s</th><th align="left">Paliers tenus</th><th align="left">Durées, formats</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
    <div class="panel" style="margin-top:18px;overflow-x:auto"><div class="panel-head"><h2>Carnet de rodage</h2>
      <span class="hint">Ce que tes validations disent de chaque modèle. Le routeur le lit avant de choisir.</span></div>
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <thead><tr><th align="left">Modèle</th><th align="left">Vidéos</th><th align="left">Validées du 1er coup</th><th align="left">Refaites</th><th align="left">Échecs</th><th align="left">Derniers retours</th></tr></thead>
        <tbody>${rod}</tbody></table></div>
    <p class="hint" style="margin-top:14px">Lip-sync : ${esc(d.lipsync)} · Visuel HD : ${esc(d.image_upscale)}</p>`;
  $view.onclick = async (ev) => {
    const t = ev.target.closest("button");
    if (!t) return;
    const d2 = t.dataset;
    try {
      if (d2.pkeyset) {
        const [prov, name] = d2.pkeyset.split(":");
        const input = $view.querySelector(`[data-pkeyval="${prov}:${name}"]`);
        if (!input.value.trim()) { toast("Colle d'abord la clé", "err"); return; }
        await api(`/api/providers/${prov}/key`, { json: { name, value: input.value.trim() } });
        input.value = "";
        toast("Clé enregistrée"); refreshSys(); return showProviders();
      }
      if (d2.pkeyrm) {
        if (needsConfirm(t, "pkeyrm" + d2.pkeyrm)) return;
        const [prov, name] = d2.pkeyrm.split(":");
        await api(`/api/providers/${prov}/key/${name}`, { method: "DELETE" });
        toast("Clé retirée"); refreshSys(); return showProviders();
      }
      if (d2.penable) {
        const [prov, on] = d2.penable.split(":");
        await api(`/api/providers/${prov}/enabled`, { json: { enabled: on === "1" } });
        toast(on === "1" ? "Fournisseur activé" : "Fournisseur désactivé"); return showProviders();
      }
    } catch (e) { toast(e.message, "err"); }
  };
  every(30000, () => { if (!isBusy()) showProviders(); });
}

/* ---------- clavier ---------- */

document.addEventListener("keydown", (e) => {
  if (isBusy()) return;
  if (e.key === "Escape" && !$drawer.hidden) {
    location.hash = `#/clip/${encodeURIComponent(state.clip.slug)}/${state.tab}`;
  } else if (e.key === " " && state.clip && document.getElementById("console")) {
    e.preventDefault();
    if (song.paused) song.play().catch(() => {}); else song.pause();
  } else if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && !$drawer.hidden) {
    const btns = $drawer.querySelectorAll(".drawer-head [data-goshot]");
    const b = e.key === "ArrowLeft" ? btns[0] : btns[1];
    if (b && b.dataset.goshot) location.hash = shotHref(b.dataset.goshot);
  }
});

refreshSys();
router();


/* ---------- dépenses à valider ---------- */
const FUNDING_LABEL = { credits: "crédits gratuits", cash: "payé en argent" };
const ACTION_LABEL = { image: "Visuel draft", image_hd: "Visuel HD", canon_hd: "Canon HD", character_asset: "Pack de référence" };

async function showSpend() {
  const d = await api("/api/spend");
  const groups = {};
  for (const r of d.pending) {
    const g = r.clip_slug ? `Clip ${r.clip_slug}` : `Personnage ${r.character_slug || ""}`;
    (groups[g] = groups[g] || []).push(r);
  }
  const credits = Object.values(d.credits).map((c) => `${esc(c.label)} : ${money(c.remaining)} restants`).join(" · ");
  const card = (r) => `
    <div class="spend-item">
      <div class="row"><b>${esc(r.label)}</b><span class="spacer"></span><span class="spend-cost">${money(r.est_usd)}</span></div>
      <p class="hint">${esc(ACTION_LABEL[r.action] || r.action)} · ${esc(r.model_label || "")} · ${esc(FUNDING_LABEL[r.funding] || r.funding)}</p>
      ${r.detail ? `<details><summary class="hint">Ce qui sera demandé</summary><p class="mono spend-detail">${esc(r.detail)}</p></details>` : ""}
      <div class="row">
        <button class="btn small go" data-spend="approve" data-ids="${r.id}">Lancer · ${money(r.est_usd)}</button>
        <button class="btn small" data-spend="refuse" data-ids="${r.id}">Ne pas lancer</button>
      </div>
    </div>`;
  const blocks = Object.entries(groups).map(([g, items]) => {
    const total = items.reduce((a, r) => a + r.est_usd, 0);
    return `<section class="panel stack">
      <div class="row"><h2>${esc(g)}</h2><span class="spacer"></span>
        ${items.length > 1 ? `<button class="btn go" data-spend="approve" data-ids="${items.map((r) => r.id).join(",")}">Tout lancer (${items.length}) · ${money(total)}</button>` : ""}</div>
      ${items.map(card).join("")}
    </section>`;
  }).join("");
  const recent = d.recent.slice(0, 10).map((r) => `<li>${esc(r.label)} · ${money(r.est_usd)} · <i>${esc({approved: "accordée, lancement en cours", refused: "non lancée", done: "lancée", failed: "échec : " + (r.note || "")}[r.status] || r.status)}</i></li>`).join("");
  $view.innerHTML = `
    <div class="pagehead"><h1>Dépenses à valider</h1></div>
    <div class="stack">
      <p class="hint">Rien de payant ne part sans ton accord, même sur les crédits gratuits. Chaque ligne indique ce qui sera généré, avec quel modèle et pour combien.
        Les vidéos ont leur propre validation, dans le plan vidéo de chaque plan, coût compris.</p>
      ${credits ? `<p class="mono">${credits}</p>` : ""}
      ${blocks || `<p class="empty">Aucune dépense en attente.</p>`}
      ${recent ? `<section class="panel"><h2>Dernières décisions</h2><ul class="hint">${recent}</ul></section>` : ""}
    </div>`;
  $view.querySelectorAll("[data-spend]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    try {
      const ids = b.dataset.ids.split(",").map(Number);
      await api("/api/spend/decide", { json: { ids, decision: b.dataset.spend } });
      toast(b.dataset.spend === "approve" ? "Lancé : la génération part dans moins d'une minute" : "Pas lancé");
      await refreshSys(); await showSpend();
    } catch (e) { toast(e.message, "err"); b.disabled = false; }
  }));
}


/* ---------- champs de texte : hauteur ajustée au contenu (lisible sur téléphone) ---------- */
function fitTextarea(t) {
  if (!t || t.offsetParent === null) return;
  t.style.height = "auto";
  t.style.height = `${t.scrollHeight + 2}px`;
}
function fitAll(root = document) { root.querySelectorAll("textarea").forEach(fitTextarea); }
document.addEventListener("input", (e) => { if (e.target.tagName === "TEXTAREA") fitTextarea(e.target); });
["view", "drawer"].forEach((id) => new MutationObserver(() => requestAnimationFrame(() => fitAll()))
  .observe(document.getElementById(id), { childList: true, subtree: true }));
document.addEventListener("toggle", () => fitAll(), true);
window.addEventListener("resize", () => fitAll());


/* ---------- Décors, objets et figurants ---------- */
const EL_KIND = {
  decor: ["Décors", "Les lieux du clip.", "D"],
  figurant: ["Figurants", "Les personnages secondaires et les animaux.", "F"],
  objet: ["Objets clés", "Les objets qui reviennent ou comptent pour l'histoire.", "O"] };
const EL_STEP = {
  start: ["Images et instruction à donner", "review"],
  draft_choose: ["Brouillon à choisir", "review"],
  hd_todo: ["Image HD à lancer", "review"],
  hd_wait: ["Image HD en cours ou à choisir", "work"],
  done: ["Prêt", "done"] };

async function loadDecors(clip, keep = false) {
  const box = document.getElementById("decors-tab");
  if (!box) return;
  const d = await api(`/api/clips/${encodeURIComponent(clip.slug)}/elements`);
  const json = JSON.stringify(d);
  if (keep && json === state.decorsJson) return;
  state.decorsJson = json;
  const open = new Set(prefs("elopen:" + clip.slug) || []);
  const byKind = { decor: [], figurant: [], objet: [] };
  d.elements.forEach((e) => (byKind[e.kind] || []).push(e));
  const code = {};
  Object.entries(byKind).forEach(([k, list]) => list.forEach((e, i) => { code[e.id] = `${EL_KIND[k][2]}${i + 1}`; }));
  const spendFor = (e) => d.spend.filter((r) => r.label.includes(`« ${e.name} »`));
  const thumbOfEl = (e) => (e.images.find((i) => i.role === "hd" && i.status === "kept")
    || e.images.find((i) => i.role === "draft") || {}).path;
  const stateSelect = (e, attr) => `<select ${attr}><option value="">État de base</option>${e.states.map((x) => `<option>${esc(x)}</option>`).join("")}</select>`;
  const ready = d.elements.filter((e) => e.step === "hd_todo" && e.prompt_status !== "requested");
  const cost = (n) => money(n * d.hd_cost);

  const card = (e) => {
    const drafts = e.images.filter((i) => i.role === "draft" && i.status === "kept");
    const draftProp = e.images.filter((i) => i.role === "draft" && i.status !== "kept");
    const inspi = e.images.filter((i) => i.role === "inspi");
    const hdKept = e.images.filter((i) => i.role === "hd" && i.status === "kept");
    const hdProp = e.images.filter((i) => i.role === "hd" && i.status !== "kept");
    const sp = spendFor(e);
    const isOpen = open.has(String(e.id));
    const th = thumbOfEl(e);
    const [stepTxt, stepCls] = EL_STEP[e.step];
    const s1 = drafts.length > 0 || hdKept.some((i) => i.source === "michael");
    const s3 = hdKept.length > 0;
    return `<details class="elcard k-${e.kind}" id="el-${e.id}" data-elid="${e.id}" ${isOpen ? "open" : ""}>
      <summary>
        <span class="elcode">${code[e.id]}</span>
        ${th ? `<img class="elthumb" src="${media(th)}" alt="">` : `<span class="elthumb none">?</span>`}
        <span class="elname"><b>${esc(e.name)}</b>
          <span class="hint">@${esc(e.slug)} · ${e.shots.length ? `plans ${compactNums(e.shots)}` : "relié à aucun plan"}</span></span>
        ${pill(stepTxt, stepCls)}
      </summary>
      <div class="elbody">
        <div class="row elrename" style="gap:8px">
          <input type="text" data-elname="${e.id}" value="${esc(e.name)}" aria-label="Nom" style="flex:1;min-width:180px">
          <button class="btn small" data-elrename="${e.id}">Renommer</button>
          <button class="btn small ghost danger" data-eldel="${e.id}">Supprimer</button>
        </div>
        <div class="elstep ${inspi.length || (e.brief || "").trim() || drafts.length ? "ok" : ""}">
          <div class="elstep-h"><span class="num">1</span><b>Tes images et ton instruction</b>
            <span class="hint">Des images trouvées ou faites ailleurs, et ce que tu veux. Elles servent à créer le brouillon.</span></div>
          ${inspi.length ? elGrid(inspi, "inspi") : ""}
          ${dropZone(`el:${e.id}:inspi`, inspi.length ? "Ajouter des images" : "Déposer des images", "png, jpg ou webp, 4 au plus", "image/*", true)}
          <label class="field"><span>Ton instruction</span>
            <textarea rows="3" data-elbrief="${e.id}" placeholder="Ex. : le canapé vert de la 2e image, la fenêtre à droite comme sur la 1re, lumière de fin de journée">${esc(e.brief || "")}</textarea></label>
        </div>

        <div class="elstep ${drafts.length ? "ok" : ""}">
          <div class="elstep-h"><span class="num">2</span><b>Brouillon</b>
            <span class="hint">${drafts.length ? "Gardé : l'image HD reprendra sa composition." : "Crée-le gratuitement à partir de l'étape 1, ou dépose le tien."}</span></div>
          ${drafts.length ? elGrid(drafts, "draft") : ""}
          ${draftProp.length ? `<p class="hint">Garde le brouillon qui te plaît, écarte les autres.</p>${elGrid(draftProp, "choose")}` : ""}
          <div class="row" style="gap:8px">
            <button class="btn ${drafts.length ? "" : "go"}" data-eldrafts="${e.id}" ${d.drafts_usable ? "" : "disabled"}>${draftProp.length || drafts.length ? "Créer 2 autres brouillons" : "Créer 2 brouillons"} · gratuit</button>
            <span class="hint">${d.drafts_usable ? "Gratuit. De quelques secondes à deux minutes." : "Aucune option gratuite branchée (page Fournisseurs)."}</span></div>
          <details class="fold"><summary>Ou dépose ton propre brouillon</summary><div class="stack" style="gap:6px">
            ${dropZone(`el:${e.id}:draft`, "Déposer ton brouillon", "png, jpg ou webp", "image/*", false)}</div></details>
        </div>

        <div class="elstep ${s3 ? "ok" : ""}">
          <div class="elstep-h"><span class="num">3</span><b>Image HD</b>
            <span class="hint">${s3 ? "Gardée : elle sert de référence aux visuels des plans." : "La version finale du brouillon, qui servira de référence aux plans."}</span></div>
          ${hdKept.length ? elGrid(hdKept, "kept") : ""}
          ${hdProp.length ? `<p class="hint">Garde la bonne image HD.</p>${elGrid(hdProp, "choose")}` : ""}
          ${sp.length ? spendRows(sp) : ""}
          ${!drafts.length ? `<p class="hint">Garde d'abord un brouillon à l'étape 2.</p>`
            : e.prompt_status === "requested" ? `<div class="agentbar">${led("work")}Le décorateur regarde ton brouillon et écrit le prompt de l'image HD (une à deux minutes).</div>`
            : `<label class="field"><span>Ce qui sera demandé pour l'image HD${e.prompt_edited ? " · modifié par toi" : " · écrit d'après ton brouillon, modifiable"}</span>
                <textarea rows="5" data-elprompt="${e.id}">${esc(e.prompt_text)}</textarea></label>
              <div class="row" style="gap:8px">
                <button class="btn ${e.step === "hd_todo" ? "go" : ""}" data-elgen="${e.id}" ${d.hd_usable ? "" : "disabled"}>${hdKept.length || hdProp.length ? "Refaire" : "Générer"} l'image HD · ${money(d.hd_cost)}</button>
                ${e.prompt_edited ? `<button class="btn small ghost" data-elresetprompt="${e.id}">Revenir au texte d'origine</button>`
                  : `<button class="btn small ghost" data-eldescribe="${e.id}">Réécrire d'après le brouillon</button>`}
              </div>
              ${d.hd_usable ? "" : `<p class="hint" style="color:var(--amber)">L'image HD n'est pas encore branchée.</p>`}`}
          <details class="fold"><summary>J'ai déjà une image HD finie</summary><div class="stack" style="gap:6px">
            ${dropZone(`el:${e.id}:hd`, "Déposer une image HD finie", "png, jpg ou webp", "image/*", true)}</div></details>
        </div>
      </div>
    </details>`;
  };

  const tiles = Object.entries(byKind).filter(([, l]) => l.length).map(([k, list]) => `
    <div class="eltiles-g"><h3>${EL_KIND[k][0]}</h3><div class="eltiles">${list.map((e) => {
      const th = thumbOfEl(e);
      return `<button class="eltile k-${e.kind} st-${e.step}" data-eljump="${e.id}">
        ${th ? `<img src="${media(th)}" alt="">` : `<span class="none">${code[e.id]}</span>`}
        <span class="t"><b>${code[e.id]}</b> ${esc(e.name)}</span><span class="s">${led(EL_STEP[e.step][1])}${EL_STEP[e.step][0]}</span></button>`;
    }).join("")}</div></div>`).join("");

  const sections = Object.entries(byKind).map(([k, list]) => `
    <section class="elsection k-${k}">
      <div class="elsection-h"><h2>${EL_KIND[k][0]}</h2><span class="hint">${list.length} · ${EL_KIND[k][1]}</span></div>
      ${list.map(card).join("") || `<p class="hint">Aucun pour l'instant.</p>`}</section>`).join("");
  const status = { todo: "L'agent décorateur repérera les décors dès que le découpage sera prêt.",
    requested: "L'agent décorateur repère les décors : la page se met à jour toute seule.",
    done: "" }[d.decors_status] || "";
  const nDone = d.elements.filter((e) => e.step === "done").length;
  box.innerHTML = `
    <section class="panel stack">
      <p class="hint helptext">Pour chaque décor, objet ou figurant : <b>1.</b> dépose des images et écris ce que tu veux,
        <b>2.</b> crée un brouillon gratuit (ou dépose le tien) et garde le bon, <b>3.</b> génère l'image HD et garde la bonne.
        L'image HD gardée sert de référence à tous les plans où l'élément apparaît. Dans un plan, tape <b>@</b> pour citer un élément.</p>
      <div class="row" style="gap:10px">
        <span class="hint"><b>${nDone} / ${d.elements.length}</b> prêts${status ? " · " + status : ""}</span><span class="spacer"></span>
        ${ready.length ? `<button class="btn go" data-elgenready>Générer les ${ready.length} image${ready.length > 1 ? "s" : ""} HD prêtes · ${cost(ready.length)}</button>` : ""}
        <button class="btn small ghost" data-elrequest>${d.elements.length ? "Demander à l'agent de compléter" : "Demander à l'agent de repérer les éléments"}</button>
      </div>
      ${d.hd_usable ? "" : `<p class="hint" style="color:#ffb547">Le modèle d'image HD (${esc(d.hd_model)}) n'est pas branché.</p>`}
      ${d.elements.length ? `<div class="eltiles-wrap">${tiles}</div>` : ""}
    </section>
    ${sections}
    <section class="panel stack" style="margin-top:18px"><h2>Ajouter un élément</h2>
      <div class="row" style="gap:8px"><select id="el-kind"><option value="decor">Décor</option><option value="objet">Objet clé</option><option value="figurant">Figurant</option></select>
      <input type="text" id="el-name" placeholder="Nom (ex. Maison et jardin, le chien, le vélo)" style="flex:1;min-width:200px"></div>

      <div class="row"><button class="btn go" data-elnew>Ajouter</button><span class="hint">Tu y déposeras ton image de départ ensuite.</span></div>
    </section>`;
  box.querySelectorAll("details.elcard").forEach((el) => el.addEventListener("toggle", () => {
    const set = new Set(prefs("elopen:" + clip.slug) || []);
    if (el.open) set.add(el.dataset.elid); else set.delete(el.dataset.elid);
    prefs("elopen:" + clip.slug, [...set]);
  }));
  const remember = (id) => prefs("elopen:" + clip.slug, [...new Set([...(prefs("elopen:" + clip.slug) || []), String(id)])]);
  bindDrops(box, async (kind, files) => {
    const [, id, role] = kind.split(":");
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f));
    const st = box.querySelector(`[data-eldropstate="${id}"]`);
    fd.set("state", role === "draft" && st ? st.value : "");
    fd.set("role", role);
    toast("Envoi…");
    try {
      await upload(`/api/elements/${id}/images`, fd); remember(id);
      toast(role === "draft" ? "Brouillon ajouté : le décorateur écrit le prompt de l'image HD d'après lui"
        : role === "inspi" ? "Inspiration ajoutée : dis ce que tu veux, puis crée les brouillons" : "Image HD gardée comme référence");
      loadDecors(clip);
    } catch (e) { toast(e.message, "err"); }
  });
  box.onchange = async (ev) => {
    const t = ev.target;
    if (!t.dataset || !t.dataset.elbrief) return;
    try { await api(`/api/elements/${t.dataset.elbrief}/brief`, { json: { text: t.value } }); toast("Instruction enregistrée"); }
    catch (e) { toast(e.message, "err"); }
  };
  box.onclick = async (ev) => {
    const t = ev.target.closest("button, [data-zoom]");
    if (!t) return;
    const dd = t.dataset;
    const reload = () => loadDecors(clip);
    try {
      if (dd.zoom) { ev.preventDefault(); return lightbox(dd.zoom); }
      if (dd.eljump) {
        remember(dd.eljump);
        const c = document.getElementById("el-" + dd.eljump);
        c.open = true; c.scrollIntoView({ behavior: "smooth", block: "start" }); return;
      }
      if (dd.spenddo) {
        t.disabled = true;
        await api("/api/spend/decide", { json: { ids: dd.ids.split(",").map(Number), decision: dd.spenddo } });
        toast(dd.spenddo === "approve" ? "Lancé : les images arrivent dans une à deux minutes" : "Pas lancé");
        refreshSys(); return reload();
      }
      if (dd.elrequest !== undefined) {
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/decors/request`, { method: "POST" });
        toast("L'agent décorateur démarre dans la minute"); return reload();
      }
      if (dd.elgenready !== undefined) {
        if (needsConfirm(t, "elgenready")) return;
        t.disabled = true;
        const r = await api(`/api/clips/${encodeURIComponent(clip.slug)}/elements/generate-ready`, { method: "POST" });
        toast(`${r.launched} image${r.launched > 1 ? "s" : ""} HD lancée${r.launched > 1 ? "s" : ""} · ${money(r.cost_usd)}`);
        refreshSys(); return reload();
      }
      if (dd.elnew !== undefined) {
        const name = document.getElementById("el-name").value.trim();
        if (!name) { toast("Donne un nom", "err"); return; }
        const e = await api(`/api/clips/${encodeURIComponent(clip.slug)}/elements`, { json: {
          kind: document.getElementById("el-kind").value, name, description: "" } });
        remember(e.id);
        toast("Ajouté : dépose ton image de départ"); return reload();
      }
      if (dd.eldrafts) {
        const brief = box.querySelector(`[data-elbrief="${dd.eldrafts}"]`).value;
        t.disabled = true; t.textContent = "Création des brouillons…";
        await api(`/api/elements/${dd.eldrafts}/drafts`, { json: { brief, n: 2 } });
        remember(dd.eldrafts);
        toast("Brouillons lancés : ils arrivent ici, de quelques secondes à deux minutes"); return reload();
      }
      if (dd.eldescribe) {
        await api(`/api/elements/${dd.eldescribe}/describe`, { method: "POST" });
        toast("Le décorateur regarde ton brouillon"); return reload();
      }
      if (dd.elrename) {
        const name = box.querySelector(`[data-elname="${dd.elrename}"]`).value.trim();
        if (!name) { toast("Donne un nom", "err"); return; }
        await api(`/api/elements/${dd.elrename}`, { json: { name } });
        toast("Renommé"); return reload();
      }
      if (dd.elsave) {
        const desc = box.querySelector(`[data-elf="${dd.elsave}:description"]`).value;
        await api(`/api/elements/${dd.elsave}`, { json: { description: desc } });
        toast("Fiche enregistrée"); return reload();
      }
      if (dd.elsaveprompt || dd.elresetprompt) {
        const id = dd.elsaveprompt || dd.elresetprompt;
        const text = dd.elresetprompt ? "" : box.querySelector(`[data-elprompt="${id}"]`).value;
        await api(`/api/elements/${id}/prompt`, { json: { text } });
        toast(dd.elresetprompt ? "Texte d'origine remis" : "Prompt enregistré"); return reload();
      }
      if (dd.eldel) {
        if (needsConfirm(t, "eldel" + dd.eldel)) return;
        await api(`/api/elements/${dd.eldel}`, { method: "DELETE" });
        toast("Supprimé"); return reload();
      }
      if (dd.elgen) {
        if (needsConfirm(t, "elgen" + dd.elgen)) return;
        t.disabled = true;
        const r = await api(`/api/elements/${dd.elgen}/generate`, { json: {
          prompt: box.querySelector(`[data-elprompt="${dd.elgen}"]`).value } });
        toast(`Image HD lancée · ${money(r.cost_usd)} : elle arrive dans une à deux minutes`);
        refreshSys(); return reload();
      }
      if (dd.elpick) {
        const [id, decision] = dd.elpick.split(":");
        await api(`/api/element-images/${id}`, { json: { decision } });
        toast(decision === "keep" ? "Gardée comme référence" : "Retirée"); return reload();
      }
    } catch (err) { toast(err.message, "err"); reload(); }
  };
}

function elGrid(list, mode) {
  return `<div class="packgrid elgrid">${list.map((i) => `<div class="packitem ${mode === "kept" ? "kept" : ""}">
      ${i.status === "generating" ? `<div class="none" style="aspect-ratio:4/3;display:grid;place-items:center">${led("work")} en cours</div>`
        : i.status === "failed" ? `<div class="none" style="aspect-ratio:4/3;display:grid;place-items:center;padding:8px;font-size:12px;text-align:center">Échec : ${esc((i.error || "").slice(0, 160))}</div>`
        : `<img src="${media(i.path)}" data-zoom="${media(i.path)}" alt="">`}
      <div class="pi"><span class="hint">${i.role === "inspi" ? "inspiration" : i.role === "draft" ? (i.source === "gen" ? esc(i.label || "brouillon") : "ton image") : i.source === "michael" ? "ton image HD" : "image HD"}</span>
        ${i.status === "failed" ? `<button class="btn small ghost" data-elpick="${i.id}:reject">Retirer</button>` : ""}
        ${mode === "choose" && i.status === "proposed" ? `<div class="row" style="gap:6px"><button class="btn small ok" data-elpick="${i.id}:keep">Garder</button>
          <button class="btn small" data-elpick="${i.id}:reject">Écarter</button></div>` : ""}
        ${mode !== "choose" ? `<button class="btn small ghost" data-elpick="${i.id}:reject">Retirer</button>` : ""}</div></div>`).join("")}</div>`;
}

/* ---------- Références @ dans les plans ---------- */
const normTxt = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

/* ce qu'on peut citer avec @ : les personnages du studio d'abord, puis les décors, objets et figurants du clip */
function mentionables() {
  const chars = ((state.clip && state.clip.characters_all) || []).map((c) => ({ ...c, kind: "perso" }));
  return [...chars, ...((state.clip && state.clip.elements) || [])];
}

function mentionHtml(text) {
  const idx = Object.fromEntries(mentionables().map((e) => [e.slug, e]));
  return esc(text || "").replace(/@([a-z0-9][a-z0-9-]*[a-z0-9]|[a-z0-9])/g, (m, slug) =>
    idx[slug] ? `<span class="mention k-${idx[slug].kind}" title="@${slug}">${esc(idx[slug].name)}</span>` : m);
}

const mention = { box: null, ta: null, start: 0, items: [], sel: 0 };
function mentionClose() { if (mention.box) mention.box.hidden = true; mention.ta = null; }
function mentionInsert(i) {
  const e = mention.items[i]; const ta = mention.ta;
  if (!e || !ta) return;
  const pos = ta.selectionStart;
  ta.value = ta.value.slice(0, mention.start) + "@" + e.slug + " " + ta.value.slice(pos);
  const caret = mention.start + e.slug.length + 2;
  ta.setSelectionRange(caret, caret);
  ta.dispatchEvent(new Event("input", { bubbles: true }));
  mentionClose(); ta.focus();
}
function mentionDraw() {
  if (!mention.box) {
    mention.box = document.createElement("div");
    mention.box.className = "mention-menu";
    mention.box.addEventListener("pointerdown", (ev) => {
      const b = ev.target.closest("[data-mi]"); if (!b) return;
      ev.preventDefault(); mentionInsert(+b.dataset.mi);
    });
    document.body.appendChild(mention.box);
  }
  const r = mention.ta.getBoundingClientRect();
  mention.box.style.left = `${Math.max(8, Math.min(r.left, innerWidth - 300))}px`;
  mention.box.style.top = `${r.bottom + 4}px`;
  mention.box.innerHTML = mention.items.map((e, i) => `<div class="mi ${i === mention.sel ? "on" : ""}" data-mi="${i}">
      ${e.thumb ? `<img src="${media(e.thumb)}" alt="">` : `<span class="none"></span>`}
      <span><b>${esc(e.name)}</b><span class="hint">${({ perso: "Personnage", decor: "Décor", objet: "Objet", figurant: "Figurant" })[e.kind]} · @${esc(e.slug)}</span></span></div>`).join("")
    || `<div class="mi"><span class="hint">Rien de ce nom : crée le personnage (Personnages) ou l'élément (onglet Décors).</span></div>`;
  mention.box.hidden = false;
}
document.addEventListener("input", (ev) => {
  const ta = ev.target;
  if (!ta.matches || !ta.matches("textarea[data-mention], input[data-mention]")) return;
  if (ev.isTrusted === false && mention.ta === null) return;
  const before = ta.value.slice(0, ta.selectionStart);
  const m = before.match(/(^|[\s(])@([\p{L}0-9-]*)$/u);
  if (!m) { mentionClose(); return; }
  const q = normTxt(m[2]);
  const all = mentionables();
  mention.ta = ta; mention.start = before.length - m[2].length - 1; mention.sel = 0;
  mention.items = all.filter((e) => !q || e.slug.includes(q) || normTxt(e.name).includes(q)).slice(0, 8);
  mentionDraw();
});
document.addEventListener("keydown", (ev) => {
  if (!mention.ta || ev.target !== mention.ta || mention.box.hidden) return;
  if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
    ev.preventDefault();
    mention.sel = (mention.sel + (ev.key === "ArrowDown" ? 1 : -1) + mention.items.length) % Math.max(1, mention.items.length);
    mentionDraw();
  } else if (ev.key === "Enter" || ev.key === "Tab") {
    if (mention.items.length) { ev.preventDefault(); mentionInsert(mention.sel); }
  } else if (ev.key === "Escape") mentionClose();
}, true);
document.addEventListener("focusout", (ev) => { if (ev.target === mention.ta) setTimeout(mentionClose, 150); });

function compactNums(nums) {
  const out = []; let a = null, b = null;
  nums.forEach((n) => { if (a === null) { a = b = n; } else if (n === b + 1) b = n; else { out.push(a === b ? `${a}` : `${a}-${b}`); a = b = n; } });
  if (a !== null) out.push(a === b ? `${a}` : `${a}-${b}`);
  return out.join(", ");
}
