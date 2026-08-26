"""Native LaBSE semantic alignment — replaces bertalign library entirely.

Algorithm mirrors bertalign's two-pass DP approach:
  Pass 1: Fast 1:1 alignment using FAISS top-k + DP to build a coarse path.
  Pass 2: Fine-grained N:M alignment within windows defined by the coarse path.

Encoding uses sentence-transformers with MPS (Apple Metal) when available,
falling back to CPU — no multiprocessing, no numba, no external patches.
"""

from __future__ import annotations

import os

# Torch's MPS backend and faiss-cpu's OpenMP thread pool fight over threads on
# macOS/arm64, causing a hard segfault (SIGSEGV) as soon as faiss runs its first
# multi-threaded search after the MPS backend has been used. Must be set before
# torch/faiss are imported anywhere in the process.
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
from typing import List, Tuple

from ..types import AlignmentUnit, ContentUnit
from .naive import _interleave_images

# ---------------------------------------------------------------------------
# Model singleton — loaded once, reused across chapters
# ---------------------------------------------------------------------------
_model = None
_device = None


def _ensure_model():
    global _model, _device
    if _model is not None:
        return

    import torch
    from sentence_transformers import SentenceTransformer

    if torch.backends.mps.is_available():
        _device = "mps"
    else:
        _device = "cpu"

    print(f"  [LaBSE] Loading model on device: {_device}", flush=True)
    _model = SentenceTransformer("sentence-transformers/LaBSE", device=_device)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

def _encode(sentences: List[str], num_overlaps: int) -> Tuple[np.ndarray, np.ndarray]:
    """Encode sentences with overlapping windows (same as bertalign's Encoder).

    For each overlap k in [1..num_overlaps], concatenate k consecutive sentences
    and encode. Returns:
        vecs  — shape (num_overlaps, n_sents, dim), float32, L2-normalized
        lens  — shape (num_overlaps, n_sents), byte lengths
    """
    n = len(sentences)
    all_vecs = []
    all_lens = []

    for overlap in range(1, num_overlaps + 1):
        # Build overlapping window strings
        windowed = []
        for i in range(n):
            chunk = " ".join(sentences[i : i + overlap])
            windowed.append(chunk)

        # Encode — show_progress_bar=False to keep output clean
        vecs = _model.encode(
            windowed,
            batch_size=128,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype(np.float32)  # (n, dim)

        lens = np.array([len(s.encode("utf-8")) for s in windowed], dtype=np.float32)

        all_vecs.append(vecs)
        all_lens.append(lens)

    # Stack: (num_overlaps, n, dim) and (num_overlaps, n)
    vecs_arr = np.stack(all_vecs, axis=0)
    lens_arr = np.stack(all_lens, axis=0)
    return vecs_arr, lens_arr


# ---------------------------------------------------------------------------
# FAISS top-k similarity search
# ---------------------------------------------------------------------------

def _find_top_k(src_vecs: np.ndarray, tgt_vecs: np.ndarray, k: int):
    """Find top-k similar target vecs for each source vec via FAISS (CPU).

    src_vecs, tgt_vecs: (n, dim) float32, already L2-normalized → inner product = cosine sim.
    Returns D (n, k), I (n, k).
    """
    import faiss

    dim = src_vecs.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(tgt_vecs)
    D, I = index.search(src_vecs, k)
    return D, I


# ---------------------------------------------------------------------------
# Search path helpers
# ---------------------------------------------------------------------------

def _first_search_path(src_len: int, tgt_len: int,
                        min_win: int = 250, pct: float = 0.06):
    win = max(min_win, int(max(src_len, tgt_len) * pct))
    ratio = tgt_len / src_len if src_len > 0 else 1.0
    path = []
    for i in range(src_len + 1):
        center = int(ratio * i)
        path.append([max(0, center - win), min(tgt_len, center + win)])
    return win, np.array(path, dtype=np.int32)


def _second_search_path(first_align: list, win: int, src_len: int, tgt_len: int):
    """Convert 1:1 first pass to a fine-grained search path."""
    align = list(first_align)
    # Ensure last bead is (src_len, tgt_len)
    if not align or align[-1] != (src_len, tgt_len):
        if align and align[-1][0] == src_len:
            align[-1] = (src_len, tgt_len)
        else:
            align.append((src_len, tgt_len))

    path = []
    prev_src, prev_tgt = 0, 0
    max_w = 0
    for src, tgt in align:
        lo = max(0, prev_tgt - win)
        hi = min(tgt_len, tgt + win)
        for _ in range(prev_src + 1, src + 1):
            path.append([lo, hi])
        w = hi - lo
        if w > max_w:
            max_w = w
        prev_src, prev_tgt = src, tgt

    path = [path[0]] + path  # row 0
    return max_w + 1, np.array(path, dtype=np.int32)


def _alignment_types(max_size: int) -> np.ndarray:
    types = [[0, 1], [1, 0]]
    for x in range(1, max_size):
        for y in range(1, max_size):
            if x + y <= max_size:
                types.append([x, y])
    return np.array(types, dtype=np.int32)


# ---------------------------------------------------------------------------
# Two-pass DP alignment (pure NumPy — no numba)
# ---------------------------------------------------------------------------

def _first_pass(src_len: int, tgt_len: int, first_w: int,
                search_path: np.ndarray, align_types: np.ndarray,
                D: np.ndarray, I: np.ndarray) -> np.ndarray:
    """DP pass 1: 1:1 alignment."""
    top_k = I.shape[1]
    cost = np.full((src_len + 1, 2 * first_w + 1), -np.inf, dtype=np.float32)
    pointers = np.zeros((src_len + 1, 2 * first_w + 1), dtype=np.uint8)
    cost[0, 0 - search_path[0, 0]] = 0.0

    for i in range(src_len + 1):
        i_start, i_end = search_path[i]
        for j in range(i_start, i_end + 1):
            if i == 0 and j == 0:
                continue
            best_score = -np.inf
            best_a = 0
            for a_idx, (a1, a2) in enumerate(align_types):
                pi, pj = i - a1, j - a2
                if pi < 0 or pj < 0:
                    continue
                ps, pe = search_path[pi]
                if pj < ps or pj > pe:
                    continue
                prev_score = cost[pi, pj - ps]
                if prev_score == -np.inf:
                    continue
                score = prev_score
                if a1 > 0 and a2 > 0:
                    # 1:1 — look up cosine similarity via faiss results
                    for k in range(top_k):
                        if I[i - 1, k] == j - 1:
                            score += D[i - 1, k]
                            break
                if score > best_score:
                    best_score = score
                    best_a = a_idx
            j_off = j - i_start
            cost[i, j_off] = best_score
            pointers[i, j_off] = best_a

    return pointers


def _first_backtrack(src_len: int, tgt_len: int, pointers: np.ndarray,
                     search_path: np.ndarray, align_types: np.ndarray) -> list:
    alignment = []
    i, j = src_len, tgt_len
    while True:
        j_off = j - search_path[i, 0]
        a = pointers[i, j_off]
        a1, a2 = align_types[a]
        if a1 == 1 and a2 == 1:
            alignment.append((i, j))
        i -= a1
        j -= a2
        if i == 0 and j == 0:
            break
    return alignment[::-1]


def _length_penalty(sl: float, tl: float, char_ratio: float) -> float:
    tl_adj = tl * char_ratio
    mn = min(sl, tl_adj)
    mx = max(sl, tl_adj)
    if mx == 0:
        return 0.0
    return float(np.log2(1 + mn / mx))


def _second_pass(src_vecs: np.ndarray, tgt_vecs: np.ndarray,
                 src_lens: np.ndarray, tgt_lens: np.ndarray,
                 second_w: int, search_path: np.ndarray,
                 align_types: np.ndarray,
                 char_ratio: float, skip: float,
                 margin: bool = True, len_penalty: bool = True) -> np.ndarray:
    """DP pass 2: N:M alignment."""
    src_len = src_vecs.shape[1]
    tgt_len = tgt_vecs.shape[1]
    num_overlaps = src_vecs.shape[0]

    cost = np.full((src_len + 1, second_w + 1), -np.inf, dtype=np.float32)
    pointers = np.zeros((src_len + 1, second_w + 1), dtype=np.uint8)
    cost[0, 0 - search_path[0, 0]] = 0.0

    for i in range(src_len + 1):
        i_start, i_end = search_path[i]
        for j in range(i_start, i_end + 1):
            if i == 0 and j == 0:
                continue
            best_score = -np.inf
            best_a = 0
            for a_idx, (a1, a2) in enumerate(align_types):
                pi, pj = i - a1, j - a2
                if pi < 0 or pj < 0:
                    continue
                ps, pe = search_path[pi]
                if pj < ps or pj > pe:
                    continue
                prev_score = cost[pi, pj - ps]
                if prev_score == -np.inf:
                    continue
                score = prev_score

                if a1 == 0 or a2 == 0:
                    score += skip
                else:
                    # Cosine similarity with overlap windows
                    ovlp = min(a1, a2, num_overlaps) - 1
                    sv = src_vecs[ovlp, i - 1]   # last src in window
                    tv = tgt_vecs[ovlp, j - 1]   # last tgt in window
                    cos_sim = float(np.dot(sv, tv))

                    if margin:
                        # Margin score: normalize by neighbours
                        k = min(4, tgt_vecs.shape[1])
                        idx = faiss_knn_single(src_vecs[ovlp], i - 1, tgt_vecs[ovlp], k)
                        neighbour_sims = np.dot(src_vecs[ovlp, i - 1], tgt_vecs[ovlp, idx].T)
                        margin_val = cos_sim / (np.mean(neighbour_sims) + 1e-9)
                        score += margin_val
                    else:
                        score += cos_sim

                    if len_penalty:
                        sl = sum(src_lens[0, i - a1 + di] for di in range(a1))
                        tl = sum(tgt_lens[0, j - a2 + di] for di in range(a2))
                        score += _length_penalty(sl, tl, char_ratio)

                if score > best_score:
                    best_score = score
                    best_a = a_idx

            j_off = j - i_start
            cost[i, j_off] = best_score
            pointers[i, j_off] = best_a

    return pointers


def faiss_knn_single(src_vecs_ovlp: np.ndarray, src_idx: int,
                     tgt_vecs_ovlp: np.ndarray, k: int) -> np.ndarray:
    """Return indices of top-k target vecs most similar to src_vecs_ovlp[src_idx]."""
    import faiss
    dim = tgt_vecs_ovlp.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(tgt_vecs_ovlp)
    q = src_vecs_ovlp[src_idx : src_idx + 1]
    _, I = index.search(q, k)
    return I[0]


def _second_backtrack(src_len: int, tgt_len: int, pointers: np.ndarray,
                      search_path: np.ndarray, align_types: np.ndarray) -> list:
    alignment = []
    i, j = src_len, tgt_len
    while True:
        j_off = j - search_path[i, 0]
        a = pointers[i, j_off]
        a1, a2 = align_types[a]
        src_idxs = list(range(i - a1, i))
        tgt_idxs = list(range(j - a2, j))
        alignment.append((src_idxs, tgt_idxs))
        i -= a1
        j -= a2
        if i == 0 and j == 0:
            break
    return alignment[::-1]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _labse_align_sentences(src_sentences: List[str],
                           tgt_sentences: List[str],
                           max_align: int = 3,
                           top_k: int = 3,
                           win: int = 5,
                           skip: float = -0.1,
                           margin: bool = True,
                           len_penalty: bool = True) -> list:
    """Two-pass LaBSE alignment. Returns list of ([src_idxs], [tgt_idxs]) pairs."""
    _ensure_model()

    src_len = len(src_sentences)
    tgt_len = len(tgt_sentences)

    if src_len == 0 or tgt_len == 0:
        return []

    print(f"  [LaBSE] Encoding {src_len} src + {tgt_len} tgt sentences...", flush=True)
    src_vecs, src_lens = _encode(src_sentences, max_align - 1)
    tgt_vecs, tgt_lens = _encode(tgt_sentences, max_align - 1)

    char_ratio = float(np.sum(src_lens[0])) / (float(np.sum(tgt_lens[0])) + 1e-9)

    # Pass 1
    print("  [LaBSE] Pass 1: coarse 1:1 alignment...", flush=True)
    D, I = _find_top_k(src_vecs[0], tgt_vecs[0], top_k)
    first_types = _alignment_types(2)
    first_w, first_path = _first_search_path(src_len, tgt_len)
    first_pointers = _first_pass(src_len, tgt_len, first_w, first_path, first_types, D, I)
    first_alignment = _first_backtrack(src_len, tgt_len, first_pointers, first_path, first_types)

    # Pass 2
    print("  [LaBSE] Pass 2: fine N:M alignment...", flush=True)
    second_types = _alignment_types(max_align)
    second_w, second_path = _second_search_path(first_alignment, win, src_len, tgt_len)
    second_pointers = _second_pass(
        src_vecs, tgt_vecs, src_lens, tgt_lens,
        second_w, second_path, second_types,
        char_ratio, skip, margin=margin, len_penalty=len_penalty,
    )
    result = _second_backtrack(src_len, tgt_len, second_pointers, second_path, second_types)
    print(f"  [LaBSE] Done — {len(result)} aligned pairs.", flush=True)
    return result


def align_bertalign(
    src_units: List[ContentUnit],
    tgt_units: List[ContentUnit],
) -> List[AlignmentUnit]:
    """Semantically align TEXT units via LaBSE two-pass DP.

    Drop-in replacement for the old bertalign-library-based function.
    IMAGE units from the source are interleaved at their original positions.
    """
    src_text = [u for u in src_units if u.kind == "TEXT"]
    tgt_text = [u for u in tgt_units if u.kind == "TEXT"]

    if not src_text or not tgt_text:
        return []

    src_sentences = [u.text for u in src_text]
    tgt_sentences = [u.text for u in tgt_text]

    alignment_path = _labse_align_sentences(src_sentences, tgt_sentences)

    # Build image interleave map
    aligned_pairs_for_images = [
        (si[0], ti[0] if ti else 0)
        for si, ti in alignment_path
        if si
    ]
    image_map = _interleave_images(src_text, src_units, aligned_pairs_for_images)

    out: List[AlignmentUnit] = []
    for pair_idx, (src_idxs, tgt_idxs) in enumerate(alignment_path):
        src_html = "\n".join(src_text[i].html for i in src_idxs if i < len(src_text))
        tgt_html = "\n".join(tgt_text[i].html for i in tgt_idxs if i < len(tgt_text))
        out.append(AlignmentUnit(
            src_html=src_html,
            tgt_html=tgt_html,
            images_before=image_map.get(pair_idx, []),
        ))

    trailing = image_map.get(len(alignment_path), [])
    if trailing:
        out.append(AlignmentUnit(src_html="", tgt_html="", images_before=trailing))

    return out
