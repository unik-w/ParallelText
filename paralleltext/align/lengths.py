"""Length-based paragraph alignment (Gale & Church, 1993).

Aligns two paragraph sequences by the character length of their text, allowing
1:1, 1:2, 2:1, 2:2, 1:3, 3:1 merges and 1:0 / 0:1 skips. Unlike the naive zip,
no paragraph is dropped: every source and target paragraph ends up in exactly
one alignment group. The DP is banded around the diagonal implied by the
cumulative text length, so whole books align in reasonable time.
"""

import bisect
import html as _html
import math
import re
from typing import List, Tuple

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# (src count, tgt count) -> prior probability of that kind of match
_MOVES = {
    (1, 1): 0.89,
    (1, 0): 0.005,
    (0, 1): 0.005,
    (2, 1): 0.04,
    (1, 2): 0.04,
    (2, 2): 0.01,
    (3, 1): 0.005,
    (1, 3): 0.005,
}
_S2 = 6.8  # variance of the length ratio per character, from Gale & Church
_BAND = 200


def text_length(par_html: str) -> int:
    text = _html.unescape(_TAG_RE.sub("", par_html))
    return len(_WS_RE.sub(" ", text).strip())


def _match_cost(l1: int, l2: int, ratio: float) -> float:
    if l1 == 0 and l2 == 0:
        return 0.0
    mean = (l1 + l2 / ratio) / 2
    z = abs(ratio * l1 - l2) / math.sqrt(_S2 * mean)
    prob = math.erfc(z / math.sqrt(2))
    return -math.log(max(prob, 1e-300))


def align_lengths(
    src_lens: List[int], tgt_lens: List[int]
) -> List[Tuple[List[int], List[int]]]:
    """Return alignment groups as (src indices, tgt indices), in order."""
    n, m = len(src_lens), len(tgt_lens)
    total_s, total_t = sum(src_lens) or 1, sum(tgt_lens) or 1
    ratio = total_t / total_s

    ps = [0]
    for x in src_lens:
        ps.append(ps[-1] + x)
    pt = [0]
    for x in tgt_lens:
        pt.append(pt[-1] + x)

    # Band: for each src row, target columns near the same cumulative-length point.
    lo, hi = [], []
    for i in range(n + 1):
        c = bisect.bisect_left(pt, ps[i] / total_s * total_t)
        lo.append(max(0, c - _BAND))
        hi.append(min(m, c + _BAND))
    lo[0], hi[n] = 0, m
    for i in range(1, n + 1):  # keep the band connected
        lo[i] = min(lo[i], hi[i - 1])
    for i in range(n - 1, -1, -1):
        hi[i] = max(hi[i], lo[i + 1])

    moves = [(di, dj, -math.log(p)) for (di, dj), p in _MOVES.items()]
    inf = float("inf")
    cost: List[List[float]] = []
    back: List[bytearray] = []
    for i in range(n + 1):
        row_lo, row_hi = lo[i], hi[i]
        row = [inf] * (row_hi - row_lo + 1)
        brow = bytearray(row_hi - row_lo + 1)
        for j in range(row_lo, row_hi + 1):
            if i == 0 and j == 0:
                row[0] = 0.0
                continue
            best, best_k = inf, 0
            for k, (di, dj, prior) in enumerate(moves):
                pi, pj = i - di, j - dj
                if pi < 0 or pj < 0:
                    continue
                if pi == i:
                    if pj < row_lo:
                        continue
                    prev = row[pj - row_lo]
                else:
                    if pj < lo[pi] or pj > hi[pi]:
                        continue
                    prev = cost[pi][pj - lo[pi]]
                if prev == inf:
                    continue
                c = prev + prior + _match_cost(ps[i] - ps[pi], pt[j] - pt[pj], ratio)
                if c < best:
                    best, best_k = c, k
            row[j - row_lo] = best
            brow[j - row_lo] = best_k
        cost.append(row)
        back.append(brow)

    groups = []
    i, j = n, m
    while i > 0 or j > 0:
        di, dj, _ = moves[back[i][j - lo[i]]]
        groups.append((list(range(i - di, i)), list(range(j - dj, j))))
        i, j = i - di, j - dj
    groups.reverse()
    return groups
