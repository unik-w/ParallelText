"""Naive 1:1 alignment — zip paragraphs, truncate to shortest.

Updated for M4 to work with ContentUnit and support image interleaving.
"""

from typing import List

from ..types import AlignmentUnit, ContentUnit


def _interleave_images(
    src_text_units: List[ContentUnit],
    all_src_units: List[ContentUnit],
    aligned_pairs: List[tuple],  # list of (src_idx, tgt_idx)
) -> dict:
    """Compute which images go before each aligned text unit.

    Returns a dict mapping aligned-pair index to list of image HTML strings.
    """
    # Build a map from TEXT unit index (in src_text_units) to its position in all_src_units
    text_positions = []
    for tu in src_text_units:
        text_positions.append(tu.index)

    # Collect all IMAGE units
    images = [u for u in all_src_units if u.kind == "IMAGE"]
    if not images:
        return {}

    result: dict[int, list[str]] = {}

    for pair_idx, (src_idx, _) in enumerate(aligned_pairs):
        # Current text unit's DOM position
        cur_pos = text_positions[src_idx] if src_idx < len(text_positions) else float("inf")
        # Previous text unit's DOM position
        if pair_idx > 0:
            prev_src_idx = aligned_pairs[pair_idx - 1][0]
            prev_pos = text_positions[prev_src_idx] if prev_src_idx < len(text_positions) else -1
        else:
            prev_pos = -1

        # Find images between prev_pos and cur_pos
        imgs = [
            img.html
            for img in images
            if prev_pos < img.index < cur_pos
        ]
        if imgs:
            result[pair_idx] = imgs

    # Also collect trailing images (after the last text unit)
    if aligned_pairs:
        last_src_idx = aligned_pairs[-1][0]
        last_pos = text_positions[last_src_idx] if last_src_idx < len(text_positions) else -1
        trailing = [img.html for img in images if img.index > last_pos]
        if trailing:
            result[len(aligned_pairs)] = trailing

    return result


def align_one_to_one(src_paras: List[str], tgt_paras: List[str]) -> List[AlignmentUnit]:
    """Zip paragraphs; truncate to shortest.

    Append leftover as dangling (ignored in M1).
    """
    n = min(len(src_paras), len(tgt_paras))
    out = [
        AlignmentUnit(src_html=src_paras[i], tgt_html=tgt_paras[i]) for i in range(n)
    ]
    return out


def align_naive(
    src_units: List[ContentUnit],
    tgt_units: List[ContentUnit],
) -> List[AlignmentUnit]:
    """Naive 1:1 alignment using ContentUnit lists, with image interleaving."""
    src_text = [u for u in src_units if u.kind == "TEXT"]
    tgt_text = [u for u in tgt_units if u.kind == "TEXT"]

    n = min(len(src_text), len(tgt_text))
    aligned_pairs = [(i, i) for i in range(n)]

    image_map = _interleave_images(src_text, src_units, aligned_pairs)

    out: List[AlignmentUnit] = []
    for pair_idx, (si, ti) in enumerate(aligned_pairs):
        imgs = image_map.get(pair_idx, [])
        out.append(
            AlignmentUnit(
                src_html=src_text[si].html,
                tgt_html=tgt_text[ti].html,
                images_before=imgs,
            )
        )

    # Trailing images after last text unit
    trailing = image_map.get(len(aligned_pairs), [])
    if trailing:
        # Attach trailing images to a final empty alignment unit
        out.append(
            AlignmentUnit(
                src_html="",
                tgt_html="",
                images_before=trailing,
            )
        )

    return out
