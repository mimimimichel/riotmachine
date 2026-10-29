"""Analyse gratuite et locale d'un morceau, pour caler le découpage.

- le rythme (librosa) : tempo et position de chaque temps ;
- les paroles (faster-whisper, modèle small sur le processeur) : position de chaque mot.

Le résultat est rangé dans studio/clips/<clip>/work/analyse.json. L'agent
script-doctor s'en sert pour donner un début et une fin à chaque plan : chaque plan
commence sur la ligne de paroles qu'il illustre, et les coupes tombent sur un temps.
Durée : environ 4 minutes pour un morceau de 2 min 30 sur ce PC.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from . import db
from .production import ProductionError, absp, studio


def analyse_song(conn, slug: str, model: str = "small") -> dict[str, Any]:
    clip = db.get_clip(conn, slug)
    song = absp(clip.get("song_path"))
    if not song or not song.is_file():
        raise ProductionError("Dépose d'abord le morceau dans le dossier du clip")
    lyrics_file = studio() / clip["dir"] / "script" / "paroles.md"
    lyrics = lyrics_file.read_text(encoding="utf-8") if lyrics_file.is_file() else ""

    import librosa
    import numpy as np
    from faster_whisper import WhisperModel

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "song.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(song), "-ac", "1", "-ar", "16000", str(wav)],
                       check=True)
        y, sr = librosa.load(str(wav), sr=16000)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
        wm = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=4)
        segs, _ = wm.transcribe(str(wav), language="en", word_timestamps=True, beam_size=5,
                                initial_prompt=lyrics[:800] or None)
        lines = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                  "words": [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for w in s.words]}
                 for s in segs]
    out = {"duration": round(float(len(y) / sr), 2), "tempo": round(float(np.atleast_1d(tempo)[0]), 1),
           "beats": [round(float(b), 3) for b in beats], "lines": lines}
    dest = studio() / clip["dir"] / "work" / "analyse.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    conn.execute("UPDATE clips SET bpm=?, updated_at=? WHERE slug=?", (out["tempo"], db.now(), slug))
    db.log_event(conn, slug, "analyse", f"Morceau analysé : {out['tempo']} BPM, {len(lines)} lignes de paroles placées")
    return {"path": str(dest), "tempo": out["tempo"], "lines": len(lines), "beats": len(out["beats"])}
