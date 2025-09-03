from typing import List
from ..types import AlignmentUnit


def align_one_to_one(src_paras: List[str], tgt_paras: List[str]) -> List[AlignmentUnit]:
    """Zip paragraphs; truncate to shortest.

    Append leftover as dangling (ignored in M1).
    """
    n = min(len(src_paras), len(tgt_paras))
    out = [
        AlignmentUnit(src_html=src_paras[i], tgt_html=tgt_paras[i]) for i in range(n)
    ]
    return out
