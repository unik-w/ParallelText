"""Cross-EPUB chapter matching using title similarity + order + content.

Matches source and target chapters before intra-chapter alignment,
handling mismatched chapter counts and boundaries.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from ..types import Chapter


def _clean_title(title: str) -> str:
    """Normalize a chapter title for comparison."""
    title = re.sub(r"\s+", " ", title.strip().lower())
    # Remove common chapter prefixes
    title = re.sub(r"^(chapter|kapitel|teil|part)\s*[\d.:ixvIXV]+\s*[.:\-–—]?\s*", "", title)
    return title.strip()


def _title_similarity(t1: str, t2: str) -> float:
    """Simple word-overlap similarity between two cleaned titles."""
    w1 = set(_clean_title(t1).split())
    w2 = set(_clean_title(t2).split())
    if not w1 and not w2:
        return 1.0  # both empty → assume match
    if not w1 or not w2:
        return 0.0
    intersection = w1 & w2
    union = w1 | w2
    return len(intersection) / len(union)


def _order_similarity(pos1: int, total1: int, pos2: int, total2: int) -> float:
    """How similar are the relative positions of two chapters."""
    if total1 <= 1 and total2 <= 1:
        return 1.0
    rel1 = pos1 / max(total1 - 1, 1)
    rel2 = pos2 / max(total2 - 1, 1)
    return 1.0 - abs(rel1 - rel2)


def _content_preview(chapter: Chapter, max_chars: int = 500) -> str:
    """Extract first N chars of plain text for content comparison."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(chapter.html, "xml")
    text = soup.get_text(" ", strip=True)
    return text[:max_chars]


def match_chapters(
    src_chapters: List[Chapter],
    tgt_chapters: List[Chapter],
    use_embeddings: bool = False,
) -> List[Tuple[Optional[Chapter], Optional[Chapter]]]:
    """Match source and target chapters using title + order + content.

    Returns a list of (src_chapter, tgt_chapter) pairs.
    None on either side means unmatched.

    Uses greedy monotonic matching — preserves chapter order.
    """
    if not src_chapters or not tgt_chapters:
        return (
            [(ch, None) for ch in src_chapters]
            + [(None, ch) for ch in tgt_chapters]
        )

    n_src = len(src_chapters)
    n_tgt = len(tgt_chapters)

    # Try embedding-based title similarity if available
    title_sim_matrix = None
    if use_embeddings:
        try:
            title_sim_matrix = _embedding_title_similarity(src_chapters, tgt_chapters)
        except Exception:
            pass  # Fall back to word overlap

    # Build score matrix
    scores = []
    for i, sc in enumerate(src_chapters):
        row = []
        for j, tc in enumerate(tgt_chapters):
            if title_sim_matrix is not None:
                t_sim = title_sim_matrix[i][j]
            else:
                t_sim = _title_similarity(sc.title, tc.title)

            o_sim = _order_similarity(i, n_src, j, n_tgt)

            # Combined score — title is most important
            score = 0.5 * t_sim + 0.5 * o_sim
            row.append(score)
        scores.append(row)

    # Greedy monotonic matching
    matches: List[Tuple[Optional[Chapter], Optional[Chapter]]] = []
    matched_src = set()
    matched_tgt = set()

    # Use DP to find best monotonic matching
    pairs = _monotonic_match(scores, n_src, n_tgt)

    for si, ti in pairs:
        matched_src.add(si)
        matched_tgt.add(ti)
        matches.append((src_chapters[si], tgt_chapters[ti]))

    # Add unmatched chapters
    for i in range(n_src):
        if i not in matched_src:
            matches.append((src_chapters[i], None))
    for j in range(n_tgt):
        if j not in matched_tgt:
            matches.append((None, tgt_chapters[j]))

    # Sort by the order they appear (matched first, then unmatched)
    return matches


def _monotonic_match(
    scores: List[List[float]],
    n_src: int,
    n_tgt: int,
    threshold: float = 0.25,
) -> List[Tuple[int, int]]:
    """Find best monotonic 1:1 matching using DP.

    Returns list of (src_idx, tgt_idx) pairs maintaining order.
    Only pairs with score >= threshold are included.
    """
    # DP: dp[i][j] = best total score matching src[:i] and tgt[:j]
    INF = float("-inf")
    dp = [[0.0] * (n_tgt + 1) for _ in range(n_src + 1)]
    bt = [[None] * (n_tgt + 1) for _ in range(n_src + 1)]

    for i in range(1, n_src + 1):
        for j in range(1, n_tgt + 1):
            # Option 1: skip src[i-1]
            if dp[i - 1][j] > dp[i][j]:
                dp[i][j] = dp[i - 1][j]
                bt[i][j] = (i - 1, j, False)

            # Option 2: skip tgt[j-1]
            if dp[i][j - 1] > dp[i][j]:
                dp[i][j] = dp[i][j - 1]
                bt[i][j] = (i, j - 1, False)

            # Option 3: match src[i-1] with tgt[j-1]
            score = scores[i - 1][j - 1]
            if score >= threshold:
                val = dp[i - 1][j - 1] + score
                if val > dp[i][j]:
                    dp[i][j] = val
                    bt[i][j] = (i - 1, j - 1, True)

    # Backtrack
    pairs = []
    i, j = n_src, n_tgt
    while i > 0 and j > 0 and bt[i][j] is not None:
        pi, pj, matched = bt[i][j]
        if matched:
            pairs.append((i - 1, j - 1))
        i, j = pi, pj

    return pairs[::-1]


def _embedding_title_similarity(
    src_chapters: List[Chapter],
    tgt_chapters: List[Chapter],
) -> List[List[float]]:
    """Use LaBSE embeddings for title similarity (if available)."""
    from sentence_transformers import SentenceTransformer
    import numpy as np

    model = SentenceTransformer("sentence-transformers/LaBSE")

    src_titles = [ch.title for ch in src_chapters]
    tgt_titles = [ch.title for ch in tgt_chapters]

    src_embs = model.encode(src_titles, normalize_embeddings=True)
    tgt_embs = model.encode(tgt_titles, normalize_embeddings=True)

    # Cosine similarity matrix
    sim_matrix = np.dot(src_embs, tgt_embs.T)

    return sim_matrix.tolist()
