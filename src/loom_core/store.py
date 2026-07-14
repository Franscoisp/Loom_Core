"""Reading, writing, listing and searching memory entries (TASK-011..013).

Writes are atomic (write to a temp file in the same directory, then
``os.replace``) so a crash never leaves a half-written entry. Files are
Markdown with YAML frontmatter, field order preserved for human readability.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import frontmatter
import yaml

from loom_core.models import BaseEntry, parse_entry
from loom_core.paths import path_for, resolve_data_dir


@dataclass(frozen=True)
class LoadedEntry:
    """An entry plus where it lives and its Markdown body."""

    entry: BaseEntry
    body: str
    path: Path


def _dump_frontmatter(entry: BaseEntry, body: str) -> str:
    metadata = entry.model_dump(mode="json")
    yaml_text = yaml.safe_dump(
        metadata,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    body = body.rstrip("\n")
    return f"---\n{yaml_text}---\n\n{body}\n" if body else f"---\n{yaml_text}---\n"


class MemoryStore:
    """Filesystem-backed store for Loom memory entries."""

    def __init__(self, data_dir: str | os.PathLike[str] | None = None) -> None:
        self.data_dir = resolve_data_dir(data_dir)

    # --- writing (TASK-011) -------------------------------------------------

    def write(self, entry: BaseEntry, body: str = "") -> Path:
        """Atomically write an entry. Re-validates before touching disk."""
        entry = parse_entry(entry.model_dump(mode="json"))
        target = path_for(entry, self.data_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        content = _dump_frontmatter(entry, body)

        fd, tmp_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.stem}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, target)
        except BaseException:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
            raise
        return target

    # --- reading (TASK-012) -------------------------------------------------

    def read(self, path: str | os.PathLike[str]) -> LoadedEntry:
        """Read and validate a single entry file."""
        p = Path(path)
        post = frontmatter.load(str(p))
        entry = parse_entry(dict(post.metadata))
        return LoadedEntry(entry=entry, body=post.content, path=p)

    def iter_files(self) -> list[Path]:
        if not self.data_dir.exists():
            return []
        return sorted(
            f for f in self.data_dir.rglob("*.md") if f.is_file()
        )

    def list_entries(
        self,
        *,
        type: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        entry_id: str | None = None,
    ) -> list[LoadedEntry]:
        """List entries, optionally filtered by type/status/tag/id."""
        results: list[LoadedEntry] = []
        for f in self.iter_files():
            loaded = self.read(f)
            e = loaded.entry
            if type is not None and str(e.type) != type:
                continue
            if status is not None and str(e.status) != status:
                continue
            if tag is not None and tag not in e.tags:
                continue
            if entry_id is not None and e.id != entry_id:
                continue
            results.append(loaded)
        return results

    def get(self, entry_id: str) -> LoadedEntry | None:
        """Return the first entry matching an id, or None."""
        matches = self.list_entries(entry_id=entry_id)
        return matches[0] if matches else None

    # --- search (TASK-013) --------------------------------------------------

    def search(self, query: str, *, limit: int | None = None) -> list[LoadedEntry]:
        """Case-insensitive keyword search over id, title, tags and body."""
        q = query.strip().lower()
        if not q:
            return []
        scored: list[tuple[int, LoadedEntry]] = []
        for loaded in self.list_entries():
            e = loaded.entry
            haystacks = {
                "title": e.title.lower(),
                "id": e.id.lower(),
                "tags": " ".join(e.tags).lower(),
                "body": loaded.body.lower(),
            }
            score = 0
            if q in haystacks["title"]:
                score += 5
            if q in haystacks["id"]:
                score += 4
            if q in haystacks["tags"]:
                score += 3
            if q in haystacks["body"]:
                score += 1
            if score:
                scored.append((score, loaded))
        scored.sort(key=lambda t: (-t[0], t[1].entry.id))
        ordered = [loaded for _, loaded in scored]
        return ordered[:limit] if limit is not None else ordered
