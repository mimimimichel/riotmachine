"""Le worker : la boucle qui tourne en continu sur le PC.

Toutes les RIOT_POLL_SECONDS secondes :
  1. il interroge fal pour les générations en cours et récupère les résultats ;
  2. il lance les étapes automatiques (rendu final, lip-sync) ;
  3. il prévient Michael sur Telegram quand des plans attendent sa validation ;
  4. quand un clip a besoin d'un agent, il dépose une demande que Michael accorde
     dans la régie (page Consommation), puis lance les passages accordés.

Il ne réfléchit pas : tout le jugement est fait par les agents Claude.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
import traceback
from pathlib import Path

from . import agents, db, fal, notify, production, providers
from .settings import get_settings, load_models



def poll_jobs(conn: sqlite3.Connection) -> int:
    """Fait avancer les générations en cours. Retourne le nombre terminées."""
    finished = 0
    jobs = db.rows(conn.execute(
        "SELECT * FROM jobs WHERE status IN ('queued','running') ORDER BY id"
    ).fetchall())
    for job in jobs:
        try:
            st = providers.status(job)
            if st in ("IN_QUEUE", "IN_PROGRESS"):
                if st == "IN_PROGRESS" and job["status"] != "running":
                    conn.execute("UPDATE jobs SET status='running', updated_at=? WHERE id=?", (db.now(), job["id"]))
                continue
            try:
                result = providers.result(job)
            except (fal.FalError, providers.ProviderError) as exc:
                production.on_job_failed(conn, job, str(exc))
                finished += 1
                continue
            if isinstance(result, dict) and result.get("error"):
                production.on_job_failed(conn, job, str(result.get("error")))
            else:
                production.on_job_done(conn, job, result)
            finished += 1
        except Exception as exc:  # erreur réseau passagère : on réessaie au tour suivant
            attempts = job["attempts"] + 1
            conn.execute("UPDATE jobs SET attempts=?, last_error=?, updated_at=? WHERE id=?",
                         (attempts, str(exc)[:1000], db.now(), job["id"]))
            if attempts >= 20:
                production.on_job_failed(conn, job, f"Abandon après {attempts} essais : {exc}")
                finished += 1
    return finished


def run_automatic_steps(conn: sqlite3.Connection) -> int:
    """Étapes sans jugement : image HD, brouillon vidéo validé, rendu final, lip-sync."""
    launched = 0
    for status, launcher in (("hd_todo", production.launch_image_hd),
                             ("draft_todo", production.launch_draft),
                             ("final_todo", production.launch_final),
                             ("lipsync_todo", production.launch_lipsync)):
        for r in conn.execute("SELECT id, clip_slug, num FROM shots WHERE status=? AND deleted_at IS NULL ORDER BY id", (status,)).fetchall():
            try:
                res = launcher(conn, r["id"])
                if not (isinstance(res, dict) and res.get("spend_request")):
                    launched += 1
            except production.BudgetError as exc:
                notify.send_once(conn, f"budget:{r['clip_slug']}:{status}",
                                 f"💸 {r['clip_slug']} : {exc}")
            except Exception as exc:
                step = {"hd_todo": "image_hd", "draft_todo": "draft", "final_todo": "final",
                        "lipsync_todo": "lipsync"}[status]
                db.update(conn, "shots", r["id"], {"status": "failed", "failed_step": step}, by="worker",
                          reason=str(exc)[:200])
                db.add_note(conn, r["id"], "machine", f"Échec du lancement ({status}) : {exc}"[:500])
                db.log_event(conn, r["clip_slug"], "error", f"Plan {r['num']} : {exc}")
    return launched


def notify_reviews(conn: sqlite3.Connection) -> None:
    for c in conn.execute("SELECT slug FROM clips WHERE stage IN ('decoupage_review','production')").fetchall():
        text = production.review_digest(conn, c["slug"])
        if not text:
            continue
        # même contenu = même clé : on ne renvoie que si la liste change
        key = f"review:{c['slug']}:{hashlib.sha1(text.encode()).hexdigest()[:12]}"
        notify.send_once(conn, key, text)
    for r in conn.execute(
            "SELECT cv.character_slug, cv.version, ca.id FROM character_assets ca "
            "JOIN character_versions cv ON cv.id=ca.version_id "
            "WHERE ca.kind='canon' AND ca.parent_id IS NOT NULL AND ca.status='proposed'").fetchall():
        notify.send_once(conn, f"canon-hd:{r['id']}",
                         f"🎭 Canon HD de <b>{r['character_slug']}</b> v{r['version']} prête : compare-la au brouillon.\n"
                         + notify.regie_link(f"#/personnages/{r['character_slug']}"))
    _budget_alerts(conn)


def _budget_alerts(conn: sqlite3.Connection) -> None:
    ratio = float(load_models().get("budget", {}).get("alert_ratio", 0.8))
    for c in db.rows(conn.execute("SELECT * FROM clips WHERE budget_usd IS NOT NULL AND stage!='done'").fetchall()):
        spent = db.clip_cost(conn, c["slug"])
        if c["budget_usd"] and spent >= ratio * c["budget_usd"]:
            notify.send_once(conn, f"budget-alert:{c['slug']}:{int(c['budget_usd'])}",
                             f"💸 <b>{c['title']}</b> : {spent:.2f} $ dépensés sur {c['budget_usd']:.0f} $ de budget.")


# --- Agents Claude : demandes soumises à Michael (R-T1) ----------------------------
# Le worker ne lance plus Claude de lui-même : il dépose une demande avec ses
# raisons et son coût estimé, et ne lance que ce que Michael a accordé (ou ce que
# le mode automatique accorde sous le plafond du jour). Voir riotmachine/agents.py.

def ask_agents(conn: sqlite3.Connection) -> list[str]:
    """Dépose les demandes d'agent des clips et des personnages. Retourne les clés demandées."""
    if not get_settings().agents_enabled:
        return []
    asked = []
    for c in conn.execute("SELECT slug FROM clips WHERE stage!='done' ORDER BY updated_at").fetchall():
        need = production.needs_agent(conn, c["slug"])
        if not need["reasons"]:
            agents.withdraw(conn, c["slug"])
            continue
        if agents.request(conn, c["slug"], f"/prod {c['slug']}", need["reasons"], need["fingerprint"],
                          retry=need.get("retry_on_backoff", True)):
            asked.append(c["slug"])
    for need in production.characters_needing_agent(conn):
        key = f"personnage:{need['slug']}"
        if agents.request(conn, key, f"/casting {need['slug']}",
                          [f"{need.get('what', 'pack demandé')} v{need['version']}"], need["fingerprint"], retry=False):
            asked.append(key)
    return asked


def wake_agents(conn: sqlite3.Connection) -> list[str]:
    """Dépose les demandes puis lance celles qui sont accordées. Retourne les clés lancées."""
    ask_agents(conn)
    return agents.launch_approved(conn)


def tick(conn: sqlite3.Connection, wake: bool = True) -> dict:
    db.set_actor("worker")
    out = {"jobs_done": poll_jobs(conn), "spend_launched": production.run_approved_spend(conn),
           "auto_launched": run_automatic_steps(conn)}
    notify_reviews(conn)
    agents.reap(conn)
    out["agents"] = wake_agents(conn) if wake else []
    return out


def run_forever() -> None:
    db.set_actor("worker")
    s = get_settings()
    production.BACKGROUND = True   # le worker dure : les générations gratuites tournent en arrière-plan
    print(f"Riot Machine worker — studio {s.studio_root} — fal {'SIMULATION' if s.fal_mock else 'réel'} "
          f"— tour toutes les {s.poll_seconds}s")
    with db.session() as conn:
        mark_stale_runs(conn)
        while True:
            try:
                from . import provider_keys
                provider_keys.reload()   # clés ajoutées ou changées depuis la régie
                out = tick(conn)
                if out["jobs_done"] or out["auto_launched"] or out["spend_launched"] or out["agents"]:
                    print(f"[{db.now()}] {out}", flush=True)
            except Exception:
                traceback.print_exc()
            time.sleep(s.poll_seconds)


def mark_stale_runs(conn: sqlite3.Connection) -> None:
    """Au démarrage : les agents d'une session précédente ne sont plus suivis."""
    agents.mark_stale(conn)


def logs_dir() -> Path:
    return get_settings().logs_dir
