"""Plugin system (spec §13) — simple Hermes-style UX.

    loom plugin install owner/repo       # git clone + auto-detect + enable prompt
    loom plugin list                     # show installed plugins
    loom plugin remove <name>            # delete from ~/.loom/plugins/
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

LOOM_HOME = Path.home() / ".loom"
PLUGINS_DIR = LOOM_HOME / "plugins"


@dataclass
class PluginInfo:
    name: str = ""
    path: str = ""
    version: str = ""
    description: str = ""
    source: str = ""


def _resolve_repo(spec: str) -> tuple[str, str]:
    """Resolve owner/repo shorthand to a full Git URL."""
    spec = spec.removesuffix(".git")
    if "/" not in spec:
        raise ValueError(f"expected 'owner/repo' format, got {spec!r}")
    owner, repo = spec.split("/", 1)
    url = f"https://github.com/{owner}/{repo}.git"
    return url, repo


def install_plugin(spec: str) -> PluginInfo:
    """Install a plugin from GitHub (owner/repo shorthand or full URL)."""
    if spec.startswith("https://") or spec.startswith("git@"):
        url = spec
        repo = Path(spec).stem.removesuffix(".git")
    else:
        url, repo = _resolve_repo(spec)

    target = PLUGINS_DIR / repo
    if target.exists():
        raise FileExistsError(f"plugin {repo!r} is already installed at {target}")

    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", url, str(target)], check=True, capture_output=True
    )

    return PluginInfo(name=repo, path=str(target), source=spec)


def list_plugins() -> list[PluginInfo]:
    if not PLUGINS_DIR.exists():
        return []
    result = []
    for d in sorted(PLUGINS_DIR.iterdir()):
        if d.is_dir() and (d / ".git").exists():
            result.append(PluginInfo(name=d.name, path=str(d), source=""))
    return result


def remove_plugin(name: str) -> bool:
    target = PLUGINS_DIR / name
    if not target.exists():
        return False
    import shutil
    shutil.rmtree(target)
    return True
