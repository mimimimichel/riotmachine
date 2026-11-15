/* Riot Machine v3 : pages ajoutées à la régie (chargé après app.js, dont il reprend
   api, esc, money, toast, $view, setNav). */

/* ---------- Consommation de Claude (R-T1, R-T4) ---------- */

const CMD_LABEL = { "/prod": "production d'un clip", "/casting": "casting d'un personnage" };
const tok = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)} M` : n >= 1e3 ? `${Math.round(n / 1e3)} k` : String(n || 0));

async function showConso() {
  const d = await api("/api/conso");
  const left = Math.max(0, d.day_cap_usd - d.spent_today_usd);
  const pend = d.pending.filter((r) => r.status === "pending");
  const queued = d.pending.filter((r) => r.status === "approved");
  const estText = (r) => (r.est_usd != null ? `~${money(r.est_usd)}` : `au plus ${money(d.run_cap_usd)}`);
  const card = (r) => `
    <div class="spend-item">
      <div class="row"><b>${esc(r.key)}</b><span class="hint">${esc(CMD_LABEL[r.command.split(" ")[0]] || r.command)}</span>
        <span class="spacer"></span><span class="spend-cost">${estText(r)}</span></div>
      <ul class="hint">${r.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      <div class="row">
        <button class="btn small go" data-agent="${r.id}" data-ok="1">Lancer · ${estText(r)}</button>
        <button class="btn small" data-agent="${r.id}" data-ok="0">Pas maintenant</button>
      </div>
    </div>`;
  const runs = d.runs.slice(0, 15).map((r) => `<tr>
      <td>${esc((r.started_at || "").slice(5, 16).replace("T", " "))}</td><td>${esc(r.key)}</td>
      <td>${r.cost_usd != null ? money(r.cost_usd) : r.ended_at ? "—" : "en cours"}</td>
      <td>${r.turns ?? ""}</td><td>${tok(r.tokens_in)} / ${tok(r.tokens_out)}</td>
      <td>${esc(r.requested_by === "michael" ? "toi" : r.requested_by === "code:auto" ? "auto" : r.requested_by || "ancien réveil")}</td></tr>`).join("");
  const days = {};
  for (const u of d.usage) (days[u.day] = days[u.day] || []).push(u);
  const usage = Object.entries(days).slice(0, 10).map(([day, us]) => `<tr><td>${esc(day.slice(5))}</td>
      <td>${us.reduce((a, u) => a + u.runs, 0)}</td><td>${us.some((u) => u.cost_usd != null) ? money(us.reduce((a, u) => a + (u.cost_usd || 0), 0)) : "non mesuré"}</td>
      <td>${tok(us.reduce((a, u) => a + u.tokens_in, 0))} / ${tok(us.reduce((a, u) => a + u.tokens_out, 0))}</td></tr>`).join("");
  $view.innerHTML = `
    <div class="pagehead"><h1>Consommation de Claude</h1></div>
    <div class="stack">
      <p class="hint">Aucun agent ne part tout seul. Quand un clip ou un personnage a besoin d'un agent, la demande arrive ici avec ses raisons et son coût estimé.
        Le coût est mesuré à chaque passage. Sur l'abonnement, c'est un équivalent API : il te donne la mesure, pas une facture.</p>
      <section class="panel stack">
        <div class="row"><h2>Aujourd'hui</h2><span class="spacer"></span>
          <span class="spend-cost">${money(d.spent_today_usd)} sur ${money(d.day_cap_usd)}</span></div>
        <div class="row">
          <label>Mode
            <select id="c-mode">
              <option value="accord" ${d.mode === "accord" ? "selected" : ""}>Sur ton accord, passage par passage</option>
              <option value="auto" ${d.mode === "auto" ? "selected" : ""}>Automatique tant que le plafond du jour n'est pas atteint</option>
            </select></label>
        </div>
        <div class="row">
          <label>Plafond du jour ($) <input id="c-day" type="number" min="0" step="0.5" value="${d.day_cap_usd}" style="width:6em"></label>
          <label>Plafond d'un passage ($) <input id="c-run" type="number" min="0" step="0.1" value="${d.run_cap_usd}" style="width:6em"></label>
          <button class="btn small" id="c-save">Enregistrer</button>
        </div>
        <p class="hint">Un passage qui atteint son plafond s'arrête net et te prévient. En mode automatique, il reste ${money(left)} aujourd'hui.</p>
      </section>
      <section class="panel stack">
        <h2>En attente de ton accord</h2>
        ${pend.length ? pend.map(card).join("") : `<p class="empty">Aucune demande.</p>`}
        ${queued.length ? `<p class="hint">Accordé, part au prochain tour du worker : ${queued.map((r) => esc(r.key)).join(", ")}</p>` : ""}
        ${d.running.length ? `<p class="hint">Au travail : ${d.running.map(esc).join(", ")}</p>` : ""}
      </section>
      <section class="panel"><h2>Derniers passages</h2>
        <div style="overflow-x:auto"><table class="mono small-table"><tr><th>Quand</th><th>Pour</th><th>Coût</th><th>Tours</th><th>Jetons entrée / sortie</th><th>Lancé par</th></tr>${runs}</table></div></section>
      <section class="panel"><h2>Par jour</h2>
        <div style="overflow-x:auto"><table class="mono small-table"><tr><th>Jour</th><th>Passages</th><th>Coût</th><th>Jetons</th></tr>${usage}</table></div></section>
    </div>`;
  $view.querySelectorAll("[data-agent]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    try {
      await api(`/api/conso/${b.dataset.agent}/decide`, { json: { approve: b.dataset.ok === "1" } });
      toast(b.dataset.ok === "1" ? "Accordé : l'agent part dans la minute" : "Demande écartée");
      refreshSys();
      await showConso();
    } catch (e) { toast(e.message, "err"); b.disabled = false; }
  }));
  document.getElementById("c-save").addEventListener("click", async () => {
    try {
      await api("/api/conso/settings", { json: { mode: document.getElementById("c-mode").value,
        day_cap_usd: +document.getElementById("c-day").value, run_cap_usd: +document.getElementById("c-run").value } });
      toast("Réglages enregistrés");
      await showConso();
    } catch (e) { toast(e.message, "err"); }
  });
}

/* ---------- Tournage par séquence (v3) ----------
   #/clip/<slug>/tournage            : les séquences du clip (étiquette indicative par séquence)
   #/clip/<slug>/tournage/s/<id>     : plan de tournage d'une séquence (offre, options et leur impact, prises, accord)
   #/clip/<slug>/tournage/d/<id>     : dérushage d'une séquence, plan par plan                                     */

const FORM_LABEL = { single: "un plan", multi: "multi-plans", continuous: "prise continue" };
const REF_STATUS = { accepted: ["acceptée", "done"], untested: ["non testée", "wait"], refused_in: ["refusée à l'entrée", "failed"],
  refused_out: ["vidéo refusée en sortie", "failed"] };
const JEU_LABEL = { aucun: "aucun", present: "présent", porteur: "porte le plan" };
const usd = (n) => `${(n || 0).toFixed(2).replace(".", ",")} $`;
const secs = (n) => `${(+n).toFixed(1).replace(".", ",")} s`;

function tournageRoute() {
  const p = (location.hash || "").slice(2).split("/").map(decodeURIComponent);
  return { sub: p[3] || "", id: p[4] ? +p[4] : null };
}

async function loadTournage(clip) {
  const box = document.getElementById("tournage-tab");
  if (!box) return;
  const r = tournageRoute();
  try {
    if (r.sub === "s" && r.id) await renderSequence(box, clip, r.id);
    else if (r.sub === "d" && r.id && typeof renderDerush === "function") await renderDerush(box, clip, r.id);
    else await renderSequences(box, clip);
  } catch (e) { box.innerHTML = `<p class="empty">${esc(e.message)}</p>`; }
}

function impactList(lines) {
  return lines && lines.length ? `<ul class="impact">${lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>` : "";
}

async function renderSequences(box, clip) {
  const d = await api(`/api/clips/${encodeURIComponent(clip.slug)}/sequences`);
  const base = `#/clip/${encodeURIComponent(clip.slug)}/tournage`;
  const res = Object.values(d.reserves || {}).map((r) => `${esc(r.label)} : ${usd(r.remaining)} restants${r.expires_soon ? " ⚠ expire bientôt" : ""}`).join(" · ");
  const opts = d.sequences.map((s) => `<option value="${s.id}">${s.num}. ${esc(s.name)}</option>`).join("");
  box.innerHTML = `
    <div class="stack">
      <p class="hint">Une séquence réunit les plans tournés au même endroit, au même moment, dans la même tenue. La machine calcule pour chacune
        comment elle la tournerait, avec quel modèle et pour combien. Rien ne part sans ton accord sur la page de la séquence.
        Seuls les plans des blocs validés se tournent.</p>
      <div class="row"><label>Qualité du clip
        <select id="t-quality"><option value="brouillon" ${d.quality === "brouillon" ? "selected" : ""}>Brouillon (résolution la plus basse)</option>
        <option value="final" ${d.quality === "final" ? "selected" : ""}>Final (1080p ou plus)</option></select></label>
        ${res ? `<span class="mono hint">${res}</span>` : ""}</div>
      ${d.sequences.map((s) => `
        <section class="panel stack seqcard" data-seq="${s.id}">
          <div class="row"><h2>${s.num}. ${esc(s.name)}</h2><span class="spacer"></span>
            <a class="btn small go" href="${base}/s/${s.id}">Plan de tournage</a></div>
          <p class="mono seqbadge ${s.blocking ? "warn" : ""}">${esc(s.badge)}</p>
          ${s.waiting_blocks.length ? `<p class="hint">Plans des blocs ${s.waiting_blocks.join(", ")} : attendent la validation de leur bloc.</p>` : ""}
          <ul class="seqshots">${s.shots.map((x) => `<li class="${x.shootable ? "" : "dim"}">
              <label><input type="checkbox" data-pick="${x.id}"> <b>${x.num}</b> <span class="mono">${tc(x.t_start)}–${tc(x.t_end)}</span>
              ${esc((x.description || "").slice(0, 110))}${(x.description || "").length > 110 ? "…" : ""}</label></li>`).join("")}</ul>
        </section>`).join("")}
      ${d.loose_shots.length ? `<section class="panel"><h2>Plans sans séquence</h2><ul class="seqshots">${d.loose_shots.map((x) => `<li>
          <label><input type="checkbox" data-pick="${x.id}"> <b>${x.num}</b> ${esc((x.description || "").slice(0, 110))}</label></li>`).join("")}</ul></section>` : ""}
      <section class="panel stack" id="t-pickbar">
        <h2>Regrouper les plans cochés</h2>
        <div class="row"><input id="t-newname" placeholder="Nom de la nouvelle séquence (ex. « Chambre, le réveil »)" style="flex:1;min-width:12em">
          <button class="btn small go" id="t-new">Nouvelle séquence</button></div>
        <div class="row"><select id="t-dest">${opts}</select><button class="btn small" id="t-move">Déplacer vers cette séquence</button></div>
        <p class="hint">Couper une séquence ne coûte rien : la machine recalcule les prises et le coût tout de suite.</p>
      </section>
    </div>`;
  const picked = () => [...box.querySelectorAll("[data-pick]:checked")].map((c) => +c.dataset.pick);
  box.querySelector("#t-quality").addEventListener("change", async (e) => {
    try { await api(`/api/clips/${encodeURIComponent(clip.slug)}/quality`, { json: { quality: e.target.value } }); toast("Qualité changée : coûts recalculés"); renderSequences(box, clip); }
    catch (err) { toast(err.message, "err"); }
  });
  box.querySelector("#t-new").addEventListener("click", async () => {
    const ids = picked();
    if (!ids.length) { toast("Coche d'abord les plans à regrouper", "err"); return; }
    try { await api(`/api/clips/${encodeURIComponent(clip.slug)}/sequences`, { json: { name: box.querySelector("#t-newname").value, shot_ids: ids } });
      toast("Séquence créée"); renderSequences(box, clip); } catch (err) { toast(err.message, "err"); }
  });
  box.querySelector("#t-move").addEventListener("click", async () => {
    const ids = picked();
    if (!ids.length) { toast("Coche d'abord les plans à déplacer", "err"); return; }
    try { await api(`/api/sequences/${box.querySelector("#t-dest").value}/shots`, { json: { shot_ids: ids } });
      toast("Plans déplacés"); renderSequences(box, clip); } catch (err) { toast(err.message, "err"); }
  });
}

function refChip(r, sel) {
  const [lab, cls] = REF_STATUS[r.status] || [r.status, "wait"];
  return `<label class="refchip ${sel ? "on" : ""}" title="${esc(r.label)} · ${esc(lab)}">
      <input type="checkbox" data-ref="${esc(r.path)}" ${sel ? "checked" : ""} ${r.status.startsWith("refused") ? "disabled" : ""}>
      <img src="${media(r.path)}" alt="" loading="lazy"><span>${esc(r.label)}</span>${pill(lab, cls)}</label>`;
}

async function renderSequence(box, clip, id) {
  const v = await api(`/api/sequences/${id}`);
  const s = v.sequence, p = v.plan;
  const base = `#/clip/${encodeURIComponent(clip.slug)}/tournage`;
  const save = async (json, msg) => {
    try { await api(`/api/sequences/${id}`, { json }); toast(msg || "Enregistré"); await renderSequence(box, clip, id); }
    catch (e) { toast(e.message, "err"); }
  };
  if (!p) { box.innerHTML = `<p class="empty">Aucune offre ne peut tourner cette séquence.</p>`; return; }
  const shootable = v.shots.filter((x) => x.shootable);
  const optImp = v.option_impacts || { mode: {}, resolution: {} };
  const modeOpts = v.options.modes.map((m) => `<option value="${m.key}" ${m.key === p.mode ? "selected" : ""}>${esc(m.label)} (${(m.durations || []).join(", ")} s)${optImp.mode[m.key] ? ` · ${usd(optImp.mode[m.key].total_usd)}` : ` · ${usd(p.total_usd)}`}</option>`).join("");
  const resOpts = v.options.resolutions.map((r) => `<option value="${r.key}" ${r.key === p.resolution ? "selected" : ""}>${esc(r.key)} · ${usd(r.price_per_s)}/s${optImp.resolution[r.key] ? ` · ${usd(optImp.resolution[r.key].total_usd)}` : ` · ${usd(p.total_usd)}`}</option>`).join("");
  const looks = v.looks || {};
  const shotRow = (x) => {
    const chars = (x.characters || []);
    const lookSel = chars.filter((c) => (looks[c] || []).length).map((c) => `<label>Tenue de ${esc(c)}
        <select data-look="${x.id}" data-char="${esc(c)}"><option value="">aucune</option>${looks[c].map((l) => `<option value="${esc(l.slug)}" ${x.looks && x.looks[c] === l.slug ? "selected" : ""}>${esc(l.name)}</option>`).join("")}</select></label>`).join("");
    return `<details class="shotv3" ${x.traps && x.traps.length ? "open" : ""}><summary><b>Plan ${x.num}</b> <span class="mono">${tc(x.t_start)}–${tc(x.t_end)} · ${secs(x.t_end - x.t_start)}</span>
        ${x.shootable ? "" : `<span class="hint">bloc ${x.block_num} pas encore validé</span>`}
        ${x.traps && x.traps.length ? `<span class="pill failed">mots pièges : ${esc(x.traps.join(", "))}</span>` : ""}</summary>
      <p class="michael-words">${esc(x.script || x.description)}</p>
      <div class="row">
        <label>Jeu <select data-attr="jeu" data-shot="${x.id}">${Object.entries(JEU_LABEL).map(([k, l]) => `<option value="${k}" ${x.jeu === k ? "selected" : ""}>${l}</option>`).join("")}</select></label>
        <label title="Deux plans de même axe peuvent sortir d'une même prise continue">Axe <input data-attr="axe" data-shot="${x.id}" value="${esc(x.axe || "")}" style="width:5em"></label>
        ${lookSel}
      </div>
      <label class="stack">Action envoyée au modèle (${x.action_edited ? "écrite par toi" : x.action_en ? "écrite par le prompteur" : "reprise du prompt détaillé du plan"})
        <textarea data-action="${x.id}" rows="4">${esc(x.action)}</textarea></label>
      <div class="row"><button class="btn small" data-saveaction="${x.id}">Enregistrer l'action</button></div>
    </details>`;
  };
  const take = (t) => `
    <section class="panel stack take">
      <div class="row"><h3>Prise ${String.fromCharCode(64 + t.n)} · ${FORM_LABEL[t.form] || t.form} · ${secs(t.duration_s)} payées</h3><span class="spacer"></span>
        <span class="spend-cost">${usd(t.est_usd)}</span></div>
      <ul class="takeshots">${t.shots.map((w) => `<li><b>${w.num}</b> fenêtre ${secs(w.t_in)} → ${secs(w.t_out)} <span class="hint">(${secs(w.duration)} dans le morceau)</span></li>`).join("")}</ul>
      ${t.already.length ? `<p class="hint">Déjà tourné : plan${t.already.length > 1 ? "s" : ""} ${t.already.join(", ")}. Tourner à nouveau crée une autre prise, l'ancienne reste gardable.</p>` : ""}
      ${t.alerts.map((a) => `<p class="alert ${a.level}">${esc(a.text)}</p>`).join("")}
      ${t.refs ? `<div class="hint">Références envoyées : ${t.refs.map((r) => esc(r.label)).join(", ") || "aucune"}</div>` : ""}
      ${t.prompt ? `<details><summary class="hint">Prompt assemblé${t.prompt.traps.length ? ` · ⚠ mots pièges : ${esc(t.prompt.traps.join(", "))}` : ""}</summary>
        <div class="promptblocks">${t.prompt.blocks.map((b) => `<p><span class="pill wait">${esc(b.block)} · ${esc(b.source)}</span> ${esc(b.text)}</p>`).join("")}</div>
        <pre class="mono prompt">${esc(t.prompt.text)}</pre><p class="hint">À éviter : ${esc(t.prompt.negative)}</p></details>` : ""}
    </section>`;
  const blocked = p.blocking || !shootable.length;
  box.innerHTML = `
    <div class="stack">
      <div class="row"><a class="btn small ghost" href="${base}">← Séquences</a><span class="spacer"></span>
        <a class="btn small" href="${base}/d/${id}">Dérushage</a></div>
      <section class="panel stack">
        <div class="row"><h2>${s.num}. </h2><input id="s-name" value="${esc(s.name)}" style="flex:1;font-size:1.1em"></div>
        <p class="hint">Profil : <b>${esc(v.profile_label)}</b> (calculé à partir des plans) · ${shootable.length} plan${shootable.length > 1 ? "s" : ""} à tourner</p>
        <label class="stack">Fiche de la séquence : lieu, heure, lumière, palette, figurants. Elle est injectée mot pour mot dans chaque prise.
          <textarea id="s-fiche" rows="3" placeholder="Ex. Morning, low warm autumn sun, long soft shadows, courtyard of an old limestone house…">${esc(s.fiche || "")}</textarea></label>
        <div class="row"><button class="btn small" id="s-save">Enregistrer nom et fiche</button></div>
      </section>
      ${(v.gaps || []).map((g) => `<p class="alert warn">${esc(g)}</p>`).join("")}
      <section class="panel stack">
        <div class="row"><h2>Comment la machine la tourne</h2><span class="spacer"></span>
          <span class="pill ${v.chosen_by_michael ? "review" : "done"}">${v.chosen_by_michael ? "offre choisie par toi" : "offre recommandée"}</span></div>
        <p><b>${esc(p.offer_label)}</b> · ${p.takes.length} prise${p.takes.length > 1 ? "s" : ""} · <b>${usd(p.total_usd)}</b> · ${esc(p.funding_label)}</p>
        ${p.warnings.map((w) => `<p class="alert ${w.level}">${esc(w.text)}</p>`).join("")}
        <div class="row">
          <label>Mode <select id="s-mode">${modeOpts}</select></label>
          <label>Résolution <select id="s-res">${resOpts}</select></label>
        </div>
        <div id="s-optimpact"></div>
        ${v.chosen_by_michael ? `<button class="btn small ghost" id="s-reco">Revenir à l'offre recommandée</button>` : ""}
      </section>
      ${p.mode === "references" ? `<section class="panel stack"><h2>Références</h2>
        <p class="hint">Au plus ${v.max_refs} par prise chez ${esc(p.offer_label)}. Sans choix de ta part, la machine prend dans l'ordre : visage, image maîtresse, en pied, tenue, objet, décor.
          Une image refusée par le fournisseur ne part jamais.</p>
        <div class="refgrid">${v.refs.map((r) => refChip(r, r.selected)).join("") || `<p class="empty">Aucune image utilisable.</p>`}</div>
        <div class="row"><button class="btn small" id="s-refs">Garder ce choix</button>
          ${(s.options.refs || []).length ? `<button class="btn small ghost" id="s-refsauto">Laisser la machine choisir</button>` : ""}</div></section>` : ""}
      <h2 class="section-title">Plans</h2>
      ${v.shots.map(shotRow).join("")}
      <h2 class="section-title">Prises proposées</h2>
      ${p.takes.map(take).join("") || `<p class="empty">Aucun plan d'un bloc validé.</p>`}
      <section class="panel stack">
        <h2>Autres offres pour la séquence</h2>
        ${v.alternatives.map((a) => `<div class="spend-item">
          <div class="row"><b>${esc(a.label)}</b><span class="hint">${a.takes} prise${a.takes > 1 ? "s" : ""} · ${esc(a.funding_label || "")}${a.recommended ? " · recommandée" : ""}</span>
            <span class="spacer"></span><span class="spend-cost">${usd(a.total_usd)}</span></div>
          <details><summary class="hint">Ce que ce changement implique</summary>${impactList(a.impact)}</details>
          <div class="row"><button class="btn small" data-offer="${esc(a.offer)}" ${a.usable ? "" : "disabled title=\"Fournisseur non branché\""}>Passer sur ${esc(a.label)}</button></div>
        </div>`).join("")}
      </section>
      <section class="panel stack shootbar">
        <div class="row"><b>Total ${usd(p.total_usd)}</b><span class="hint">${esc(p.funding_label)}${Object.values(v.reserves).map((r) => ` · ${esc(r.label)} : reste ${usd(r.remaining)}`).join("")}</span></div>
        ${blocked ? `<p class="alert bad">Rien ne peut partir tant que les points en rouge ne sont pas réglés.</p>` : ""}
        <button class="btn go" id="s-shoot" ${blocked ? "disabled" : ""} data-total="${p.total_usd}">Accorder et tourner · ${usd(p.total_usd)}</button>
      </section>
    </div>`;
  box.querySelector("#s-save").addEventListener("click", () => save({ name: box.querySelector("#s-name").value, fiche: box.querySelector("#s-fiche").value }));
  const optBox = box.querySelector("#s-optimpact");
  const showImpact = (kind, key, payload) => {
    const imp = (optImp[kind] || {})[key];
    if (!imp) { optBox.innerHTML = ""; return; }
    optBox.innerHTML = `<div class="actionbox stack"><b>Avant de changer :</b>${impactList(imp.impact)}
      <div class="row"><button class="btn small go" id="s-apply">Appliquer · ${usd(imp.total_usd)}</button><button class="btn small ghost" id="s-cancel">Garder l'actuel</button></div></div>`;
    optBox.querySelector("#s-apply").addEventListener("click", () => save({ options: payload }, "Option changée : prises recalculées"));
    optBox.querySelector("#s-cancel").addEventListener("click", () => renderSequence(box, clip, id));
  };
  box.querySelector("#s-mode").addEventListener("change", (e) => showImpact("mode", e.target.value, { mode: e.target.value }));
  box.querySelector("#s-res").addEventListener("change", (e) => showImpact("resolution", e.target.value, { resolution: e.target.value }));
  box.querySelector("#s-reco")?.addEventListener("click", () => save({ clear_offer: true }, "Offre recommandée rétablie"));
  box.querySelectorAll("[data-offer]").forEach((b) => b.addEventListener("click", () => save({ offer_key: b.dataset.offer }, "Offre changée : prises recalculées")));
  box.querySelector("#s-refs")?.addEventListener("click", () => save({ options: { refs: [...box.querySelectorAll("[data-ref]:checked")].map((c) => c.dataset.ref) } }, "Références gardées"));
  box.querySelector("#s-refsauto")?.addEventListener("click", () => save({ options: { refs: [] } }, "La machine choisit les références"));
  const attr = async (shot, json, msg) => {
    try { await api(`/api/shots/${shot}/attrs`, { json }); toast(msg || "Enregistré"); await renderSequence(box, clip, id); }
    catch (e) { toast(e.message, "err"); }
  };
  box.querySelectorAll("[data-attr]").forEach((el) => el.addEventListener("change", () => attr(el.dataset.shot, { [el.dataset.attr]: el.value })));
  box.querySelectorAll("[data-look]").forEach((el) => el.addEventListener("change", () => attr(el.dataset.look, { look: { character: el.dataset.char, look: el.value } }, "Tenue posée")));
  box.querySelectorAll("[data-saveaction]").forEach((b) => b.addEventListener("click", () => attr(b.dataset.saveaction, { action_en: box.querySelector(`[data-action="${b.dataset.saveaction}"]`).value }, "Action enregistrée")));
  box.querySelector("#s-shoot")?.addEventListener("click", async (e) => {
    const b = e.currentTarget;
    b.disabled = true;
    try {
      const r = await api(`/api/sequences/${id}/shoot`, { json: { accepted_usd: +b.dataset.total } });
      toast(`Accordé : ${r.takes} prise${r.takes > 1 ? "s" : ""} partent (${usd(r.total_usd)})`);
      refreshSys();
      location.hash = `${base}/d/${id}`;
    } catch (err) { toast(err.message, "err"); b.disabled = false; }
  });
}

/* ---------- Dérushage d'une séquence, plan par plan (R-H13) et montage (R-M1) ---------- */

const TAKE_STATUS = { queued: ["accordée, part bientôt", "wait"], submitting: ["envoi…", "work"], running: ["en tournage", "work"],
  done: ["rentrée", "done"], blocked: ["bloquée", "failed"], failed: ["échec", "failed"], check: ["à vérifier", "review"] };

const derushPick = {};

async function renderDerush(box, clip, id) {
  const d = await api(`/api/sequences/${id}/derush`);
  const base = `#/clip/${encodeURIComponent(clip.slug)}/tournage`;
  const mot = d.motives.map((m) => `<option value="${m.key}">${esc(m.label)}</option>`).join("");
  const shotCard = (s) => {
    const done = s.takes.filter((t) => t.status === "done");
    const cur = done.find((t) => t.take_id === derushPick[s.id]) || done.find((t) => t.kept) || done[0];
    const others = s.takes.filter((t) => t.status !== "done");
    const win = cur ? `
      <div class="derushplayer" data-shot="${s.id}" data-take="${cur.take_id}" data-tin="${cur.t_in}" data-speed="${cur.speed}"
           data-d="${s.duration}" data-start="${s.t_start}" data-takedur="${cur.take_duration}">
        <video src="${media(cur.path)}" playsinline muted preload="metadata"></video>
        <div class="row"><button class="btn small" data-play>▶ En boucle sur la musique</button>
          <span class="hint mono" data-pos></span></div>
        <label>Début dans la prise <input type="range" data-tinr min="0" max="${Math.max(0, cur.take_duration - s.duration * cur.speed).toFixed(2)}" step="0.05" value="${cur.t_in}">
          <span class="mono" data-tinv>${secs(cur.t_in)}</span></label>
        <label>Vitesse <input type="range" data-spr min="0.9" max="1.1" step="0.01" value="${cur.speed}"> <span class="mono" data-spv>${cur.speed}</span></label>
        <div class="row"><button class="btn small" data-savewin>Enregistrer la fenêtre (gratuit)</button></div>
      </div>
      ${done.length > 1 ? `<div class="row">Prises : ${done.map((t) => `<button class="btn small ${t === cur ? "go" : ""}" data-pick="${s.id}:${t.take_id}">#${t.take_id}${t.kept ? " ✓" : ""}</button>`).join("")}</div>` : ""}
      <div class="row">
        <button class="btn ok" data-keep="${cur.take_id}:${s.id}" ${cur.kept ? "disabled" : ""}>${cur.kept ? "Gardé ✓" : "Garder"}</button>
        <select data-motive="${s.id}">${mot}</select>
        <input data-note="${s.id}" placeholder="Ce qui ne va pas" style="flex:1;min-width:10em">
        <button class="btn small danger" data-redo="${cur.take_id}:${s.id}">Refaire</button>
      </div>
      ${cur.verdict === "redo" ? `<p class="alert warn">À refaire (${esc(cur.motive || "")}) : ${esc(cur.note || "")}. Il revient dans le plan de tournage avec son coût.</p>` : ""}` : "";
    return `<section class="panel stack derushcard" id="ds-${s.id}">
      <div class="row"><h3>Plan ${s.num}</h3><span class="mono">${tc(s.t_start)}–${tc(s.t_end)} · ${secs(s.duration)}</span>
        <span class="spacer"></span>${pill(s.state_label, s.state === "garde" ? "done" : s.state === "a_derusher" ? "review" : s.state === "bloque" ? "failed" : "wait")}</div>
      <p class="michael-words">${esc(s.words)}</p>
      ${win || (others.length ? "" : `<p class="hint">Pas encore de prise : accorde le tournage depuis le plan de tournage.</p>`)}
      ${others.map((t) => { const [l, c] = TAKE_STATUS[t.status] || [t.status, "wait"];
        return `<div class="row">${pill(`Prise #${t.take_id} : ${l}`, c)}${t.error ? `<span class="hint">${esc(t.error)}</span>` : ""}
          ${["check", "failed"].includes(t.status) ? `<button class="btn small" data-relaunch="${t.take_id}">Relancer (déjà accordée)</button>` : ""}</div>`; }).join("")}
    </section>`;
  };
  const m = await api(`/api/clips/${encodeURIComponent(clip.slug)}/montage`);
  box.innerHTML = `
    <div class="stack">
      <div class="row"><a class="btn small ghost" href="${base}/s/${id}">← Plan de tournage</a><span class="spacer"></span>
        <a class="btn small ghost" href="${base}">Séquences</a></div>
      <h2>${esc(d.sequence.num + ". " + d.sequence.name)} · dérushage</h2>
      <p class="hint">Un plan à la fois, joué en boucle sur la musique à son timecode. Garder, refaire avec un motif, ou régler la fenêtre :
        rien de tout cela ne dépense. Un plan à refaire revient dans le plan de tournage, avec son coût.</p>
      ${d.shots.map(shotCard).join("") || `<p class="empty">Aucun plan d'un bloc validé.</p>`}
      <section class="panel stack" id="montagebox">
        <div class="row"><h2>Montage des blocs validés</h2><span class="spacer"></span>
          <button class="btn small go" id="m-build">${m.running ? "Montage en cours…" : "Mettre à jour le montage"}</button></div>
        ${m.error ? `<p class="alert bad">${esc(m.error)}</p>` : ""}
        ${m.path ? `<video controls playsinline src="${media(m.path)}?t=${encodeURIComponent(m.built_at || "")}" style="width:100%"></video>
          <p class="hint">${m.kept} plan${m.kept > 1 ? "s" : ""} gardé${m.kept > 1 ? "s" : ""} sur ${m.shots} ; les autres sont des cartons. Mis à jour à chaque décision.</p>` : `<p class="hint">Pas encore de montage.</p>`}
      </section>
    </div>`;
  const song = d.song_path ? new Audio(media(d.song_path)) : null;
  box.querySelectorAll(".derushplayer").forEach((pl) => {
    const v = pl.querySelector("video"), pos = pl.querySelector("[data-pos]");
    const get = () => ({ tin: +pl.querySelector("[data-tinr]").value, sp: +pl.querySelector("[data-spr]").value, d: +pl.dataset.d, start: +pl.dataset.start });
    let playing = false;
    const restart = () => { const g = get(); v.playbackRate = g.sp; v.currentTime = g.tin; if (song) { song.currentTime = g.start; song.play().catch(() => {}); } v.play().catch(() => {}); };
    v.addEventListener("timeupdate", () => {
      const g = get();
      pos.textContent = `${secs(Math.max(0, v.currentTime - g.tin) / g.sp)} / ${secs(g.d)}`;
      if (playing && v.currentTime >= g.tin + g.d * g.sp) restart();
    });
    pl.querySelector("[data-play]").addEventListener("click", (e) => {
      playing = !playing; e.target.textContent = playing ? "⏸ Pause" : "▶ En boucle sur la musique";
      if (playing) restart(); else { v.pause(); song && song.pause(); }
    });
    pl.querySelector("[data-tinr]").addEventListener("input", (e) => { pl.querySelector("[data-tinv]").textContent = secs(+e.target.value); if (!playing) v.currentTime = +e.target.value; });
    pl.querySelector("[data-spr]").addEventListener("input", (e) => {
      pl.querySelector("[data-spv]").textContent = (+e.target.value).toFixed(2);
      pl.querySelector("[data-tinr]").max = Math.max(0, +pl.dataset.takedur - +pl.dataset.d * +e.target.value).toFixed(2);
    });
    pl.querySelector("[data-savewin]").addEventListener("click", () => post(pl.dataset.take, pl.dataset.shot, { action: "window", t_in: get().tin, speed: get().sp }, "Fenêtre enregistrée"));
  });
  const post = async (take, shot, json, msg) => {
    try { const r = await api(`/api/takes/${take}/shots/${shot}`, { json }); toast(r.next ? `${msg}. ${r.next}` : msg); song && song.pause(); await renderDerush(box, clip, id); }
    catch (e) { toast(e.message, "err"); }
  };
  box.querySelectorAll("[data-keep]").forEach((b) => b.addEventListener("click", () => { const [t, s] = b.dataset.keep.split(":"); post(t, s, { action: "keep" }, "Gardé"); }));
  box.querySelectorAll("[data-redo]").forEach((b) => b.addEventListener("click", () => {
    const [t, s] = b.dataset.redo.split(":");
    post(t, s, { action: "redo", motive: box.querySelector(`[data-motive="${s}"]`).value, note: box.querySelector(`[data-note="${s}"]`).value }, "À refaire");
  }));
  box.querySelectorAll("[data-pick]").forEach((b) => b.addEventListener("click", () => {
    const [sh, t] = b.dataset.pick.split(":"); derushPick[sh] = +t; song && song.pause(); renderDerush(box, clip, id);
  }));
  box.querySelectorAll("[data-relaunch]").forEach((b) => b.addEventListener("click", async () => {
    try { await api(`/api/takes/${b.dataset.relaunch}/relaunch`, { json: {} }); toast("Relancée"); await renderDerush(box, clip, id); } catch (e) { toast(e.message, "err"); }
  }));
  box.querySelector("#m-build").addEventListener("click", async () => {
    await api(`/api/clips/${encodeURIComponent(clip.slug)}/montage`, { json: {} }); toast("Montage lancé en tâche de fond");
    setTimeout(() => renderDerush(box, clip, id), 4000);
  });
}
