"""Sentence-level alignment algorithms."""

from typing import List
from ..types import AlignmentUnit


def align_sentences_one_to_one(
    src_sentences: List[str], tgt_sentences: List[str]
) -> List[AlignmentUnit]:
    """Zip sentences; truncate to shortest.

    Similar to paragraph alignment but works at sentence level.
    Append leftover as dangling (ignored in current implementation).
    """
    n = min(len(src_sentences), len(tgt_sentences))
    out = [
        AlignmentUnit(src_html=src_sentences[i], tgt_html=tgt_sentences[i])
        for i in range(n)
    ]
    return out
