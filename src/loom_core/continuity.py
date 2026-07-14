"""Continuity protocol enforcement (spec §7).

At session start the sacred continuity files must exist. If any are missing the
guard reports them and can recreate a safe stub from a template (spec §7,
"Missing Continuity Files"). It also detects whether a session is a *recovery*
(memory already contains entries) for the value metrics (spec §8).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SACRED_FILES: tuple[str, ...] = (
    "PROGRESS.md",
    "TASKS.md",
    "CURRENT_FOCUS.md",
    "SESSION_LOG.md",
    "DECISIONS.md",
    "COMPLETED.md",
    "docs/LOOM_CORE_MASTER_SPEC.md",
)

_STUB = """# {name}

> AUTO-RECREATED STUB. The original continuity file was missing at session
> start and was recreated by the continuity guard (spec §7). Review and restore
> real content from git history or memory as soon as possible.
"""


@dataclass
class ContinuityReport:
    root: Path
    missing: list[str]
    recreated: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing


class ContinuityGuard:
    """Verify and, if asked, repair the sacred continuity files (spec §7)."""

    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root)

    def check(self) -> list[str]:
        """Return the list of missing sacred files (empty means healthy)."""
        return [rel for rel in SACRED_FILES if not (self.root / rel).exists()]

    def recreate_missing(self) -> ContinuityReport:
        """Recreate missing files from a stub template, logging the recovery."""
        missing = self.check()
        recreated: list[str] = []
        for rel in missing:
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                _STUB.format(name=Path(rel).name), encoding="utf-8", newline="\n"
            )
            recreated.append(rel)
        return ContinuityReport(root=self.root, missing=missing, recreated=recreated)
