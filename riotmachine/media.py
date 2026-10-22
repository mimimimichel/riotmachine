"""Outils ffmpeg : durée, vignettes, extraits audio, images clés, montage."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

SIZES = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (1080, 1080), "4:5": (1080, 1350)}


class MediaError(Exception):
    pass


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    if shutil.which(cmd[0]) is None:
        raise MediaError(f"{cmd[0]} introuvable : installe ffmpeg (sudo apt install ffmpeg)")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise MediaError(f"{' '.join(cmd[:3])}… a échoué : {proc.stderr[-800:]}")
    return proc


def duration(path: str | Path) -> float:
    proc = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path),
    ])
    return float(json.loads(proc.stdout)["format"]["duration"])


def is_video(path: str | Path) -> bool:
    return Path(path).suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}


def cut_audio(src: str | Path, start: float, end: float, dest: Path) -> Path:
    """Extrait le passage du morceau (ou de la piste voix) couvert par un plan."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
        "-i", str(src), "-ac", "2", "-ar", "44100", "-b:a", "192k", str(dest),
    ])
    return dest


def extract_frames(video: str | Path, dest_dir: Path, count: int = 3) -> list[Path]:
    """Images clés réparties sur la vidéo, pour que l'agent contrôle un draft."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    total = duration(video)
    frames = []
    for i in range(count):
        t = total * (i + 0.5) / count
        out = dest_dir / f"frame-{i + 1}.jpg"
        _run([
            "ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video),
            "-frames:v", "1", "-q:v", "3", str(out),
        ])
        frames.append(out)
    return frames


def thumbnail(src: str | Path, dest: Path, width: int = 640) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    if is_video(src):
        args += ["-ss", "0.5"]
    args += ["-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(dest)]
    _run(args)
    return dest


def assemble(segments: list[dict[str, Any]], song: str | Path | None, dest: Path,
             aspect: str = "16:9", song_offset: float = 0.0) -> Path:
    """Monte les plans bout à bout sur le morceau.

    segments : liste de {"path": fichier image ou vidéo, "seconds": durée du plan}.
    Les images fixes sont tenues à l'écran (animatique), les vidéos sont coupées
    à la durée du plan.
    """
    if not segments:
        raise MediaError("Aucun plan à monter")
    w, h = SIZES.get(aspect, SIZES["16:9"])
    work = dest.parent / f".{dest.stem}-parts"
    work.mkdir(parents=True, exist_ok=True)
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24,format=yuv420p")
    parts = []
    for i, seg in enumerate(segments):
        out = work / f"part-{i:03d}.mp4"
        secs = max(0.3, float(seg["seconds"]))
        if seg.get("path") and is_video(seg["path"]):
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(seg["path"]),
                   "-t", f"{secs:.3f}", "-an", "-vf", vf]
        elif seg.get("path"):
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(seg["path"]),
                   "-t", f"{secs:.3f}", "-vf", vf]
        else:
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                   "-i", f"color=c=black:s={w}x{h}:r=24", "-t", f"{secs:.3f}", "-vf", vf]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)]
        _run(cmd)
        parts.append(out)
    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    video_only = work / "video.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", str(listing), "-c", "copy", str(video_only)])
    dest.parent.mkdir(parents=True, exist_ok=True)
    if song:
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_only),
              "-ss", f"{song_offset:.3f}", "-i", str(song),
              "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
              "-shortest", str(dest)])
    else:
        shutil.copy(video_only, dest)
    shutil.rmtree(work, ignore_errors=True)
    return dest


TEXT_EXT = {".txt", ".md", ".markdown", ".srt", ".lrc", ".csv"}


def extract_text(path: Path) -> Path | None:
    """Version texte d'un document (pdf, docx, txt, md) pour que les agents la lisent.

    Écrit <fichier>.txt à côté de l'original et retourne son chemin, ou None si le
    fichier n'est pas un document (audio, image) ou si l'extraction échoue.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in TEXT_EXT:
        return path
    out = path.with_name(path.name + ".txt")
    try:
        if suffix == ".pdf":
            subprocess.run(["pdftotext", "-layout", str(path), str(out)], check=True, capture_output=True)
            return out if out.is_file() and out.stat().st_size else None
        if suffix == ".docx":
            import re
            import zipfile
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            xml = re.sub(r"</w:p>", "\n", xml)
            xml = re.sub(r"<w:tab/>", "\t", xml)
            text = re.sub(r"<[^>]+>", "", xml)
            import html
            out.write_text(html.unescape(text), encoding="utf-8")
            return out
    except (OSError, subprocess.CalledProcessError, KeyError, ValueError):
        return None
    return None


def waveform(path: str | Path, points: int = 1200) -> list[float]:
    """Enveloppe du morceau (valeurs 0..1) pour dessiner la forme d'onde dans la régie."""
    import array
    if shutil.which("ffmpeg") is None:
        raise MediaError("ffmpeg introuvable")
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "4000", "-f", "s16le", "-"],
                          capture_output=True)
    if proc.returncode != 0:
        raise MediaError(proc.stderr.decode(errors="ignore")[-400:])
    samples = array.array("h", proc.stdout)
    if not samples:
        return []
    step = max(1, len(samples) // points)
    peaks = [max(abs(x) for x in samples[i:i + step]) for i in range(0, len(samples), step)]
    top = max(peaks) or 1
    return [round(p / top, 3) for p in peaks]
