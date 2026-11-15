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
      <td>${us.reduce((a, u) => a + u.runs, 0)}</td><td>${money(us.reduce((a, u) => a + u.cost_usd, 0))}</td>
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
