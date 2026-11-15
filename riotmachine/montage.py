"""Montage automatique sur le morceau (R-M1, R-T8).

Chaque plan devient un segment à sa durée exacte : la fenêtre gardée de sa prise
(début, vitesse), ou un carton noir avec ses mots s'il n'a pas encore de prise.
Un segment est rangé sous une clé (prise, fenêtre, vitesse, durée) : seul ce qui
a changé est réencodé. Le montage tourne en tâche de fond, jamais dans une requête.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import threading
from pathlib import Path
from typing import Any

from . import db, derush, media, production

SIZES = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (1024, 1024)}
FONT = next((p for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                         "/usr/share/fonts/TTF/DejaVuSans.ttf") if Path(p).is_file()), None)
_running: set[str] = set()
_status: dict[str, dict] = {}


def _dir(slug: str) -> Path:
    return production.studio() / "clips" / slug / "montage"


def _key(seg: dict, size: tuple[int, int]) -> str:
    d = round(float(seg["t_end"]) - float(seg["t_start"]), 3)
    raw = [seg.get("take_path"), seg.get("t_in"), seg.get("speed"), d, size,
           None if seg.get("take_path") else (seg["num"], seg.get("script") or seg.get("description"))]
    return hashlib.sha1(json.dumps(raw, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def _segment(seg: dict, out: Path, size: tuple[int, int]) -> None:
    w, h = size
    d = max(0.1, float(seg["t_end"]) - float(seg["t_start"]))
    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24,format=yuv420p"
    if seg.get("take_path"):
        src = production.absp(seg["take_path"])
        speed = float(seg.get("speed") or 1.0)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{float(seg['t_in']):.3f}", "-i", str(src),
               "-t", f"{d * speed:.3f}", "-an", "-vf", f"setpts=PTS/{speed:.4f},{vf}", "-t", f"{d:.3f}"]
    else:
        words = (seg.get("script") or seg.get("description") or "")[:90]
        label = f"Plan {seg['num']} : pas encore de prise"
        draw = ""
        if FONT:
            draw = (f",drawtext=fontfile={FONT}:text='{_escape(label)}':fontcolor=white:fontsize={h // 22}:"
                    f"x=(w-text_w)/2:y=h/2-{h // 12},drawtext=fontfile={FONT}:text='{_escape(words)}':"
                    f"fontcolor=0xbbbbbb:fontsize={h // 34}:x=(w-text_w)/2:y=h/2+{h // 40}")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x15131c:s={w}x{h}:r=24",
               "-t", f"{d:.3f}", "-vf", "format=yuv420p" + draw]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)]
    media._run(cmd)


def build(conn: sqlite3.Connection, slug: str, block_nums: list[int] | None = None) -> dict:
    clip = db.get_clip(conn, slug)
    segs = derush.kept_segments(conn, slug, block_nums)
    if not segs:
        raise production.ProductionError("Aucun plan à monter (aucun bloc validé).")
    size = SIZES.get(clip.get("aspect_ratio") or "16:9", SIZES["16:9"])
    cache = _dir(slug) / ".segments"
    cache.mkdir(parents=True, exist_ok=True)
    parts, made = [], 0
    for s in segs:
        out = cache / f"{_key(s, size)}.mp4"
        if not out.is_file():
            _segment(s, out, size)
            made += 1
        parts.append(out)
    # les trous entre plans (zone à résoudre) : carton de la durée du trou
    listing = cache / f"concat-{slug}.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    video = cache / f"video-{slug}.mp4"
    media._run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                "-c", "copy", str(video)])
    start, end = float(segs[0]["t_start"]), float(segs[-1]["t_end"])
    name = "montage" + (f"-blocs-{'-'.join(map(str, block_nums))}" if block_nums else "-blocs-valides")
    dest = _dir(slug) / f"{name}.mp4"
    song = production.absp(clip.get("song_path"))
    if song and song.is_file():
        media._run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
                    "-i", str(song), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                    "-shortest", str(dest)])
    else:
        shutil.copy(video, dest)
    kept = sum(1 for s in segs if s["take_path"])
    info = {"path": production.rel(dest), "shots": len(segs), "kept": kept, "reencoded": made,
            "start": start, "end": end, "built_at": db.now()}
    (_dir(slug) / f"{name}.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


def start(slug: str, block_nums: list[int] | None = None) -> dict:
    """Lance le montage en tâche de fond (R-T8). Un seul à la fois par clip."""
    if slug in _running:
        return {"running": True}
    _running.add(slug)
    _status[slug] = {"running": True}

    def work() -> None:
        conn = db.connect()
        try:
            _status[slug] = {"running": False, **build(conn, slug, block_nums)}
        except Exception as exc:
            _status[slug] = {"running": False, "error": str(exc)[:500]}
            db.log_event(conn, slug, "error", f"Montage impossible : {exc}")
        finally:
            _running.discard(slug)
            conn.close()
    threading.Thread(target=work, daemon=True).start()
    return {"running": True}


def status(slug: str) -> dict[str, Any]:
    if slug in _status:
        return _status[slug]
    f = _dir(slug) / "montage-blocs-valides.json"
    return json.loads(f.read_text()) if f.is_file() else {"running": False, "path": None}
