"""Le scénariste : Michael colle un brainstorm brut, l'agent `scenariste` en tire
des propositions (pitch, concept, dossier de réalisation, blocs, idées de plans),
et Michael accepte ou écarte chaque partie dans l'onglet Dossier.

- Le brainstorm est rangé dans le dossier du clip (dossier/brainstorm-<date>.md).
- Les propositions de l'agent vivent dans work/scenariste.json.
- Une partie acceptée remplit le pitch ou le concept du clip, ou devient un
  document du dossier de réalisation que le script doctor lira.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from . import db
from .production import ProductionError, add_clip_file, rel, studio, update_brief

KINDS = {"pitch": "Pitch", "concept": "Concept", "dossier": "Dossier de réalisation", "blocs": "Blocs et intentions",
         "plans": "Idées de plans", "references": "Références visuelles", "autre": "Autre"}


def _file(clip: dict) -> Path:
    return studio() / clip["dir"] / "work" / "scenariste.json"


def submit_brainstorm(conn, slug: str, text: str) -> str:
    """Michael colle une conversation ou des notes brutes : le scénariste est réveillé."""
    if len(text.strip()) < 40:
        raise ProductionError("Le brainstorm est trop court : colle la conversation ou tes notes complètes")
    stamp = db.now()[:16].replace("T", "-").replace(":", "")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"brainstorm-{stamp}.md"
        src.write_text(text.strip() + "\n", encoding="utf-8")
        f = add_clip_file(conn, slug, "dossier", src, label=f"Brainstorm du {stamp[:10]}")
    conn.execute("UPDATE clips SET scenario_status='requested', updated_at=? WHERE slug=?", (db.now(), slug))
    db.log_event(conn, slug, "scenario", "Brainstorm envoyé au scénariste")
    return f["path"]


def propose(conn, slug: str, data: Any) -> dict:
    """L'agent scénariste dépose ses propositions (voir .claude/agents/scenariste.md)."""
    clip = db.get_clip(conn, slug)
    if not isinstance(data, dict) or not isinstance(data.get("parts"), list) or not data["parts"]:
        raise ProductionError('Format attendu : {"resume": "...", "parts": [{"key", "kind", "title", "text"}]}')
    seen = set()
    for i, p in enumerate(data["parts"], 1):
        if p.get("kind") not in KINDS:
            raise ProductionError(f"Partie {i} : kind doit être l'un de {', '.join(KINDS)}")
        if not str(p.get("text") or "").strip():
            raise ProductionError(f"Partie {i} : texte vide")
        p["key"] = str(p.get("key") or f"{p['kind']}-{i}")
        if p["key"] in seen:
            raise ProductionError(f"Partie {i} : clé {p['key']} en double")
        seen.add(p["key"])
        p.setdefault("title", KINDS[p["kind"]])
        p["status"] = "proposed"
    data["created_at"] = db.now()
    dest = _file(clip)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    conn.execute("UPDATE clips SET scenario_status='proposed', updated_at=? WHERE slug=?", (db.now(), slug))
    db.log_event(conn, slug, "scenario", f"Le scénariste propose {len(data['parts'])} parties")
    return {"parts": len(data["parts"]), "path": rel(dest)}


def state(conn, slug: str) -> dict:
    clip = db.get_clip(conn, slug)
    f = _file(clip)
    data = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    return {"status": clip.get("scenario_status") or "none", "proposal": data, "kinds": KINDS}


def decide(conn, slug: str, key: str, decision: str, text: str | None = None) -> dict:
    """Michael accepte (éventuellement après retouche) ou écarte une partie."""
    if decision not in ("accept", "reject"):
        raise ProductionError("Décision : accept ou reject")
    clip = db.get_clip(conn, slug)
    f = _file(clip)
    if not f.is_file():
        raise ProductionError("Pas de proposition du scénariste")
    data = json.loads(f.read_text(encoding="utf-8"))
    part = next((p for p in data["parts"] if p["key"] == key), None)
    if part is None:
        raise ProductionError("Partie inconnue")
    if text is not None and text.strip():
        part["text"] = text.strip()
    if decision == "accept":
        if part["kind"] == "pitch":
            update_brief(conn, slug, pitch=part["text"])
        elif part["kind"] == "concept":
            update_brief(conn, slug, concept=part["text"])
        else:
            with tempfile.TemporaryDirectory() as tmp:
                src = Path(tmp) / f"scenariste-{key}.md"
                src.write_text(f"# {part['title']}\n\n{part['text']}\n", encoding="utf-8")
                add_clip_file(conn, slug, "dossier", src, label=f"Scénariste : {part['title']}")
    part["status"] = "accepted" if decision == "accept" else "rejected"
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    left = [p for p in data["parts"] if p["status"] == "proposed"]
    if not left:
        conn.execute("UPDATE clips SET scenario_status='none', updated_at=? WHERE slug=?", (db.now(), slug))
    db.log_event(conn, slug, "scenario", f"Scénariste : « {part['title']} » "
                                         f"{'acceptée' if decision == 'accept' else 'écartée'} par Michael")
    return {"ok": True, "left": len(left)}
