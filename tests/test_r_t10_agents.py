"""R-T10 : aucun agent n'écrit dans riot.db, config/ ni .env ; les agents n'agissent que par la CLI."""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_r_t10_permissions_des_agents():
    cfg = json.loads((REPO / "config" / "agents-permissions.json").read_text(encoding="utf-8"))
    allow, deny = cfg["permissions"]["allow"], set(cfg["permissions"]["deny"])
    assert {"Write", "Edit", "NotebookEdit"} <= deny                  # aucun outil d'écriture de fichier
    for path in ("studio/riot*.db*", "config/**", ".env"):
        assert f"Write({path})" in deny and f"Edit({path})" in deny
    assert "Read(.env)" in deny and "Bash(sqlite3 *)" in deny
    assert not [a for a in allow if a.startswith(("Write", "Edit"))]
    bash = [a for a in allow if a.startswith("Bash(")]
    assert "Bash(riot *)" in bash and all(a in ("Bash(riot *)", "Bash(ffprobe *)") for a in bash)


def test_r_t10_aucune_permission_de_developpement_ne_vise_les_agents():
    """L'ancien .claude/settings.json (agents v1, Write(studio/**)) n'est plus actif (D18)."""
    old = REPO / ".claude" / "settings.json"
    if old.exists():
        text = old.read_text(encoding="utf-8")
        assert "Write(studio/**)" not in text and "Edit(studio/**)" not in text
