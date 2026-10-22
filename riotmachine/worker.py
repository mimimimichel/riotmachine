"""Le worker : la boucle qui tourne en continu sur le PC.

Toutes les RIOT_POLL_SECONDS secondes :
  1. il interroge fal pour les générations en cours et récupère les résultats ;
  2. il lance les étapes automatiques (rendu final, lip-sync) ;
  3. il prévient Michael sur Telegram quand des plans attendent sa validation ;
  4. il réveille Claude Code (`claude -p "/prod <clip>"`) quand un clip a besoin
     d'un agent : découpage, prompts, contrôle qualité, tri des retours.

Il ne réfléchit pas : tout le jugement est fait par les agents Claude.
"""

from __future__ import annotations

import hashlib
import os
import signal
import sqlite3
import subprocess
import time
import traceback
from pathlib import Path

from . import db, fal, notify, production, providers
from .settings import get_settings, load_models

# agents en cours : id du passage -> (processus, clip)
_running: dict[int, tuple[subprocess.Popen, str]] = {}


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
        for r in conn.execute("SELECT id, clip_slug, num FROM shots WHERE status=? ORDER BY id", (status,)).fetchall():
            try:
                launcher(conn, r["id"])
                launched += 1
            except production.BudgetError as exc:
                notify.send_once(conn, f"budget:{r['clip_slug']}:{status}",
                                 f"💸 {r['clip_slug']} : {exc}")
            except Exception as exc:
                conn.execute("UPDATE shots SET status='failed', notes=?, updated_at=? WHERE id=?",
                             (f"Échec du lancement ({status}) : {exc}"[:500], db.now(), r["id"]))
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


# --- Réveil des agents Claude ----------------------------------------------------

def _agent_env() -> dict[str, str]:
    env = dict(os.environ)
    # Une clé API dans l'environnement ferait payer l'API au lieu de l'abonnement Claude.
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def _reap_agents(conn: sqlite3.Connection) -> None:
    for run_id, (proc, _slug) in list(_running.items()):
        code = proc.poll()
        if code is None:
            run = conn.execute("SELECT started_at FROM agent_runs WHERE id=?", (run_id,)).fetchone()
            if db.age_seconds(run["started_at"]) > get_settings().agent_timeout_s:
                proc.send_signal(signal.SIGTERM)
                conn.execute("UPDATE agent_runs SET ended_at=?, exit_code=? WHERE id=?", (db.now(), -15, run_id))
                _running.pop(run_id, None)
            continue
        conn.execute("UPDATE agent_runs SET ended_at=?, exit_code=? WHERE id=?", (db.now(), code, run_id))
        _running.pop(run_id, None)
        if code != 0:
            run = conn.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone()
            notify.send_once(conn, f"agent-fail:{run_id}",
                             f"⚠️ L'orchestrateur a échoué sur <b>{run['clip_slug']}</b> (code {code}). "
                             f"Journal : {run['log_path']}")


def _should_wake(conn: sqlite3.Connection, slug: str, need: dict) -> bool:
    fingerprint = need["fingerprint"]
    if any(clip == slug for _proc, clip in _running.values()):
        return False
    last = conn.execute(
        "SELECT * FROM agent_runs WHERE clip_slug=? ORDER BY id DESC LIMIT 1", (slug,)
    ).fetchone()
    if last is None or last["fingerprint"] != fingerprint:
        return True
    # Même situation qu'au dernier passage : l'agent n'a pas pu avancer.
    # On attend avant de réessayer pour ne pas brûler le quota de l'abonnement.
    if last["ended_at"] is None or not need.get("retry_on_backoff", True):
        return False
    return db.age_seconds(last["ended_at"]) > get_settings().agent_backoff_s


def wake_agents(conn: sqlite3.Connection) -> list[str]:
    s = get_settings()
    if not s.agents_enabled:
        return []
    global _claude_missing
    _claude_missing = False
    woken = []
    for c in conn.execute("SELECT slug FROM clips WHERE stage!='done' ORDER BY updated_at").fetchall():
        need = production.needs_agent(conn, c["slug"])
        if not need["reasons"] or not _should_wake(conn, c["slug"], need):
            continue
        if _launch_claude(conn, c["slug"], f"/prod {c['slug']}", need["reasons"], need["fingerprint"]):
            woken.append(c["slug"])
        elif _claude_missing:
            return woken
    return woken


_claude_missing = False


def _launch_claude(conn: sqlite3.Connection, key: str, prompt: str, reasons: list[str], fingerprint: str) -> bool:
    global _claude_missing
    s = get_settings()
    log_path = s.logs_dir / f"agent-{key.replace(':', '-')}-{db.now().replace(':', '')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        s.claude_bin, "-p", prompt,
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Bash(riot *),Bash(ffmpeg *),Bash(ffprobe *),Read,Write,Edit,Glob,Grep,Agent,Task",
        "--output-format", "text",
    ]
    if s.claude_model:
        cmd += ["--model", s.claude_model]
    log = log_path.open("w", encoding="utf-8")
    log.write(f"# {' '.join(cmd)}\n# raisons : {reasons}\n\n")
    log.flush()
    try:
        proc = subprocess.Popen(cmd, cwd=s.repo_root, stdout=log, stderr=subprocess.STDOUT,
                                env=_agent_env(), start_new_session=True)
    except FileNotFoundError:
        notify.send_once(conn, "claude-missing", "⚠️ Claude Code introuvable : installe-le et connecte-toi (claude puis /login).")
        log.close()
        _claude_missing = True
        return False
    cur = conn.execute(
        "INSERT INTO agent_runs (clip_slug, reason, fingerprint, pid, log_path, started_at) VALUES (?,?,?,?,?,?)",
        (key, "; ".join(reasons), fingerprint, proc.pid, str(log_path), db.now()),
    )
    _running[cur.lastrowid] = (proc, key)
    return True


def wake_casting(conn: sqlite3.Connection) -> list[str]:
    """Réveille /casting quand Michael a demandé le pack d'un personnage."""
    s = get_settings()
    if not s.agents_enabled:
        return []
    woken = []
    for need in production.characters_needing_agent(conn):
        key = f"personnage:{need['slug']}"
        need = {**need, "retry_on_backoff": False}
        if not _should_wake(conn, key, need):
            continue
        if _launch_claude(conn, key, f"/casting {need['slug']}", [f"pack demandé v{need['version']}"],
                          need["fingerprint"]):
            woken.append(key)
    return woken


def tick(conn: sqlite3.Connection, wake: bool = True) -> dict:
    out = {"jobs_done": poll_jobs(conn), "auto_launched": run_automatic_steps(conn)}
    notify_reviews(conn)
    _reap_agents(conn)
    out["agents"] = (wake_agents(conn) + wake_casting(conn)) if wake else []
    return out


def run_forever() -> None:
    s = get_settings()
    print(f"Riot Machine worker — studio {s.studio_root} — fal {'SIMULATION' if s.fal_mock else 'réel'} "
          f"— tour toutes les {s.poll_seconds}s")
    with db.session() as conn:
        mark_stale_runs(conn)
        while True:
            try:
                out = tick(conn)
                if out["jobs_done"] or out["auto_launched"] or out["agents"]:
                    print(f"[{db.now()}] {out}", flush=True)
            except Exception:
                traceback.print_exc()
            time.sleep(s.poll_seconds)


def mark_stale_runs(conn: sqlite3.Connection) -> None:
    """Au démarrage : les agents d'une session précédente ne sont plus suivis."""
    conn.execute("UPDATE agent_runs SET ended_at=?, exit_code=-1 WHERE ended_at IS NULL", (db.now(),))


def logs_dir() -> Path:
    return get_settings().logs_dir
