"""Write curated documents to <backup>/<space>/curated/ as Markdown files."""

import json
from pathlib import Path

from src.backup import layout
from src.curation.models import CuratedDoc


def curated_path(space_dir: Path, doc: CuratedDoc) -> Path:
    return space_dir / "curated" / f"{layout.slugify(doc.title)}-{doc.id[:8]}.md"


def export_doc(doc: CuratedDoc) -> Path:
    """Persist a curated doc; links are rebased from the space root to curated/."""
    space_dir = layout.space_dir(doc.space_key)
    body = layout.rebase_links(doc.markdown, "", "curated")
    head = {
        "id": doc.id,
        "title": doc.title,
        "status": doc.status.value,
        "sources": doc.source_ids,
        "conflicts": len(doc.conflicts),
    }
    front = "---\n" + "\n".join(
        f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in head.items()
    )
    path = curated_path(space_dir, doc)
    layout.write_atomic(path, f"{front}\n---\n\n{body}".encode())
    return path
