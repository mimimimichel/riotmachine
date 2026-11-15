"""Les agents Claude sous le contrôle de Michael (R-T1, R-T4).

Le worker ne lance plus Claude de lui-même. Quand un clip ou un personnage a
besoin d'un agent, il dépose une **demande** (`agent_queue`) avec ses raisons et
une estimation de coût. Michael l'accorde ou la refuse dans la régie (page
Consommation). En mode « automatique », une demande est accordée d'office tant
que le plafond du jour n'est pas atteint.

Chaque passage est lancé avec `--max-budget-usd` (plafond par passage) et en
sortie JSON : coût, tours et jetons sont relevés à la fin et rangés dans
`agent_runs`. Sur l'abonnement, le coût est un équivalent API : il sert de
mesure, pas de facture.
"""

from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from . import db, notify
from .settings import get_settings

# Réglages modifiables depuis la régie, rangés dans settings_kv
DEFAULTS: dict[str, str] = {
    "agent_mode": "accord",          # accord | auto
    "claude_day_cap_usd": "3.0",     # plafond du jour, tous agents confondus
    "claude_run_cap_usd": "1.0",     # plafond d'un passage (--max-budget-usd)
}

# passages en cours : id du passage -> processus
_running: dict[int, subprocess.Popen] = {}
_claude_missing = False


# --- réglages -------------------------------------------------------------------

def get(conn: sqlite3.Connection, key: str) -> str:
    r = conn.execute("SELECT value FROM settings_kv WHERE key=?", (key,)).fetchone()
    return r["value"] if r else DEFAULTS[key]


def put(conn: sqlite3.Connection, key: str, value: Any, by: str | None = None) -> None:
    if key not in DEFAULTS:
        raise ValueError(f"Réglage inconnu : {key}")
    value = str(value).strip()
    if key == "agent_mode" and value not in ("accord", "auto"):
        raise ValueError("Mode : « accord » ou « auto »")
    if key.endswith("_usd"):
        if float(value) < 0:
            raise ValueError("Un plafond ne peut pas être négatif")
        value = f"{float(value):.2f}"
    old = get(conn, key)
    conn.execute("INSERT INTO settings_kv (key, value, updated_at) VALUES (?,?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                 (key, value, db.now()))
    conn.execute("INSERT INTO changes (table_name, row_id, field, old, new, author, reason, created_at) "
                 "VALUES ('settings_kv', ?, 'value', ?, ?, ?, NULL, ?)", (key, old, value, by or db.actor(), db.now()))


def config(conn: sqlite3.Connection) -> dict:
    return {"mode": get(conn, "agent_mode"), "day_cap_usd": float(get(conn, "claude_day_cap_usd")),
            "run_cap_usd": float(get(conn, "claude_run_cap_usd"))}


# --- mesures ----------------------------------------------------------------------

def _today() -> str:
    return db.now()[:10]


def spent_today(conn: sqlite3.Connection) -> float:
    r = conn.execute("SELECT COALESCE(SUM(COALESCE(cost_usd, est_usd, 0)),0) FROM agent_runs WHERE substr(started_at,1,10)=?",
                     (_today(),)).fetchone()
    return float(r[0] or 0)


def command_kind(command: str) -> str:
    return command.split()[0] if command else "?"


def estimate(conn: sqlite3.Connection, command: str) -> float | None:
    """Coût moyen des cinq derniers passages mesurés de la même commande."""
    rs = conn.execute("SELECT cost_usd FROM agent_runs WHERE command_kind=? AND cost_usd IS NOT NULL "
                      "ORDER BY id DESC LIMIT 5", (command_kind(command),)).fetchall()
    if not rs:
        return None
    return round(sum(r[0] for r in rs) / len(rs), 2)


def usage(conn: sqlite3.Connection, days: int = 14) -> list[dict]:
    """Consommation par jour et par commande (R-T4, `riot usage`)."""
    return db.rows(conn.execute(
        "SELECT substr(started_at,1,10) AS day, command_kind AS command, COUNT(*) AS runs, "
        "ROUND(SUM(COALESCE(cost_usd,0)),2) AS cost_usd, SUM(COALESCE(turns,0)) AS turns, "
        "SUM(COALESCE(tokens_in,0)) AS tokens_in, SUM(COALESCE(tokens_out,0)) AS tokens_out "
        "FROM agent_runs WHERE started_at >= date('now', ?) GROUP BY day, command_kind ORDER BY day DESC, command_kind",
        (f"-{int(days)} days",)).fetchall())


# --- demandes ---------------------------------------------------------------------

def _last_runs(conn: sqlite3.Connection, key: str, n: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM agent_runs WHERE clip_slug=? ORDER BY id DESC LIMIT ?", (key, n)).fetchall()


def running_for(conn: sqlite3.Connection, key: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM agent_runs WHERE clip_slug=? AND ended_at IS NULL", (key,)).fetchone())


def _worth_asking(conn: sqlite3.Connection, key: str, fingerprint: str, retry: bool) -> bool:
    """Même règle que l'ancien réveil : pas de nouvelle demande pour une situation
    que l'agent vient de traiter sans la faire avancer (au plus N relances, après un délai)."""
    s = get_settings()
    if running_for(conn, key):
        return False
    last = _last_runs(conn, key, s.agent_max_retries + 1)
    if not last or last[0]["fingerprint"] != fingerprint:
        return True
    if last[0]["ended_at"] is None or not retry:
        return False
    if len(last) > s.agent_max_retries and all(r["fingerprint"] == fingerprint for r in last):
        return False
    return db.age_seconds(last[0]["ended_at"]) > s.agent_backoff_s


def request(conn: sqlite3.Connection, key: str, command: str, reasons: list[str], fingerprint: str,
            retry: bool = True) -> dict | None:
    """Dépose (ou met à jour) la demande d'agent pour `key`. Retourne la demande, ou None."""
    pending = db.row(conn.execute("SELECT * FROM agent_queue WHERE key=? AND status IN ('pending','approved')",
                                  (key,)).fetchone())
    if pending:
        if pending["fingerprint"] != fingerprint:
            conn.execute("UPDATE agent_queue SET reasons=?, fingerprint=?, updated_at=? WHERE id=?",
                         (json.dumps(reasons, ensure_ascii=False), fingerprint, db.now(), pending["id"]))
        return pending
    if not _worth_asking(conn, key, fingerprint, retry):
        return None
    est = estimate(conn, command)
    cfg = config(conn)
    auto = cfg["mode"] == "auto" and spent_today(conn) + (est or cfg["run_cap_usd"]) <= cfg["day_cap_usd"]
    cur = conn.execute(
        "INSERT INTO agent_queue (key, command, reasons, fingerprint, est_usd, status, decided_by, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (key, command, json.dumps(reasons, ensure_ascii=False), fingerprint, est,
         "approved" if auto else "pending", "code:auto" if auto else None, db.now(), db.now()))
    if not auto:
        cost = f"~{est:.2f} $" if est is not None else f"au plus {cfg['run_cap_usd']:.2f} $"
        notify.send_once(conn, f"agent-ask:{key}:{fingerprint}",
                         f"🤖 Un agent attend ton accord ({command}, {cost}) :\n• " + "\n• ".join(reasons[:4])
                         + "\n" + notify.regie_link("#/conso"))
    return db.row(conn.execute("SELECT * FROM agent_queue WHERE id=?", (cur.lastrowid,)).fetchone())


def withdraw(conn: sqlite3.Connection, key: str) -> None:
    """La situation s'est réglée sans agent : la demande en attente devient sans objet."""
    conn.execute("UPDATE agent_queue SET status='obsolete', updated_at=? WHERE key=? AND status='pending'",
                 (db.now(), key))


def pending(conn: sqlite3.Connection) -> list[dict]:
    out = db.rows(conn.execute("SELECT * FROM agent_queue WHERE status IN ('pending','approved') ORDER BY id").fetchall())
    for r in out:
        r["reasons"] = json.loads(r["reasons"] or "[]")
    return out


def decide(conn: sqlite3.Connection, request_id: int, approve: bool, by: str | None = None) -> dict:
    r = db.row(conn.execute("SELECT * FROM agent_queue WHERE id=?", (request_id,)).fetchone())
    if not r or r["status"] != "pending":
        raise ValueError("Cette demande n'attend plus de décision.")
    conn.execute("UPDATE agent_queue SET status=?, decided_by=?, updated_at=? WHERE id=?",
                 ("approved" if approve else "refused", by or db.actor(), db.now(), request_id))
    return {**r, "status": "approved" if approve else "refused"}


# --- lancement et relevé ------------------------------------------------------------

def _agent_env() -> dict[str, str]:
    env = dict(os.environ)
    # Une clé API héritée ferait payer l'API à notre insu ; le lanceur (RIOT_CLAUDE_BIN) décide.
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def build_cmd(command: str, run_cap: float) -> list[str]:
    s = get_settings()
    cmd = [s.claude_bin, "-p", command,
           "--permission-mode", "acceptEdits",
           "--allowedTools", "Bash(riot *),Bash(ffmpeg *),Bash(ffprobe *),Read,Write,Edit,Glob,Grep,Agent,Task",
           "--output-format", "json",
           "--max-budget-usd", f"{run_cap:.2f}"]
    perms = s.repo_root / "config" / "agents-permissions.json"
    if perms.is_file():
        cmd += ["--settings", str(perms)]
    if s.claude_model:
        cmd += ["--model", s.claude_model]
    return cmd


def launch_approved(conn: sqlite3.Connection) -> list[str]:
    global _claude_missing
    if not get_settings().agents_enabled:
        return []
    launched = []
    for r in db.rows(conn.execute("SELECT * FROM agent_queue WHERE status='approved' ORDER BY id").fetchall()):
        if running_for(conn, r["key"]):
            continue
        run_id = _launch(conn, r)
        if run_id is None:
            if _claude_missing:
                break
            continue
        conn.execute("UPDATE agent_queue SET status='launched', run_id=?, updated_at=? WHERE id=?",
                     (run_id, db.now(), r["id"]))
        launched.append(r["key"])
    return launched


def _launch(conn: sqlite3.Connection, req: dict) -> int | None:
    global _claude_missing
    s = get_settings()
    cap = float(get(conn, "claude_run_cap_usd"))
    log_path = s.logs_dir / f"agent-{req['key'].replace(':', '-')}-{db.now().replace(':', '')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_cmd(req["command"], cap)
    log = log_path.open("w", encoding="utf-8")
    log.write(f"# {' '.join(cmd)}\n# raisons : {req['reasons']}\n\n")
    log.flush()
    try:
        proc = subprocess.Popen(cmd, cwd=s.repo_root, stdout=log, stderr=subprocess.STDOUT,
                                env=_agent_env(), start_new_session=True)
    except FileNotFoundError:
        notify.send_once(conn, "claude-missing", "⚠️ Claude Code introuvable : installe-le et connecte-toi (claude puis /login).")
        log.close()
        _claude_missing = True
        return None
    reasons = req["reasons"] if isinstance(req["reasons"], str) else json.dumps(req["reasons"], ensure_ascii=False)
    cur = conn.execute(
        "INSERT INTO agent_runs (clip_slug, reason, fingerprint, pid, log_path, started_at, command_kind, est_usd, requested_by) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (req["key"], "; ".join(json.loads(reasons)), req["fingerprint"], proc.pid, str(log_path), db.now(),
         command_kind(req["command"]), req.get("est_usd"), req.get("decided_by")))
    _running[cur.lastrowid] = proc
    return cur.lastrowid


def parse_result(log_path: str | Path) -> dict:
    """Relève coût, tours et jetons dans la sortie JSON de `claude -p`."""
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") != "result":
            continue
        u = d.get("usage") or {}
        return {"cost_usd": d.get("total_cost_usd"), "turns": d.get("num_turns"),
                "tokens_in": (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
                + (u.get("cache_creation_input_tokens") or 0),
                "tokens_out": u.get("output_tokens"), "subtype": d.get("subtype")}
    return {}


def reap(conn: sqlite3.Connection) -> None:
    s = get_settings()
    for run_id, proc in list(_running.items()):
        code = proc.poll()
        run = conn.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone()
        if code is None:
            if db.age_seconds(run["started_at"]) > s.agent_timeout_s:
                proc.send_signal(signal.SIGTERM)
                conn.execute("UPDATE agent_runs SET ended_at=?, exit_code=? WHERE id=?", (db.now(), -15, run_id))
                _running.pop(run_id, None)
            continue
        _running.pop(run_id, None)
        m = parse_result(run["log_path"])
        conn.execute("UPDATE agent_runs SET ended_at=?, exit_code=?, cost_usd=?, turns=?, tokens_in=?, tokens_out=? WHERE id=?",
                     (db.now(), code, m.get("cost_usd"), m.get("turns"), m.get("tokens_in"), m.get("tokens_out"), run_id))
        if m.get("subtype") == "error_max_budget_usd":
            notify.send_once(conn, f"agent-cap:{run_id}",
                             f"✋ L'agent sur <b>{run['clip_slug']}</b> s'est arrêté au plafond du passage. "
                             + notify.regie_link("#/conso"))
        elif code != 0:
            notify.send_once(conn, f"agent-fail:{run_id}",
                             f"⚠️ L'agent a échoué sur <b>{run['clip_slug']}</b> (code {code}). Journal : {run['log_path']}")


def mark_stale(conn: sqlite3.Connection) -> None:
    """Au démarrage du worker : les passages d'une session précédente ne sont plus suivis."""
    for r in conn.execute("SELECT id, log_path FROM agent_runs WHERE ended_at IS NULL").fetchall():
        m = parse_result(r["log_path"])
        conn.execute("UPDATE agent_runs SET ended_at=?, exit_code=-1, cost_usd=COALESCE(cost_usd, ?) WHERE id=?",
                     (db.now(), m.get("cost_usd"), r["id"]))


def recent_runs(conn: sqlite3.Connection, limit: int = 30) -> list[dict]:
    return db.rows(conn.execute(
        "SELECT id, clip_slug AS key, reason, command_kind AS command, started_at, ended_at, exit_code, "
        "cost_usd, est_usd, turns, tokens_in, tokens_out, requested_by FROM agent_runs ORDER BY id DESC LIMIT ?",
        (limit,)).fetchall())


def overview(conn: sqlite3.Connection) -> dict:
    cfg = config(conn)
    return {**cfg, "spent_today_usd": round(spent_today(conn), 2), "pending": pending(conn),
            "running": [r["clip_slug"] for r in conn.execute("SELECT clip_slug FROM agent_runs WHERE ended_at IS NULL")],
            "usage": usage(conn), "runs": recent_runs(conn)}
