#!/usr/bin/env python3
"""Test des trois modes de Veo 3.1 sur Vertex (brief du 11/11/2026).

Modes : références (referenceImages « asset », sans image clé), première + dernière
image (image + lastFrame), et témoin image vers vidéo (comme la chaîne aujourd'hui).

Ne touche ni à la base, ni à la config, ni à studio/clips/ : lit plan.json dans le
dossier du test, écrit tout dans ce dossier. Budget plafonné. Pas de relance
automatique, sauf deux cas prévus par le brief :
  - Fast refuse referenceImages (« not supported ») : ce seul appel repart en Standard ;
  - une image de référence refusée (code 15236754) : remplacée par la photo de secours
    de la même version, une fois.
Toute autre erreur arrête le script et affiche la réponse brute.

Usage : .venv/bin/python scripts/test_veo_modes.py [--only P1,P2] [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import sqlite3
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from riotmachine import media  # noqa: E402
from riotmachine.providers import vertex  # noqa: E402
from riotmachine.settings import get_settings  # noqa: E402

STUDIO = REPO / "studio"
OUT = STUDIO / "tests" / "veo-modes-2026-11-11"
BUDGET = 10.0
PRICE = {("veo-3.1-fast-generate-001", "720p"): 0.08, ("veo-3.1-fast-generate-001", "1080p"): 0.10,
         ("veo-3.1-generate-001", "720p"): 0.20, ("veo-3.1-generate-001", "1080p"): 0.20}
STANDARD = "veo-3.1-generate-001"
FACE_BACKUP = {"characters/jj/v2/canon.png": "characters/jj/v2/canon/tshirt-blanc-rousseur.png"}


def img_part(rel: str) -> dict:
    p = STUDIO / rel
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return {"bytesBase64Encoded": base64.b64encode(p.read_bytes()).decode(), "mimeType": mime}


def strip_b64(obj):
    """La requête ou la réponse sans les gros blocs base64, pour l'archive."""
    if isinstance(obj, dict):
        return {k: (f"<base64 {len(v)} car.>" if k == "bytesBase64Encoded" and isinstance(v, str) else strip_b64(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_b64(x) for x in obj]
    return obj


def params(p: dict) -> dict:
    return {"aspectRatio": "16:9", "durationSeconds": int(p["dur"]), "resolution": p["res"],
            "generateAudio": False, "sampleCount": 1, "personGeneration": "allow_adult",
            "negativePrompt": p["negative"]}


def build_body(key: str, p: dict) -> dict:
    inst: dict = {"prompt": p["prompt"]}
    if p["mode"] == "references":
        inst["referenceImages"] = [{"referenceType": "asset", "image": img_part(r)} for r in p["refs"]]
    elif p["mode"] == "first_last":
        inst["image"] = img_part(p["first_frame"])
        inst["lastFrame"] = img_part(p["last_frame"])
    elif p["mode"] == "image_to_video":
        inst["image"] = img_part(p["first_frame"])
    else:
        raise SystemExit(f"{key} : mode inconnu {p['mode']}")
    return {"instances": [inst], "parameters": params(p)}


def submit(model: str, body: dict) -> tuple[int, dict]:
    headers, query = vertex._auth()
    with httpx.Client(timeout=180) as c:
        r = c.post(vertex._model_url(model, "predictLongRunning"), headers=headers, params=query, json=body)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"raw": r.text[:2000]}


def poll(model: str, op: str) -> dict:
    headers, query = vertex._auth()
    with httpx.Client(timeout=300) as c:
        r = c.post(vertex._model_url(model, "fetchPredictOperation"), headers=headers, params=query,
                   json={"operationName": op})
    return r.json()


def err_text(x) -> str:
    return json.dumps(x, ensure_ascii=False)


def load_plan() -> dict:
    plan = json.loads((OUT / "plan.json").read_text())
    # témoin : le prompt et le négatif actuels du plan 5, tels que la chaîne les envoie
    conn = sqlite3.connect(f"file:{STUDIO / 'riot.db'}?mode=ro", uri=True)
    vp, neg = conn.execute("SELECT video_prompt, negative_prompt FROM shots WHERE clip_slug='nobody-saw' AND num=5").fetchone()
    plan["P5"]["prompt"], plan["P5"]["negative"] = vp, neg
    plan["P1b"] = {**plan["P1"], **{k: v for k, v in plan["P1b"].items() if k != "same_as"}}
    plan["P4"]["first_frame"] = str((OUT / "P4" / "premiere.png").relative_to(STUDIO))
    plan["P4"]["last_frame"] = str((OUT / "P4" / "derniere.png").relative_to(STUDIO))
    return plan


def make_p4_frames(p: dict) -> None:
    """Les deux images de P4 sur FLUX.2 klein 9B (Cloudflare, gratuit), mêmes références que le storyboard."""
    from riotmachine import image_models
    d = OUT / "P4"
    d.mkdir(parents=True, exist_ok=True)
    refs = [STUDIO / r for r in p["frames_refs"]]
    for name, prompt in (("premiere.png", p["first_frame_prompt"]), ("derniere.png", p["last_frame_prompt"])):
        if (d / name).exists():
            continue
        image_models.run_free("cloudflare:klein-9b", prompt, refs, d / name, 1280, 720)
        print(f"P4 : {name} faite")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="P1,P2,P3,P4,P5,P1b")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    get_settings()   # charge .env (clés Vertex et Cloudflare) sans l'afficher
    plan = load_plan()
    keys = [k.strip() for k in a.only.split(",") if k.strip()]
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"runs": {}}
    spent = sum(r.get("cost_usd", 0) for r in manifest["runs"].values())

    if "P4" in keys and not a.dry_run:
        try:
            make_p4_frames(plan["P4"])
        except Exception as exc:  # noqa: BLE001 - quota Cloudflare : P4 attend, le reste part
            print(f"P4 reporté : images non faites ({exc})")
            manifest["runs"]["P4"] = {"status": "reporté", "why": str(exc)[:300]}
            keys.remove("P4")

    jobs = {}
    for k in keys:
        p = plan[k]
        model = p["model"]
        cost = PRICE[(model, p["res"])] * p["dur"]
        if spent + cost > BUDGET:
            print(f"{k} : budget dépassé ({spent:.2f} + {cost:.2f} > {BUDGET}), arrêt")
            break
        if a.dry_run and p["mode"] == "first_last" and not (STUDIO / p["first_frame"]).exists():
            print(f"{k} : {p['mode']} sur {model}, {p['res']} {p['dur']} s, ~{cost:.2f} $ (à blanc, images pas encore faites)")
            continue
        body = build_body(k, p)
        d = OUT / k
        d.mkdir(parents=True, exist_ok=True)
        (d / "requete.json").write_text(json.dumps({"model": model, **strip_b64(body)}, ensure_ascii=False, indent=1))
        if a.dry_run:
            print(f"{k} : {p['mode']} sur {model}, {p['res']} {p['dur']} s, ~{cost:.2f} $ (à blanc)")
            continue
        notes = []
        for attempt in range(3):
            code, resp = submit(model, body)
            text = err_text(resp)
            if code < 300 and resp.get("name"):
                break
            if p["mode"] == "references" and "not supported" in text.lower() and model != STANDARD:
                notes.append(f"{model} refuse referenceImages : relancé en {STANDARD}")
                model = STANDARD
                cost = PRICE[(model, p["res"])] * p["dur"]
                if spent + cost > BUDGET:
                    print(f"{k} : budget dépassé pour la relance en Standard, arrêt")
                    return 1
                continue
            if "15236754" in text and p["mode"] == "references":
                swapped = False
                for i, r in enumerate(p["refs"]):
                    if r in FACE_BACKUP and FACE_BACKUP[r] not in p["refs"]:
                        notes.append(f"référence refusée (15236754) : {r} remplacée par {FACE_BACKUP[r]}")
                        p["refs"][i] = FACE_BACKUP[r]
                        swapped = True
                        break
                if swapped:
                    body = build_body(k, p)
                    continue
            print(f"{k} : erreur, arrêt. Réponse brute ({code}) :\n{text[:3000]}")
            (d / "reponse.json").write_text(json.dumps(strip_b64(resp), ensure_ascii=False, indent=1))
            manifest["runs"][k] = {"status": "erreur", "http": code, "notes": notes, "model": model}
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
            return 1
        jobs[k] = {"model": model, "op": resp["name"], "t0": time.time(), "cost": cost, "notes": notes,
                   "refs": p.get("refs"), "mode": p["mode"]}
        spent += cost   # compté dès la soumission, pour le plafond
        print(f"{k} : soumis sur {model}")

    while jobs:
        time.sleep(15)
        for k in list(jobs):
            j = jobs[k]
            op = poll(j["model"], j["op"])
            if not op.get("done"):
                if time.time() - j["t0"] > 900:
                    print(f"{k} : toujours en cours après 15 min, abandon du suivi")
                    manifest["runs"][k] = {"status": "trop long", "op": j["op"], "model": j["model"]}
                    del jobs[k]
                continue
            d = OUT / k
            (d / "reponse.json").write_text(json.dumps(strip_b64(op), ensure_ascii=False, indent=1))
            dt = round(time.time() - j["t0"])
            run = {"mode": j["mode"], "model": j["model"], "refs": j["refs"], "notes": j["notes"], "generation_s": dt}
            videos = (op.get("response") or {}).get("videos") or []
            if op.get("error") or not videos:
                run.update(status="refus", cost_usd=0.0, error=err_text(op.get("error") or op.get("response"))[:800])
                spent -= j["cost"]
                print(f"{k} : refusé ou vide, voir {d / 'reponse.json'}")
            else:
                mp4 = d / f"{k}.mp4"
                mp4.write_bytes(base64.b64decode(videos[0]["bytesBase64Encoded"]))
                frames = media.extract_frames(mp4, d / "images", 3)
                run.update(status="ok", cost_usd=round(j["cost"], 2), video=str(mp4.relative_to(OUT)),
                           frames=[str(f.relative_to(OUT)) for f in frames])
                print(f"{k} : vidéo reçue en {dt} s")
            manifest["runs"][k] = run
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
            del jobs[k]
    manifest["total_usd"] = round(sum(r.get("cost_usd", 0) for r in manifest["runs"].values()), 2)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"Total dépensé : {manifest['total_usd']} $")
    return 0


if __name__ == "__main__":
    sys.exit(main())
