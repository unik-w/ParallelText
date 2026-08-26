"""Alignment backend dispatcher."""

from typing import Callable, List
from ..types import ContentUnit, AlignmentUnit


def get_aligner(
    backend: str = "bertalign",
) -> Callable[[List[ContentUnit], List[ContentUnit]], List[AlignmentUnit]]:
    """Return the alignment function for the given backend name."""
    if backend == "bertalign":
        from .bertalign_align import align_bertalign

        return align_bertalign
    elif backend == "naive":
        from .naive import align_naive

        return align_naive
    else:
        raise ValueError(
            f"Unknown alignment backend: {backend!r}. "
            f"Supported: 'bertalign', 'naive'"
        )
