"use strict";

/* Régie Riot Machine — page unique, sans dépendance. */

const STATUS = {
  image_todo: ["Storyboard à faire", "work"],
  image_gen: ["Image en cours", "work"],
  image_qc: ["Contrôle de l'image", "work"],
  image_review: ["Image à valider", "review"],
  prompt_todo: ["Prompt vidéo à écrire", "work"],
  draft_gen: ["Draft en cours", "work"],
  draft_qc: ["Contrôle du draft", "work"],
  draft_review: ["Draft à valider", "review"],
  final_todo: ["Rendu final en cours", "work"],
  final_gen: ["Rendu final en cours", "work"],
  lipsync_todo: ["Lip-sync en cours", "work"],
  lipsync_gen: ["Lip-sync en cours", "work"],
  final_review: ["Final à valider", "review"],
  done: ["Validé", "done"],
  change_requested: ["Modif demandée", "change"],
  failed: ["En échec", "failed"],
};
const STAGE = {
  script: "Découpage en préparation",
  decoupage_review: "Découpage à valider",
  production: "En production",
  done: "Terminé",
};
const GATE_OF = { image_review: "images", draft_review: "drafts", final_review: "finals" };
const GATE_LABEL = { images: "les images", drafts: "les drafts", finals: "les finals" };
const APPROVE_ALL_LABEL = { images: "Valider toutes les images", drafts: "Valider tous les drafts", finals: "Valider tous les finals" };
const KIND_ORDER = { image: 0, draft: 1, final: 2, lipsync: 3 };
const KIND_LABEL = { image: "Image", draft: "Draft", final: "Final", lipsync: "Lip-sync" };
const CHAR_KINDS = ["canon", "turnaround", "fullbody", "expressions", "lighting", "details"];
const CHAR_KIND_LABEL = {
  canon: "Canon", turnaround: "Angles", fullbody: "Silhouette", expressions: "Expressions",
  lighting: "Lumières", details: "Détails",
};

const state = { route: "", data: null, filter: "review", picked: {}, refreshTimer: null, lastJson: "" };
const $view = document.getElementById("view");

/* ---------- utilitaires ---------- */

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const media = (p) => (p ? "/media/" + p.split("/").map(encodeURIComponent).join("/") : "");
const tc = (s) => {
  const m = Math.floor(s / 60);
  const r = (s - m * 60).toFixed(1).padStart(4, "0");
  return `${m}:${r}`;
};
const money = (n) => `${(n || 0).toFixed(2)} $`;
const isVideo = (p) => /\.(mp4|mov|webm)$/i.test(p || "");

function toast(msg, err = false) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "show" + (err ? " err" : "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.className = ""; }, err ? 5000 : 2500);
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
  if (!r.ok) throw new Error(body.detail || `Erreur ${r.status}`);
  return body;
}

function prefs(key, value) {
  try {
    if (value === undefined) return localStorage.getItem("riot:" + key);
    localStorage.setItem("riot:" + key, value);
  } catch (e) { /* stockage indisponible : sans conséquence */ }
  return null;
}

function statusBadge(status) {
  const [label, cls] = STATUS[status] || [status, ""];
  return `<span class="st ${cls}">${esc(label)}</span>`;
}

function colorClass(status) {
  const cls = (STATUS[status] || [0, "idle"])[1];
  return "c-" + (cls === "work" ? "work" : cls);
}

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

/* ---------- routeur ---------- */

function setNav(name) {
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === name));
}

async function router() {
  const hash = location.hash || "#/";
  state.route = hash;
  clearInterval(state.refreshTimer);
  state.lastJson = "";
  const [, page, arg] = hash.split("/");
  try {
    if (page === "clip" && arg) { setNav(""); await showClip(decodeURIComponent(arg)); }
    else if (page === "personnages" && arg) { setNav("personnages"); await showCharacter(decodeURIComponent(arg)); }
    else if (page === "personnages") { setNav("personnages"); await showCharacters(); }
    else if (page === "nouveau") { setNav("nouveau"); await showNewClip(); }
    else { setNav("clips"); await showHome(); }
  } catch (e) {
    $view.innerHTML = `<p class="empty">${esc(e.message)}</p>`;
  }
}
window.addEventListener("hashchange", router);

function autoRefresh(fn, ms = 15000) {
  clearInterval(state.refreshTimer);
  state.refreshTimer = setInterval(() => {
    if (document.hidden) return;
    const busy = document.querySelector(".feedback:not([hidden]) textarea, form.new")
      || [...document.querySelectorAll("video, audio")].some((m) => !m.paused);
    if (!busy) fn();
  }, ms);
}

/* ---------- accueil ---------- */

async function showHome() {
  const d = await api("/api/overview");
  const pending = d.clips.reduce((n, c) => n + c.to_review, 0);
  let html = `<h1>Clips</h1>
    <div class="meta"><span>${pending ? `<span class="count-review">${pending} validation(s) t'attendent</span>` : "Rien à valider pour l'instant"}</span>
    <span>${d.jobs_running} génération(s) en cours</span>
    ${d.fal_mode === "simulation" ? "<span>fal en mode simulation (aucune dépense)</span>" : ""}</div>`;
  if (!d.clips.length) {
    html += `<p class="empty" style="margin-top:28px">Aucun clip. <a href="#/nouveau">Démarre le premier</a> avec ton morceau et ton script.</p>`;
  } else {
    html += `<div class="clips">` + d.clips.map((c) => {
      const total = c.shots || 1;
      const segs = Object.entries(c.status_counts).map(([s, n]) =>
        `<i class="${colorClass(s)}" style="width:${(100 * n) / total}%"></i>`).join("");
      return `<a class="clip-row" href="#/clip/${encodeURIComponent(c.slug)}">
        <span><span class="title">${esc(c.title)}</span><br>
          <span class="meta"><span>${esc(STAGE[c.stage] || c.stage)}</span><span>${c.shots} plans</span></span></span>
        <span class="side">${c.to_review ? `<span class="count-review">${c.to_review} à valider</span><br>` : ""}
          ${money(c.cost_usd)}${c.budget_usd ? ` / ${c.budget_usd.toFixed(0)} $` : ""}</span>
        ${c.shots ? `<span class="mini-strip">${segs}</span>` : ""}
      </a>`;
    }).join("") + `</div>`;
  }
  $view.innerHTML = html;
  autoRefresh(showHome, 20000);
}

/* ---------- clip ---------- */

function currentKinds(shot) {
  const s = shot.status;
  if (s.startsWith("image") || s === "image_todo") return ["image"];
  if (s === "prompt_todo" || s.startsWith("draft")) return ["draft", "image"];
  return ["lipsync", "final", "draft", "image"];
}

function shotAssets(shot) {
  return shot.assets
    .filter((a) => a.path && a.status !== "generating" && a.status !== "failed")
    .sort((a, b) => (KIND_ORDER[a.kind] - KIND_ORDER[b.kind]) || (a.version - b.version));
}

function defaultAsset(shot) {
  const list = shotAssets(shot);
  for (const kind of currentKinds(shot)) {
    const ofKind = list.filter((a) => a.kind === kind && a.status !== "superseded" && a.status !== "rejected");
    if (ofKind.length) return ofKind[ofKind.length - 1];
  }
  for (const kind of currentKinds(shot)) {
    const ofKind = list.filter((a) => a.kind === kind);
    if (ofKind.length) return ofKind[ofKind.length - 1];
  }
  return null;
}

function renderMedia(asset, aspect, shotId, poster) {
  const cls = aspect === "9:16" ? "v916" : aspect === "1:1" ? "v11" : "";
  if (!asset) return `<div class="media ${cls}"><span class="none">Pas encore d'image</span></div>`;
  const src = media(asset.path);
  const inner = isVideo(asset.path)
    ? `<video src="${src}" controls playsinline preload="metadata" muted data-shot="${shotId}"${poster ? ` poster="${media(poster)}"` : ""}></video>`
    : `<img src="${src}" alt="Plan ${shotId}" loading="lazy" data-zoom="${src}">`;
  return `<div class="media ${cls}">${inner}</div>`;
}

function renderShot(shot, clip) {
  const picked = state.picked[shot.id];
  const assets = shotAssets(shot);
  const asset = assets.find((a) => a.id === picked) || defaultAsset(shot);
  const gate = GATE_OF[shot.status];
  const tags = [shot.framing, shot.motion && `mouvement ${shot.motion}`, shot.camera,
    shot.tier && `${shot.tier}${shot.model_key ? " · " + shot.model_key : ""}`,
    shot.singing ? "chanté" : null, ...(shot.characters || [])].filter(Boolean);
  const lastReview = (shot.reviews || []).find((r) => r.decision === "change");
  const versions = assets.map((a) => {
    const cls = [a.id === asset?.id ? "on" : "", a.status].join(" ");
    return `<button class="${cls}" data-pick="${shot.id}:${a.id}">${KIND_LABEL[a.kind]} v${a.version}</button>`;
  }).join("");
  const prompt = shot.video_prompt || shot.image_prompt;
  return `<article class="shot ${gate ? "is-review" : ""}" id="shot-${shot.id}" data-shot="${shot.id}">
    <div>
      ${renderMedia(asset, clip.aspect_ratio, shot.id, (assets.filter((a) => a.kind === "image").pop() || {}).path)}
      ${versions ? `<div class="versions">${versions}</div>` : ""}
    </div>
    <div class="info">
      <div class="head"><span class="num">${shot.num}</span>
        <span class="tc">${tc(shot.t_start)} → ${tc(shot.t_end)} · ${(shot.t_end - shot.t_start).toFixed(1)} s${shot.section ? " · " + esc(shot.section) : ""}</span>
        ${statusBadge(shot.status)}</div>
      <p class="desc">${esc(shot.description)}</p>
      <div class="tags">${tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      ${shot.notes ? `<p class="note ${shot.notes.startsWith("Retour de Michael") ? "from-michael" : ""}">${esc(shot.notes)}</p>` : ""}
      ${lastReview && !shot.notes ? `<p class="note from-michael">Ton dernier retour : ${esc(lastReview.comment)}</p>` : ""}
      ${prompt ? `<details class="prompt"><summary>Prompt${shot.video_prompt ? " vidéo" : " image"}</summary><p>${esc(prompt)}</p></details>` : ""}
      <div class="actions">
        <div class="row">
          <button class="btn small ghost" data-play="${shot.id}">Lire dans le morceau</button>
          ${shot.status === "failed" ? `<button class="btn small" data-retry="${shot.id}">Relancer</button>` : ""}
          <span class="hint">${money(shot.cost_usd)}</span>
        </div>
        ${gate ? `<div class="row">
            <button class="btn go" data-approve="${shot.id}">Valider ${gate === "images" ? "l'image" : gate === "drafts" ? "le draft" : "le final"}</button>
            <button class="btn" data-change="${shot.id}">Demander une modif</button>
          </div>
          <div class="feedback" id="fb-${shot.id}" hidden>
            <textarea placeholder="Ce qui ne va pas et ce que tu veux à la place (cadrage, geste, lumière, tenue…)"></textarea>
            <div class="row"><button class="btn go" data-send="${shot.id}">Envoyer le retour</button>
              <button class="btn ghost" data-cancel="${shot.id}">Annuler</button></div>
          </div>` : ""}
      </div>
    </div>
  </article>`;
}

function renderStrip(clip) {
  const shots = clip.shots;
  if (!shots.length) return "";
  const start = shots[0].t_start;
  const total = Math.max(0.1, shots[shots.length - 1].t_end - start);
  const segs = shots.map((s) => `<span class="seg ${colorClass(s.status)}" data-seek="${s.id}"
      style="width:${(100 * (s.t_end - s.t_start)) / total}%" title="Plan ${s.num} · ${esc((STATUS[s.status] || [s.status])[0])}">${s.num}</span>`).join("");
  return `<div class="strip" id="strip" data-start="${start}" data-total="${total}">${segs}<span class="head" id="head"></span></div>
    <div class="strip-legend"><span><b class="c-review"></b>à valider</span><span><b class="c-work"></b>en production</span>
      <span><b class="c-change"></b>modif demandée</span><span><b class="c-done"></b>validé</span><span><b class="c-failed"></b>échec</span></div>`;
}

function renderDecoupage(clip) {
  const rows = clip.shots.map((s) => `<tr><td>${s.num}</td><td>${tc(s.t_start)}–${tc(s.t_end)}</td>
    <td>${esc(s.section || "")}</td><td>${esc(s.description)}</td>
    <td>${esc([s.framing, s.motion, s.singing ? "chanté" : ""].filter(Boolean).join(" · "))}</td></tr>`).join("");
  return `<section class="gate">
    <h2>Découpage à valider</h2>
    <p class="hint">${clip.shots.length} plans proposés par le script doctor. Valide pour lancer le storyboard, ou explique ce qu'il faut changer.</p>
    ${clip.script_notes ? `<details><summary>Notes de relecture du script doctor</summary><div class="notes-doc">${esc(clip.script_notes)}</div></details>` : ""}
    <div style="overflow-x:auto;margin-top:12px"><table class="cut"><thead><tr><th>#</th><th>Temps</th><th>Partie</th><th>Ce qu'on voit</th><th>Plan</th></tr></thead><tbody>${rows}</tbody></table></div>
    <div class="row" style="margin-top:14px"><button class="btn go" data-cut="approve">Valider le découpage</button>
      <button class="btn" data-cut="open">Demander des changements</button></div>
    <div class="feedback" id="fb-cut" hidden style="margin-top:10px">
      <textarea placeholder="Ex. : le refrain doit commencer sur un plan large, fusionner les plans 4 et 5, ajouter un plan de foule…"></textarea>
      <div class="row"><button class="btn go" data-cut="change">Envoyer</button></div>
    </div>
  </section>`;
}

async function showClip(slug, keepScroll = false) {
  const clip = await api(`/api/clips/${encodeURIComponent(slug)}`);
  const json = JSON.stringify(clip);
  if (keepScroll && json === state.lastJson) return;
  state.lastJson = json;
  state.data = clip;
  const savedFilter = prefs("filter:" + slug);
  if (!keepScroll && savedFilter) state.filter = savedFilter;
  const scroll = window.scrollY;
  const counts = clip.status_counts || {};
  const toReview = Object.keys(GATE_OF).reduce((n, s) => n + (counts[s] || 0), 0);
  if (!keepScroll && state.filter === "review" && !toReview && clip.stage !== "decoupage_review") state.filter = "all";

  const filters = [
    ["review", `À valider (${toReview})`, (s) => GATE_OF[s.status]],
    ["work", "En production", (s) => (STATUS[s.status] || [0, ""])[1] === "work"],
    ["change", "Retours & échecs", (s) => ["change_requested", "failed"].includes(s.status)],
    ["done", "Validés", (s) => s.status === "done"],
    ["all", "Tous", () => true],
  ];
  const active = filters.find((f) => f[0] === state.filter) || filters[4];
  const visible = clip.stage === "decoupage_review" || clip.stage === "script" ? [] : clip.shots.filter(active[2]);
  const gatesOpen = [...new Set(clip.shots.map((s) => GATE_OF[s.status]).filter(Boolean))];

  let html = `<h1>${esc(clip.title)}</h1>
    <div class="meta"><span>${esc(STAGE[clip.stage] || clip.stage)}</span><span>${clip.shots.length} plans</span>
      <span>${money(clip.cost_usd)}${clip.budget_usd ? ` sur ${clip.budget_usd.toFixed(0)} $ <button class="btn small ghost" data-budget>modifier</button>` : ""}</span>
      <span>${esc(clip.aspect_ratio)}</span>${clip.casting.map((c) => `<span>${esc(c.name)} v${c.version}${c.look_slug ? " · " + esc(c.look_slug) : ""}</span>`).join("")}</div>
    <div class="player">
      ${clip.song_path ? `<audio id="song" src="${media(clip.song_path)}" controls preload="metadata"></audio>` : `<p class="hint">Pas de morceau.</p>`}
      ${renderStrip(clip)}
    </div>`;

  if (clip.stage === "script") {
    html += `<p class="empty" style="margin-top:24px">Le script doctor prépare le découpage. Tu recevras une notification quand il sera prêt.</p>`;
    if (clip.script) html += `<details style="margin-top:12px"><summary>Ton script</summary><div class="notes-doc">${esc(clip.script)}</div></details>`;
  } else if (clip.stage === "decoupage_review") {
    html += renderDecoupage(clip);
  } else {
    html += `<div class="filters">${filters.map(([k, label]) =>
      `<button class="chip ${k === active[0] ? "on" : ""}" data-filter="${k}">${label}</button>`).join("")}
      <span class="spacer"></span>
      ${state.filter === "review" ? gatesOpen.map((g) => `<button class="btn small" data-approve-all="${g}">${APPROVE_ALL_LABEL[g]}</button>`).join("") : ""}
      <button class="btn small" data-assemble>Monter le clip</button>
      ${clip.montages.length ? `<a class="btn small ghost" href="${media(clip.montages[0])}" target="_blank" rel="noopener">Dernier montage</a>` : ""}
    </div>`;
    html += visible.length
      ? `<div class="shots">${visible.map((s) => renderShot(s, clip)).join("")}</div>`
      : `<p class="empty">${state.filter === "review" ? "Rien à valider : les agents travaillent, tu seras prévenu." : "Aucun plan ici."}</p>`;
  }
  if (clip.events.length) {
    html += `<h2>Journal</h2><div class="hint">${clip.events.slice(0, 8).map((e) =>
      `${esc(e.created_at.replace("T", " ").slice(0, 16))} — ${esc(e.message)}`).join("<br>")}</div>`;
  }
  $view.innerHTML = html;
  bindClip(clip);
  if (keepScroll) window.scrollTo(0, scroll);
  autoRefresh(() => showClip(slug, true));
}

let stopAt = null;

function bindClip(clip) {
  const song = document.getElementById("song");
  const strip = document.getElementById("strip");
  const head = document.getElementById("head");
  if (song && strip) {
    const start = parseFloat(strip.dataset.start);
    const total = parseFloat(strip.dataset.total);
    song.addEventListener("timeupdate", () => {
      head.style.left = `${Math.min(100, Math.max(0, (100 * (song.currentTime - start)) / total))}%`;
      if (stopAt && song.currentTime >= stopAt.end) {
        song.pause();
        stopAt.video?.pause();
        stopAt = null;
      }
    });
  }

  $view.onclick = async (ev) => {
    const t = ev.target.closest("button, [data-seek], [data-zoom]");
    if (!t) return;
    const d = t.dataset;
    try {
      if (d.zoom) return lightbox(d.zoom);
      if (d.filter) {
        state.filter = d.filter;
        prefs("filter:" + clip.slug, d.filter);
        return showClip(clip.slug);
      }
      if (d.seek) {
        const shot = clip.shots.find((s) => s.id === +d.seek);
        if (song) { song.currentTime = shot.t_start; }
        document.getElementById("shot-" + shot.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      if (d.pick) {
        const [sid, aid] = d.pick.split(":").map(Number);
        state.picked[sid] = aid;
        const shot = clip.shots.find((s) => s.id === sid);
        const node = document.getElementById("shot-" + sid);
        node.outerHTML = renderShot(shot, clip);
        return;
      }
      if (d.play) return playInSong(clip, +d.play);
      if (d.change) {
        const fb = document.getElementById("fb-" + d.change);
        fb.hidden = false;
        fb.querySelector("textarea").focus();
        return;
      }
      if (d.cancel) { document.getElementById("fb-" + d.cancel).hidden = true; return; }
      if (d.approve) {
        const sid = +d.approve;
        const shot = clip.shots.find((s) => s.id === sid);
        const pickedId = state.picked[sid];
        const assetId = pickedId && GATE_OF[shot.status] !== "finals" ? pickedId : null;
        t.disabled = true;
        await api(`/api/shots/${sid}/review`, { json: { decision: "approve", asset_id: assetId } });
        toast(`Plan ${shot.num} validé`);
        return showClip(clip.slug, false);
      }
      if (d.send) {
        const sid = +d.send;
        const text = document.querySelector(`#fb-${sid} textarea`).value.trim();
        if (!text) { toast("Explique la modification souhaitée", true); return; }
        t.disabled = true;
        await api(`/api/shots/${sid}/review`, { json: { decision: "change", comment: text, asset_id: state.picked[sid] || null } });
        toast("Retour envoyé à l'orchestrateur");
        return showClip(clip.slug, false);
      }
      if (d.approveAll) {
        if (!confirm(`${APPROVE_ALL_LABEL[d.approveAll]} en attente ?`)) return;
        const r = await api(`/api/clips/${encodeURIComponent(clip.slug)}/approve-all/${d.approveAll}`, { method: "POST" });
        toast(`${r.approved} plan(s) validé(s)`);
        return showClip(clip.slug, false);
      }
      if (d.cut === "open") { const fb = document.getElementById("fb-cut"); fb.hidden = false; fb.querySelector("textarea").focus(); return; }
      if (d.cut === "approve" || d.cut === "change") {
        const comment = d.cut === "change" ? document.querySelector("#fb-cut textarea").value.trim() : "";
        if (d.cut === "change" && !comment) { toast("Explique les changements voulus", true); return; }
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/decoupage`, { json: { decision: d.cut, comment } });
        toast(d.cut === "approve" ? "Découpage validé : le storyboard démarre" : "Retour envoyé au script doctor");
        return showClip(clip.slug, false);
      }
      if (d.retry !== undefined && d.retry !== "") {
        await api(`/api/shots/${d.retry}/retry`, { method: "POST" });
        toast("Plan relancé");
        return showClip(clip.slug, false);
      }
      if (d.assemble !== undefined) {
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/assemble`, { method: "POST" });
        toast("Montage lancé, il apparaîtra dans une à deux minutes");
        return;
      }
      if (d.budget !== undefined) {
        const v = prompt("Nouveau budget du clip, en dollars :", clip.budget_usd || "");
        if (v === null) return;
        await api(`/api/clips/${encodeURIComponent(clip.slug)}/budget`, { json: { budget_usd: parseFloat(v) } });
        return showClip(clip.slug, false);
      }
    } catch (e) {
      t.disabled = false;
      toast(e.message, true);
    }
  };
}

function playInSong(clip, shotId) {
  const shot = clip.shots.find((s) => s.id === shotId);
  const song = document.getElementById("song");
  const video = document.querySelector(`#shot-${shotId} video`);
  document.querySelectorAll("video").forEach((v) => { if (v !== video) v.pause(); });
  if (song) {
    song.currentTime = shot.t_start;
    song.play().catch(() => {});
  }
  if (video) {
    video.muted = true;
    video.currentTime = 0;
    video.play().catch(() => {});
  }
  stopAt = { end: shot.t_end, video };
}

/* ---------- personnages ---------- */

async function showCharacters() {
  const d = await api("/api/overview");
  $view.innerHTML = `<h1>Personnages</h1>
    <p class="hint">Le référentiel : chaque personnage a des versions. Seule une version validée peut être castée dans un clip.
    Pour créer ou faire évoluer un personnage, lance <b>/casting &lt;nom&gt;</b> dans Claude Code.</p>
    <div class="cast">${d.characters.map((c) => `<a href="#/personnages/${encodeURIComponent(c.slug)}">
      ${c.canon_path ? `<img src="${media(c.canon_path)}" alt="${esc(c.name)}">` : ""}
      <div class="cap"><b>${esc(c.name)}</b><br><span class="hint">canon v${c.canon_version || "–"}</span>
      ${c.to_review ? `<br><span class="count-review">${c.to_review} image(s) à trier</span>` : ""}</div></a>`).join("")}</div>`;
  autoRefresh(showCharacters, 30000);
}

async function showCharacter(slug, keepScroll = false) {
  const ch = await api(`/api/characters/${encodeURIComponent(slug)}`);
  const json = JSON.stringify(ch);
  if (keepScroll && json === state.lastJson) return;
  state.lastJson = json;
  const scroll = window.scrollY;
  const versions = ch.versions.map((v) => {
    const canon = v.assets.filter((a) => a.kind === "canon" && a.status === "kept").pop();
    const labelSt = { draft: ["brouillon", "work"], validated: ["validée", "done"], archived: ["archivée", ""] }[v.status];
    const isCanon = ch.canon_version === v.version;
    const kinds = CHAR_KINDS.map((k) => {
      const list = v.assets.filter((a) => a.kind === k && a.path && a.status !== "generating" && !(k === "canon" && a === canon));
      if (!list.length) return "";
      return `<div class="kind"><h3>${CHAR_KIND_LABEL[k]}</h3><div class="assets">${list.map((a) => `
        <div class="asset ${a.status}">
          <img src="${media(a.path)}" alt="${esc(a.label || k)}" loading="lazy" data-zoom="${media(a.path)}">
          ${a.status === "proposed" && v.status === "draft" ? `<div class="row">
            <button class="btn small go" data-pick-asset="${a.id}:keep">Garder</button>
            <button class="btn small" data-pick-asset="${a.id}:reject">Rejeter</button>
            <button class="btn small ghost" data-pick-asset="${a.id}:canon">Canon</button></div>`
            : `<div class="row hint">${esc(a.label || "")}${a.status === "rejected" ? " · rejetée" : ""}</div>`}
        </div>`).join("")}</div></div>`;
    }).join("");
    const generating = v.assets.filter((a) => a.status === "generating").length;
    return `<section class="version">
      <div class="version-head"><h2 style="margin:0">Version ${v.version}</h2>
        <span class="row"><span class="st ${labelSt[1]}">${labelSt[0]}</span>${isCanon ? `<span class="st done">canon actuelle</span>` : ""}
        ${generating ? `<span class="st work">${generating} en génération</span>` : ""}
        ${v.status === "draft" ? `<button class="btn go small" data-validate="${v.version}" ${canon ? "" : "disabled title=\"Choisis d'abord une image canon\""}>Valider cette version</button>` : ""}</span></div>
      <div class="version-body">
        <div class="canon">${canon ? `<img src="${media(canon.path)}" alt="Canon" data-zoom="${media(canon.path)}">` : `<p class="hint">Pas encore de canon : choisis-en une parmi les propositions.</p>`}
          ${v.adn ? `<details><summary class="hint">ADN</summary><pre class="adn">${esc(v.adn)}</pre></details>` : ""}</div>
        <div>${kinds || `<p class="hint">Aucune autre image dans cette version.</p>`}</div>
      </div></section>`;
  }).join("");
  $view.innerHTML = `<h1>${esc(ch.name)}</h1>
    <div class="meta"><span>canon v${ch.canon_version || "–"}</span>
      <span>${ch.clips.length ? "Clips : " + ch.clips.map((c) => `${esc(c.clip_slug)} (v${c.version})`).join(", ") : "Dans aucun clip"}</span>
      ${ch.looks.length ? `<span>Looks : ${ch.looks.map((l) => esc(l.slug)).join(", ")}</span>` : ""}</div>
    ${versions}`;
  if (keepScroll) window.scrollTo(0, scroll);

  $view.onclick = async (ev) => {
    const t = ev.target.closest("button, [data-zoom]");
    if (!t) return;
    try {
      if (t.dataset.zoom) return lightbox(t.dataset.zoom);
      if (t.dataset.pickAsset) {
        const [id, decision] = t.dataset.pickAsset.split(":");
        await api(`/api/character-assets/${id}`, { json: { decision } });
        toast({ keep: "Image gardée", reject: "Image rejetée", canon: "Nouvelle canon de la version" }[decision]);
        return showCharacter(slug);
      }
      if (t.dataset.validate) {
        if (!confirm(`Valider la version ${t.dataset.validate} ? Elle devient la canon de ${ch.name} pour les prochains clips.`)) return;
        await api(`/api/characters/${encodeURIComponent(slug)}/versions/${t.dataset.validate}/validate`, { method: "POST" });
        toast("Version validée");
        return showCharacter(slug);
      }
    } catch (e) { toast(e.message, true); }
  };
  autoRefresh(() => showCharacter(slug, true), 20000);
}

/* ---------- nouveau clip ---------- */

async function showNewClip() {
  const d = await api("/api/overview");
  const castable = d.characters.filter((c) => c.canon_version);
  $view.innerHTML = `<h1>Nouveau clip</h1>
    <p class="hint">Dépose le morceau et ton script : le script doctor propose un découpage, tu le valides, la production démarre.</p>
    <form class="new">
      <label>Titre<input type="text" name="title" required placeholder="Titre du morceau"></label>
      <label>Morceau (mp3 ou wav exporté de Suno)<input type="file" name="song" accept="audio/*" required></label>
      <label>Piste voix isolée (stem « vocals » de Suno, pour le lip-sync)<input type="file" name="vocals" accept="audio/*"></label>
      <label>Script, intentions de réalisation, paroles<textarea name="script" rows="10" placeholder="L'histoire du clip, l'ambiance, les décors, et les paroles avec leurs passages (couplet, refrain…)"></textarea></label>
      <div><span class="hint">Personnages</span><div class="checks">${castable.map((c, i) =>
        `<label><input type="checkbox" name="characters" value="${esc(c.slug)}" ${i === 0 ? "checked" : ""}> ${esc(c.name)}</label>`).join("")}</div></div>
      <div class="two">
        <label>Format<select name="aspect"><option value="16:9">16:9 — YouTube</option><option value="9:16">9:16 — Reels, TikTok</option><option value="1:1">1:1</option></select></label>
        <label>Budget ($)<input type="number" name="budget" min="1" step="1" value="80"></label>
        <label>BPM (facultatif)<input type="number" name="bpm" min="40" max="220" step="0.1"></label>
      </div>
      <div class="row"><button class="btn go" type="submit">Créer le clip</button><span class="hint" id="up"></span></div>
    </form>`;
  const form = $view.querySelector("form");
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(form);
    const chars = fd.getAll("characters");
    fd.delete("characters");
    fd.set("characters", chars.join(","));
    if (!fd.get("bpm")) fd.delete("bpm");
    if (!fd.get("vocals")?.size) fd.delete("vocals");
    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    document.getElementById("up").textContent = "Envoi des fichiers…";
    try {
      const r = await api("/api/clips", { method: "POST", body: fd });
      toast("Clip créé : le script doctor démarre");
      location.hash = `#/clip/${encodeURIComponent(r.slug)}`;
    } catch (e) {
      btn.disabled = false;
      document.getElementById("up").textContent = "";
      toast(e.message, true);
    }
  };
}

router();
