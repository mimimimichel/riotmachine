"""R-G2 : crochet de pré-commit en place, et un test nommé par exigence livrée."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_r_g2_crochet_pre_commit():
    hook = REPO / "deploy" / "hooks" / "pre-commit"
    assert hook.is_file() and hook.stat().st_mode & 0o111
    text = hook.read_text()
    assert "pytest" in text and "exit 1" in text
    assert "SKIP" not in text                                   # pas de porte de sortie
    installer = REPO / "deploy" / "install-hooks.sh"
    assert installer.is_file()
    installed = REPO / ".git" / "hooks" / "pre-commit"
    if installed.exists():                                      # installé par install-hooks.sh (D24)
        assert installed.resolve() == hook.resolve()


def test_r_g2_chaque_exigence_livree_a_son_test():
    log = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    v3 = log.split("## v1", 1)[0]                               # seule la partie v3 compte
    delivered = set(re.findall(r"\bR-([A-Z]\d+)\b", v3))
    tests = "\n".join(p.read_text(encoding="utf-8") for p in (REPO / "tests").glob("test_*.py"))
    missing = sorted(i for i in delivered if not re.search(rf"def test_r_{i.lower()}_", tests))
    assert delivered, "le CHANGELOG v3 ne cite aucune exigence"
    assert not missing, f"exigences livrées sans test nommé : {missing}"
