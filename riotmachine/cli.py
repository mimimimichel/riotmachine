"""CLI `riot` : la boîte à outils de l'orchestrateur et des agents.

Toutes les commandes qui servent aux agents renvoient du JSON.
Lance `riot --help` ou `riot <commande> --help` pour le détail.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import db, fal, media, notify, production, routing, worker
from .settings import get_settings


def out(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _conn():
    conn = db.connect()
    db.init_db(conn)
    return conn


# --- commandes ------------------------------------------------------------------

def cmd_init(a) -> None:
    s = get_settings()
    for d in (s.characters_dir, s.clips_dir, s.groups_dir, s.logs_dir):
        d.mkdir(parents=True, exist_ok=True)
    conn = _conn()
    added = production.sync_character_files(conn)
    chars = [dict(r) for r in conn.execute("SELECT slug, name, canon_version FROM characters").fetchall()]
    out({"studio": str(s.studio_root), "db": str(s.db_path), "fal": "simulation" if s.fal_mock else "réel",
         "telegram": notify.telegram_configured(), "images_referencees": added, "personnages": chars})


def cmd_status(a) -> None:
    conn = _conn()
    if a.clip:
        snap = production.clip_snapshot(conn, a.clip, compact=True)
        if a.json:
            out(snap)
            return
        print(f"{snap['title']} [{snap['slug']}] — étape {snap['stage']} — {snap['cost_usd']:.2f} $"
              f" / {snap.get('budget_usd') or '∞'} $")
        for s in snap["shots"]:
            print(f"  #{s['num']:>3} {s['t_start']:>6.1f}-{s['t_end']:<6.1f} {s['status']:<16} "
                  f"{(s.get('tier') or '-'):<8} {s['description'][:60]}")
        if snap["needs_agent"]:
            print("À faire par les agents : " + " | ".join(snap["needs_agent"]))
        return
    clips = db.rows(conn.execute("SELECT slug, title, stage FROM clips ORDER BY updated_at DESC").fetchall())
    for c in clips:
        c["cost_usd"] = round(db.clip_cost(conn, c["slug"]), 2)
        c["needs_agent"] = production.needs_agent(conn, c["slug"])["reasons"]
    jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
    data = {"clips": clips, "generations_en_cours": jobs}
    if a.json:
        out(data)
    else:
        for c in clips:
            print(f"{c['slug']:<28} {c['stage']:<18} {c['cost_usd']:>7.2f} $  {', '.join(c['needs_agent'])}")
        print(f"Générations en cours : {jobs}")


def cmd_clip_new(a) -> None:
    conn = _conn()
    clip = production.create_clip(
        conn, a.title, slug=a.slug, song=a.song, vocals=a.vocals, script_file=a.script, bpm=a.bpm,
        aspect=a.aspect, budget_usd=a.budget, characters=a.characters or [], pitch=a.pitch,
        concept=a.concept, dossier=a.dossier or [], lyrics_files=a.lyrics or [],
    )
    out(clip)


def cmd_clip_show(a) -> None:
    out(production.clip_snapshot(_conn(), a.clip, compact=not a.full))


def cmd_clip_stage(a) -> None:
    conn = _conn()
    production.set_stage(conn, a.clip, a.stage)
    out({"clip": a.clip, "stage": a.stage})


def cmd_clip_budget(a) -> None:
    conn = _conn()
    conn.execute("UPDATE clips SET budget_usd=?, updated_at=? WHERE slug=?", (a.usd, db.now(), a.clip))
    out({"clip": a.clip, "budget_usd": a.usd})


def cmd_casting(a) -> None:
    conn = _conn()
    production.set_casting(conn, a.clip, a.character, a.version, a.look)
    out(db.casting_for_clip(conn, a.clip))


def cmd_shots_import(a) -> None:
    conn = _conn()
    data = json.loads(Path(a.file).read_text(encoding="utf-8"))
    n = production.import_shots(conn, a.clip, data)
    out({"clip": a.clip, "plans_importes": n})


def cmd_shot_show(a) -> None:
    conn = _conn()
    shot = db.get_shot(conn, a.shot)
    view = production.shot_view(conn, shot)
    clip = db.get_clip(conn, shot["clip_slug"])
    casting = {c["character_slug"]: c for c in db.casting_for_clip(conn, clip["slug"])}
    view["casting"] = []
    for c in shot["characters"]:
        if c in casting:
            cv = casting[c]
            view["casting"].append({
                "character": c, "version": cv["version"], "look": cv["look_slug"],
                "refs": [production.rel(p) for p in production.character_refs(conn, c, cv["version"], cv["look_slug"])],
                "adn": production.adn_text(conn, c, cv["version"]),
            })
    view["aspect_ratio"] = clip["aspect_ratio"]
    out(view)


def cmd_shot_set(a) -> None:
    conn = _conn()
    fields = {k: getattr(a, k) for k in production.SETTABLE if hasattr(a, k)}
    if a.characters is not None:
        fields["characters"] = [c.strip() for c in a.characters.split(",") if c.strip()]
    for name in ("image_prompt", "video_prompt"):
        file_arg = getattr(a, f"{name}_file", None)
        if file_arg:
            fields[name] = Path(file_arg).read_text(encoding="utf-8").strip()
    out(production.update_shot(conn, a.shot, **fields))


def cmd_shot_status(a) -> None:
    conn = _conn()
    db.set_shot_status(conn, a.shot, a.status)
    out({"shot": a.shot, "status": a.status})


def cmd_shot_submit(a) -> None:
    out(production.submit_video_plan(_conn(), a.shot))


def cmd_shot_retry(a) -> None:
    out({"shot": a.shot, "status": production.retry_failed(_conn(), a.shot)})


def cmd_route(a) -> None:
    conn = _conn()
    shot = db.get_shot(conn, a.shot)
    shot["aspect_ratio"] = db.get_clip(conn, shot["clip_slug"])["aspect_ratio"]
    tier = a.tier or (shot.get("tier") if a.keep_tier else None)
    res = routing.route_shot(shot, force_tier=None if a.model else tier, model_key=a.model)
    prov = res["provider"]
    if not routing.provider_usable(prov):
        raise ValueError(f"Le fournisseur {prov} n'est pas branché : choisis un modèle d'un fournisseur disponible")
    if a.apply:
        production.update_shot(conn, a.shot, tier=res["tier"], model_key=res["model_key"],
                               route_reason=a.why or res["why"])
        res["applied"] = True
    out(res)


def cmd_rodage(a) -> None:
    out(production.rodage(_conn(), a.model))


def cmd_analyse(a) -> None:
    from . import analyse
    out(analyse.analyse_song(_conn(), a.clip, a.model))


def cmd_providers(a) -> None:
    out({"fournisseurs": routing.providers(), "modeles_video": routing.video_models()})


def cmd_gen(a) -> None:
    conn = _conn()
    launcher = {"image": production.launch_image, "hd": production.launch_image_hd,
                "draft": production.launch_draft,
                "final": production.launch_final, "lipsync": production.launch_lipsync}[a.kind]
    out(launcher(conn, a.shot, force=a.force))


def cmd_qc(a) -> None:
    conn = _conn()
    if a.action == "frames":
        out({"frames": production.qc_frames(conn, a.shot)})
        return
    status = production.qc_result(conn, a.shot, a.action == "pass", a.note or "")
    out({"shot": a.shot, "status": status})


def cmd_review(a) -> None:
    conn = _conn()
    if a.action == "list":
        q = "SELECT * FROM reviews WHERE 1=1"
        params: list = []
        if a.clip:
            q += " AND clip_slug=?"
            params.append(a.clip)
        if not a.all:
            q += " AND handled=0 AND decision='change'"
        out(db.rows(conn.execute(q + " ORDER BY id", params).fetchall()))
    elif a.action == "handle":
        out(production.handle_review(conn, a.id, a.route, a.note or ""))


def cmd_decide(a) -> None:
    """Décisions de Michael en ligne de commande (normalement via la régie)."""
    conn = _conn()
    if a.target == "decoupage":
        production.review_decoupage(conn, a.id, a.decision, a.comment or "")
        out({"clip": a.id, "decision": a.decision})
    else:
        out({"shot": int(a.id), "status": production.review_shot(conn, int(a.id), a.decision, a.comment or "")})


def cmd_character(a) -> None:
    conn = _conn()
    if a.action == "list":
        out(db.rows(conn.execute("SELECT * FROM characters ORDER BY slug").fetchall()))
    elif a.action == "new":
        out(production.create_character(conn, a.slug, a.name or a.slug.upper()))
    elif a.action == "show":
        out(production.character_snapshot(conn, a.slug))
    elif a.action == "version":
        out(production.new_character_version(conn, a.slug, a.notes or ""))
    elif a.action == "sync":
        out({"ajoutees": production.sync_character_files(conn, a.slug)})
    elif a.action == "gen":
        out(production.launch_character_asset(conn, a.slug, a.version, a.kind, a.label, a.prompt
                                              or Path(a.prompt_file).read_text(encoding="utf-8"),
                                              a.ref, a.model))
    elif a.action == "pick":
        production.review_character_asset(conn, a.asset, a.decision)
        out({"asset": a.asset, "decision": a.decision})
    elif a.action == "validate":
        production.validate_character_version(conn, a.slug, a.version)
        out({"character": a.slug, "canon_version": a.version})
    elif a.action == "pack-done":
        production.pack_done(conn, a.slug, a.version)
        out({"character": a.slug, "version": a.version, "pack": "done"})


def cmd_model(a) -> None:
    if a.key:
        out(routing.model(a.key))
    else:
        cfg = routing.models_cfg()
        out({"tiers": cfg["tiers"], "image": cfg["image"], "lipsync": cfg["lipsync"], "upscale": cfg["upscale"],
             "modeles": {k: {"kind": v["kind"], "endpoint": v["endpoint"]} for k, v in cfg["models"].items()}})


def cmd_assemble(a) -> None:
    path = production.assemble_clip(_conn(), a.clip)
    out({"montage": production.rel(path)})


def cmd_notify(a) -> None:
    out({"envoye": notify.send(a.text)})


def cmd_cost(a) -> None:
    conn = _conn()
    rows = db.rows(conn.execute(
        "SELECT s.num, a.kind, a.version, a.model_key, a.cost_usd, a.status FROM assets a "
        "JOIN shots s ON s.id=a.shot_id WHERE s.clip_slug=? ORDER BY s.num, a.kind, a.version", (a.clip,)
    ).fetchall())
    out({"clip": a.clip, "total_usd": round(sum(r["cost_usd"] for r in rows), 3), "detail": rows})


def cmd_events(a) -> None:
    conn = _conn()
    q = "SELECT * FROM events" + (" WHERE clip_slug=?" if a.clip else "") + " ORDER BY id DESC LIMIT ?"
    params = ([a.clip] if a.clip else []) + [a.limit]
    out(db.rows(conn.execute(q, params).fetchall()))


def cmd_backup(a) -> None:
    """Copie la base (à chaud, sans risque) et le studio vers un autre disque."""
    import shutil
    import sqlite3
    import subprocess

    s = get_settings()
    dest = Path(a.dest).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    db_copy = dest / "riot.db"
    src = db.connect()
    target = sqlite3.connect(db_copy)
    with target:
        src.backup(target)
    target.close()
    excludes = ["riot.db", "riot.db-wal", "riot.db-shm", "work/", ".frames-*", "logs/", "*.part"]
    if shutil.which("rsync"):
        cmd = ["rsync", "-a", *[f"--exclude={e}" for e in excludes], f"{s.studio_root}/", f"{dest}/studio/"]
        subprocess.run(cmd, check=True)
    else:
        shutil.copytree(s.studio_root, dest / "studio", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("riot.db*", "work", ".frames-*", "logs", "*.part"))
    out({"sauvegarde": str(dest), "base": str(db_copy)})


def cmd_demo(a) -> None:
    from . import demo
    conn = _conn()
    if a.reset:
        demo.reset(conn)
        out({"demo": "supprimé"})
        return
    slug = demo.create(conn)
    out({"demo": slug, "regie": notify.regie_link(f"#/clip/{slug}")})


def cmd_worker(a) -> None:
    if a.once:
        with db.session() as conn:
            out(worker.tick(conn, wake=not a.no_agents))
        return
    worker.run_forever()


def cmd_regie(a) -> None:
    import uvicorn
    s = get_settings()
    uvicorn.run("riotmachine.regie.app:app", host=a.host or s.regie_host, port=a.port or s.regie_port,
                log_level="warning")


# --- parseur --------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="riot", description="Riot Machine — studio de clips IA")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="Crée la base et référence les personnages de studio/characters")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("status", help="Vue d'ensemble, ou d'un clip")
    sp.add_argument("clip", nargs="?")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_status)

    clip = sub.add_parser("clip", help="Gestion des clips").add_subparsers(dest="action", required=True)
    sp = clip.add_parser("new", help="Nouveau clip")
    sp.add_argument("title")
    sp.add_argument("--slug")
    sp.add_argument("--song", help="Morceau (mp3/wav)")
    sp.add_argument("--vocals", help="Piste voix isolée (stem Suno) pour le lip-sync")
    sp.add_argument("--script", help="Fichier texte/markdown du script ou des paroles")
    sp.add_argument("--bpm", type=float)
    sp.add_argument("--aspect", default="16:9", choices=["16:9", "9:16", "1:1", "4:5"])
    sp.add_argument("--budget", type=float, help="Budget en dollars")
    sp.add_argument("--characters", nargs="*", help="Personnages castés (version canon)")
    sp.add_argument("--pitch", help="Le pitch du clip en une ou deux phrases")
    sp.add_argument("--concept", help="Le concept du clip")
    sp.add_argument("--dossier", nargs="*", help="Dossier de réalisation : DA, storytelling, plans (pdf, docx, md, images)")
    sp.add_argument("--lyrics", nargs="*", help="Fichier(s) de paroles")
    sp.set_defaults(func=cmd_clip_new)
    sp = clip.add_parser("show", help="État complet d'un clip (JSON)")
    sp.add_argument("clip")
    sp.add_argument("--full", action="store_true", help="Inclure toutes les versions et retours")
    sp.set_defaults(func=cmd_clip_show)
    sp = clip.add_parser("stage", help="Change l'étape d'un clip")
    sp.add_argument("clip")
    sp.add_argument("stage", choices=db.CLIP_STAGES)
    sp.set_defaults(func=cmd_clip_stage)
    sp = clip.add_parser("budget", help="Fixe le budget d'un clip (dollars)")
    sp.add_argument("clip")
    sp.add_argument("usd", type=float)
    sp.set_defaults(func=cmd_clip_budget)

    sp = sub.add_parser("casting", help="Associe un personnage (version + look) à un clip")
    sp.add_argument("clip")
    sp.add_argument("character")
    sp.add_argument("--version", type=int)
    sp.add_argument("--look")
    sp.set_defaults(func=cmd_casting)

    shots = sub.add_parser("shots", help="Découpage").add_subparsers(dest="action", required=True)
    sp = shots.add_parser("import", help="Importe un découpage JSON (remplace l'existant)")
    sp.add_argument("clip")
    sp.add_argument("file")
    sp.set_defaults(func=cmd_shots_import)

    shot = sub.add_parser("shot", help="Un plan").add_subparsers(dest="action", required=True)
    sp = shot.add_parser("show", help="Tout sur un plan, avec les références du casting")
    sp.add_argument("shot", type=int)
    sp.set_defaults(func=cmd_shot_show)
    sp = shot.add_parser("set", help="Modifie un plan")
    sp.add_argument("shot", type=int)
    for f in ("section", "description", "camera", "image_prompt", "video_prompt", "negative_prompt", "notes",
              "tier", "model_key"):
        sp.add_argument(f"--{f.replace('_', '-')}", dest=f)
    sp.add_argument("--model", dest="model_key")
    sp.add_argument("--framing", choices=db.FRAMINGS)
    sp.add_argument("--motion", choices=db.MOTIONS)
    sp.add_argument("--characters", help="slugs séparés par des virgules")
    sp.add_argument("--singing", choices=["oui", "non"])
    sp.add_argument("--seed", type=int)
    sp.add_argument("--t-start", dest="t_start", type=float)
    sp.add_argument("--t-end", dest="t_end", type=float)
    sp.add_argument("--image-prompt-file")
    sp.add_argument("--video-prompt-file")
    sp.set_defaults(func=cmd_shot_set)
    sp = shot.add_parser("status", help="Force le statut d'un plan (à éviter)")
    sp.add_argument("shot", type=int)
    sp.add_argument("status", choices=db.SHOT_STATUSES)
    sp.set_defaults(func=cmd_shot_status)
    sp = shot.add_parser("submit", help="Présente le plan vidéo (modèle + prompt + coût) à Michael")
    sp.add_argument("shot", type=int)
    sp.set_defaults(func=cmd_shot_submit)

    sp = shot.add_parser("retry", help="Relance un plan en échec à l'étape qui a échoué")
    sp.add_argument("shot", type=int)
    sp.set_defaults(func=cmd_shot_retry)

    sp = sub.add_parser("route", help="Choisit palier et modèle d'un plan")
    sp.add_argument("shot", type=int)
    sp.add_argument("--tier", choices=["eco", "standard", "premium"], help="Force un palier")
    sp.add_argument("--keep-tier", action="store_true", help="Garde le palier déjà enregistré")
    sp.add_argument("--model", help="Choisit un modèle précis de config/models.yaml")
    sp.add_argument("--why", help="Raison du choix, montrée à Michael")
    sp.add_argument("--apply", action="store_true")
    sp.set_defaults(func=cmd_route)

    sp = sub.add_parser("gen", help="Lance une génération")
    sp.add_argument("kind", choices=["image", "hd", "draft", "final", "lipsync"])
    sp.add_argument("shot", type=int)
    sp.add_argument("--force", action="store_true", help="Ignore le budget")
    sp.set_defaults(func=cmd_gen)

    sp = sub.add_parser("qc", help="Contrôle qualité d'un plan par l'agent")
    sp.add_argument("action", choices=["pass", "fail", "frames"])
    sp.add_argument("shot", type=int)
    sp.add_argument("--note")
    sp.set_defaults(func=cmd_qc)

    sp = sub.add_parser("review", help="Retours de Michael")
    sp.add_argument("action", choices=["list", "handle"])
    sp.add_argument("id", type=int, nargs="?")
    sp.add_argument("--clip")
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--route", choices=list(production.ROUTES))
    sp.add_argument("--note")
    sp.set_defaults(func=cmd_review)

    sp = sub.add_parser("decide", help="Décision de Michael (sinon : la régie)")
    sp.add_argument("target", choices=["decoupage", "shot"])
    sp.add_argument("id", help="slug du clip (découpage) ou id du plan")
    sp.add_argument("decision", choices=["approve", "change", "use_work_image"])
    sp.add_argument("--comment")
    sp.set_defaults(func=cmd_decide)

    sp = sub.add_parser("character", help="Référentiel des personnages")
    sp.add_argument("action", choices=["list", "new", "show", "version", "sync", "gen", "pick", "validate",
                                       "pack-done"])
    sp.add_argument("slug", nargs="?")
    sp.add_argument("--name")
    sp.add_argument("--notes")
    sp.add_argument("--version", type=int)
    sp.add_argument("--kind", choices=["turnaround", "fullbody", "expressions", "lighting", "details", "canon"])
    sp.add_argument("--label")
    sp.add_argument("--prompt")
    sp.add_argument("--prompt-file")
    sp.add_argument("--ref", action="append", help="Image de référence (chemin dans studio/), répétable")
    sp.add_argument("--model")
    sp.add_argument("--asset", type=int)
    sp.add_argument("--decision", choices=["keep", "reject", "canon"])
    sp.set_defaults(func=cmd_character)

    sp = sub.add_parser("rodage", help="Carnet de rodage : ce que l'historique dit de chaque modèle vidéo")
    sp.add_argument("--model")
    sp.set_defaults(func=cmd_rodage)

    sp = sub.add_parser("analyse", help="Analyse le morceau (tempo, temps, position des paroles) pour caler le découpage")
    sp.add_argument("clip")
    sp.add_argument("--model", default="small", help="Modèle Whisper (base, small)")
    sp.set_defaults(func=cmd_analyse)

    sp = sub.add_parser("providers", help="Fournisseurs vidéo branchés et modèles disponibles")
    sp.set_defaults(func=cmd_providers)

    sp = sub.add_parser("model", help="Config d'un modèle (dont son guide de prompt), ou la liste")
    sp.add_argument("key", nargs="?")
    sp.set_defaults(func=cmd_model)

    sp = sub.add_parser("assemble", help="Monte le clip sur le morceau (meilleure version de chaque plan)")
    sp.add_argument("clip")
    sp.set_defaults(func=cmd_assemble)

    sp = sub.add_parser("notify", help="Envoie un message Telegram à Michael")
    sp.add_argument("text")
    sp.set_defaults(func=cmd_notify)

    sp = sub.add_parser("cost", help="Coûts d'un clip")
    sp.add_argument("clip")
    sp.set_defaults(func=cmd_cost)

    sp = sub.add_parser("events", help="Journal")
    sp.add_argument("--clip")
    sp.add_argument("--limit", type=int, default=30)
    sp.set_defaults(func=cmd_events)

    sp = sub.add_parser("backup", help="Sauvegarde la base et le studio vers un dossier (disque externe…)")
    sp.add_argument("dest")
    sp.set_defaults(func=cmd_backup)

    sp = sub.add_parser("demo", help="Crée un clip de démonstration simulé pour découvrir la régie")
    sp.add_argument("--reset", action="store_true", help="Supprime le clip de démo")
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser("worker", help="Boucle de production (service)")
    sp.add_argument("--once", action="store_true", help="Un seul tour")
    sp.add_argument("--no-agents", action="store_true", help="Ne réveille pas Claude Code")
    sp.set_defaults(func=cmd_worker)

    sp = sub.add_parser("regie", help="Lance la régie web")
    sp.add_argument("--host")
    sp.add_argument("--port", type=int)
    sp.set_defaults(func=cmd_regie)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (production.ProductionError, routing.RoutingError, fal.FalError, media.MediaError,
            LookupError, ValueError) as exc:
        out({"erreur": str(exc)})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
