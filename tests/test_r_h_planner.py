"""Planificateur v3 (R-H3, R-H4, R-H5, R-H28) : fonction pure, une règle par test."""

import pytest

from riotmachine import catalogue as cat
from riotmachine import planner


def offer(key="o8", *, durs=(4, 6, 8), ref_durs=(8,), max_shots=3, cuts="approximate", price=0.1,
          provider="vertex", usable=True, profiles=None, refs=True):
    modes = {"text": {"durations": list(durs)}, "image_start": {"durations": list(durs)}}
    if refs:
        modes["references"] = {"durations": list(ref_durs), "max_refs": 3}
    return {"key": key, "label": key, "provider": provider, "provider_label": provider, "usable": usable,
            "prices": {"720p": price, "1080p": price * 2}, "resolutions": ["720p", "1080p"], "modes": modes,
            "multi_shot": {"max_shots": max_shots, "cuts": cuts} if max_shots > 1 else None,
            "profiles": profiles or {"decor": "ok", "action": "ok", "jeu": "weak"}, "dialect": "generic",
            "refusals_billed": False, "stale": False, "source": "test"}


def shot(i, a, b, chars=("jj",), **kw):
    return {"id": i, "num": i, "t_start": a, "t_end": b, "characters": list(chars), **kw}


def test_r_h4_same_input_same_output():
    shots = [shot(1, 0, 3), shot(2, 3, 5.5), shot(3, 5.5, 9)]
    o = offer()
    assert planner.plan_sequence(shots, o) == planner.plan_sequence(list(reversed(shots)), o)


def test_r_h4_twelve_seconds_two_takes_at_8_one_at_15():
    shots = [shot(1, 0, 4), shot(2, 4, 8), shot(3, 8, 12)]
    p8 = planner.plan_sequence(shots, offer(ref_durs=(8,), cuts="fixed"))
    assert len(p8["takes"]) == 2
    p15 = planner.plan_sequence(shots, offer("o15", ref_durs=tuple(range(3, 16)), cuts="fixed", max_shots=6))
    assert len(p15["takes"]) == 1 and p15["takes"][0]["duration_s"] == 12


def test_r_h4_multi_shot_margin_on_approximate_cuts():
    # 3 + 4 = 7 s, + 0,5 s de marge = 7,5 s : tient en 8 s
    p = planner.plan_sequence([shot(1, 0, 3), shot(2, 3, 7)], offer())
    (t,) = p["takes"]
    assert t["form"] == "multi" and t["duration_s"] == 8
    assert t["shots"][1]["t_in"] == 3.5
    # 4 + 4 = 8 s + 0,5 : ne tient plus, deux prises
    assert len(planner.plan_sequence([shot(1, 0, 4), shot(2, 4, 8)], offer())["takes"]) == 2


def test_r_h4_non_contiguous_shots_not_grouped():
    p = planner.plan_sequence([shot(1, 0, 3), shot(2, 10, 12)], offer())
    assert [t["form"] for t in p["takes"]] == ["single", "single"]


def test_r_h4_same_axis_continuous():
    p = planner.plan_sequence([shot(1, 0, 4, axe="A"), shot(2, 4, 8, axe="A")], offer())
    (t,) = p["takes"]
    assert t["form"] == "continuous" and t["shots"][1]["t_in"] == 4


def test_r_h4_acting_or_close_singing_alone():
    shots = [shot(1, 0, 2), shot(2, 2, 4, jeu="porteur"), shot(3, 4, 6, singing=1, framing="CU")]
    p = planner.plan_sequence(shots, offer())
    assert [len(t["shots"]) for t in p["takes"]] == [1, 1, 1]


def test_r_h4_smallest_duration_and_unused_alert():
    p = planner.plan_sequence([shot(1, 0, 3, chars=())], offer(), options={"mode": "text"})
    (t,) = p["takes"]
    assert t["duration_s"] == 4 and not t["alerts"]
    p = planner.plan_sequence([shot(1, 0, 3)], offer())   # références : 8 s seulement
    assert p["takes"][0]["duration_s"] == 8
    assert any(a["kind"] == "unused" for a in p["takes"][0]["alerts"])


def test_r_h4_too_long_blocks_with_explanation():
    p = planner.plan_sequence([shot(1, 0, 9)], offer())
    assert p["blocking"]
    (a,) = [a for a in p["takes"][0]["alerts"] if a["kind"] == "too_long"]
    assert "recouper" in a["text"] and a["shot_id"] == 1


def test_r_h4_resolution_by_quality():
    o = offer()
    assert planner.plan_sequence([shot(1, 0, 3)], o, quality="brouillon")["resolution"] == "720p"
    assert planner.plan_sequence([shot(1, 0, 3)], o, quality="final")["resolution"] == "1080p"
    p = planner.plan_sequence([shot(1, 0, 3)], o, options={"resolution": "1080p"})
    assert p["resolution"] == "1080p" and p["total_usd"] == 1.6


def test_r_h5_payment_order_reserve_first():
    shots = [shot(1, 0, 3)]
    reserve = {"vertex": {"remaining": 100, "label": "crédits Google"}}
    cheap_cash = offer("cash", provider="fal", price=0.05)
    pricey_reserve = offer("res", provider="vertex", price=0.2)
    ranked = planner.candidates(shots, [cheap_cash, pricey_reserve], reserves=reserve)
    assert ranked[0]["offer"] == "res" and ranked[0]["funding"] == "reserve:vertex"
    # sans réserve : le moins cher
    ranked = planner.candidates(shots, [cheap_cash, pricey_reserve], reserves={})
    assert ranked[0]["offer"] == "cash"


def test_r_h5_weak_offer_never_default():
    shots = [shot(1, 0, 3, jeu="porteur")]
    weak = offer("weak", price=0.05, profiles={"jeu": "weak"})
    ok = offer("ok", price=0.2, profiles={"jeu": "ok"})
    ranked = planner.candidates(shots, [weak, ok], reserves={})
    assert ranked[0]["offer"] == "ok"
    assert any(w["kind"] == "profile_weak" for w in ranked[1]["warnings"])


def test_r_h28_missing_capability_warns():
    p = planner.plan_sequence([shot(1, 0, 3)], offer(refs=False))
    assert p["mode"] == "text"
    assert any(w["kind"] == "no_refs" for w in p["warnings"])
    p = planner.plan_sequence([shot(1, 0, 3)], offer(usable=False))
    assert p["blocking"] and any(w["kind"] == "not_connected" for w in p["warnings"])


def test_d35_impact_before_change():
    shots = [shot(1, 0, 4), shot(2, 4, 8), shot(3, 8, 17)]
    cur = planner.plan_sequence(shots, offer("o15", ref_durs=tuple(range(3, 16)), cuts="fixed", max_shots=6))
    alt = planner.plan_sequence(shots, offer("o8"))
    lines = planner.impact(cur, alt, shot_taken={1: "o15"})
    assert any(l.startswith("Coût") for l in lines)
    assert any("recouper" in l and "plan 3" in l for l in lines)
    assert any("retourner" in l for l in lines)


def test_r_h3_catalogue_from_yaml_only(studio, tmp_path, monkeypatch):
    """Un modèle ajouté aux fichiers de configuration devient proposable sans toucher au Python."""
    import shutil
    import yaml
    from riotmachine import settings
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    models = yaml.safe_load((settings.REPO_ROOT / "config" / "models.yaml").read_text())
    models["models"]["fictif-1"] = {"label": "Fictif", "provider": "vertex", "kind": "video",
                                    "durations": [5, 10], "price": {"per_second": {"720p": 0.01}}}
    (repo / "config" / "models.yaml").write_text(yaml.safe_dump(models, allow_unicode=True))
    caps = yaml.safe_load((settings.REPO_ROOT / "config" / "capacites.yaml").read_text())
    caps["models"]["fictif-1"] = {"modes": {"references": {"durations": [5, 10], "max_refs": 2}},
                                  "profiles": {"action": "ok"}}
    (repo / "config" / "capacites.yaml").write_text(yaml.safe_dump(caps, allow_unicode=True))
    monkeypatch.setenv("RIOT_MODELS", str(repo / "config" / "models.yaml"))
    monkeypatch.setattr(settings, "REPO_ROOT", repo)
    settings.reset_caches()
    cat.reset()
    try:
        o = cat.offer("fictif-1")
        assert o["modes"]["references"]["max_refs"] == 2
        p = planner.plan_sequence([shot(1, 0, 4)], o)
        assert p["takes"][0]["duration_s"] == 5 and p["total_usd"] == 0.05
    finally:
        cat.reset()
