"""Group near-duplicate pages by embedding similarity (pgvector + union-find)."""

from typing import Dict, Iterable, List, Tuple

from src.db.pool import get_pool

# Page vector = mean of its chunk vectors; pairs above the threshold are "same topic"
_PAIRS_SQL = """
WITH page_vec AS (
    SELECT page_id, avg(embedding) AS v FROM chunks WHERE space_key = $1 GROUP BY page_id
)
SELECT a.page_id AS a, b.page_id AS b
FROM page_vec a JOIN page_vec b ON a.page_id < b.page_id
WHERE 1 - (a.v <=> b.v) >= $2
"""


def group_pairs(
    page_ids: Iterable[str], pairs: Iterable[Tuple[str, str]]
) -> List[List[str]]:
    """Connected components over similarity pairs; singletons are kept as groups of one."""
    parent: Dict[str, str] = {pid: pid for pid in page_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path halving
            x = parent[x]
        return x

    for a, b in pairs:
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    groups: Dict[str, List[str]] = {}
    for pid in sorted(parent):
        groups.setdefault(find(pid), []).append(pid)
    return sorted(groups.values(), key=lambda g: g[0])


async def find_clusters(
    space_key: str, page_ids: Iterable[str], threshold: float
) -> List[List[str]]:
    """Cluster the given pages of a space by semantic similarity."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_PAIRS_SQL, space_key, threshold)
    return group_pairs(page_ids, [(r["a"], r["b"]) for r in rows])
