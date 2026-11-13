"""Administration des fournisseurs depuis la régie : clés d'API et activation.

- Les clés vivent dans `.env` (droits 600). La régie les écrit, ne les relit jamais
  vers le navigateur : elle n'en montre que les 4 derniers caractères.
- Seules les variables déclarées par un fournisseur dans config/models.yaml
  (`env`, `env_any`) peuvent être écrites : la régie ne touche à rien d'autre.
- Un fournisseur désactivé garde ses clés mais n'est plus utilisé
  (liste dans RIOT_DISABLED_PROVIDERS).
- Le worker relit ces valeurs à chaque tour (`reload`) : pas de redémarrage.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .settings import REPO_ROOT

ENV_FILE = REPO_ROOT / ".env"
DISABLED = "RIOT_DISABLED_PROVIDERS"


class KeyError_(Exception):
    pass


def _providers_cfg() -> dict:
    from . import routing
    return routing.models_cfg().get("providers") or {}


def env_names(provider: str) -> list[str]:
    cfg = _providers_cfg().get(provider)
    if cfg is None:
        raise KeyError_(f"Fournisseur inconnu : {provider}")
    names = cfg.get("env") or []
    names = [names] if isinstance(names, str) else list(names)
    return names + list(cfg.get("env_any") or []) + list(cfg.get("env_optional") or [])


def managed_names() -> set[str]:
    out = {DISABLED}
    for p in _providers_cfg():
        out.update(env_names(p))
    return out


def _read() -> list[str]:
    return ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.is_file() else []


def _write(lines: list[str]) -> None:
    ENV_FILE.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    os.chmod(ENV_FILE, 0o600)


def _set_line(name: str, value: str | None) -> None:
    lines = [l for l in _read() if not re.match(rf"\s*{re.escape(name)}\s*=", l)]
    if value is not None:
        lines.append(f"{name}={value}")
    _write(lines)


def set_key(provider: str, name: str, value: str) -> None:
    if name not in env_names(provider):
        raise KeyError_(f"{name} n'est pas une clé de {provider}")
    value = value.strip()
    if not value or "\n" in value:
        raise KeyError_("Clé vide ou invalide")
    _set_line(name, value)
    os.environ[name] = value


def remove_key(provider: str, name: str) -> None:
    if name not in env_names(provider):
        raise KeyError_(f"{name} n'est pas une clé de {provider}")
    _set_line(name, None)
    os.environ.pop(name, None)


def disabled() -> set[str]:
    return {x.strip() for x in os.environ.get(DISABLED, "").split(",") if x.strip()}


def set_enabled(provider: str, enabled: bool) -> None:
    env_names(provider)   # vérifie que le fournisseur existe
    now = disabled()
    now = (now - {provider}) if enabled else (now | {provider})
    value = ",".join(sorted(now))
    _set_line(DISABLED, value or None)
    if value:
        os.environ[DISABLED] = value
    else:
        os.environ.pop(DISABLED, None)


def masked(name: str) -> str | None:
    v = os.environ.get(name, "").strip()
    if not v:
        return None
    return "••••" + v[-4:] if len(v) > 8 else "••••"


def reload() -> None:
    """Relit .env pour les variables gérées par la régie (ajout, changement, retrait)."""
    seen = {}
    for raw in _read():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        seen[k.strip()] = v.strip().strip('"').strip("'")
    for name in managed_names():
        if name in seen and seen[name]:
            os.environ[name] = seen[name]
        else:
            os.environ.pop(name, None)
