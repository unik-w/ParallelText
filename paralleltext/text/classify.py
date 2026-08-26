"""Content classification for EPUB chapters — front/back matter detection."""

import re
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

from ..types import Chapter, ChapterClass


# ---------------------------------------------------------------------------
# Title / heading keyword patterns (EN + DE)
# ---------------------------------------------------------------------------
_TITLE_FRONT_MATTER = re.compile(
    r"""(?xi)
    \b(
        table\s+of\s+contents | contents | toc | nav(?:igation)?
      | cover | title\s*page | half[\s-]?title
      | inhaltsverzeichnis | inhalt
      | dedication | widmung
      | frontispiece
    )\b
    """,
)

_TITLE_BACK_MATTER = re.compile(
    r"""(?xi)
    \b(
        impressum | imprint | colophon
      | acknowledg(?:e?ment)?s? | danksagung
      | afterword | nachwort
      | about\s+the\s+author | über\s+den\s+autor
      | also\s+by | andere\s+werke
      | bibliography | literaturverzeichnis
      | index | register
      | glossary | glossar
      | advertisement | anzeige
    )\b
    """,
)

_TITLE_NAVIGATION = re.compile(
    r"""(?xi)
    \b(
        table\s+of\s+contents | toc | nav | contents
      | inhaltsverzeichnis
    )\b
    """,
)

# ---------------------------------------------------------------------------
# Body-text boilerplate patterns (must match a SUBSTANTIAL portion)
# ---------------------------------------------------------------------------
_BOILERPLATE_PATTERNS = [
    # Copyright / rights
    re.compile(r"(?i)©\s*\d{4}"),
    re.compile(r"(?i)\ball\s+rights\s+reserved\b"),
    re.compile(r"(?i)\balle\s+rechte\s+vorbehalten\b"),
    re.compile(r"(?i)\burheberrecht\b"),
    # ISBN
    re.compile(r"(?i)\bisbn[\s:\-]*[\d\-X]{10,}"),
    # Publisher / imprint
    re.compile(r"(?i)\bpublished\s+by\b"),
    re.compile(r"(?i)\bprinted\s+(in|by)\b"),
    re.compile(r"(?i)\bverlag\b"),
    re.compile(r"(?i)\bherausgeber\b"),
    # Edition / printing
    re.compile(r"(?i)\b\d+\w*\s+(edition|auflage|printing|druck)\b"),
    re.compile(r"(?i)\bfirst\s+published\b"),
    re.compile(r"(?i)\bcatalog(u?)ing[\s-]in[\s-]publication\b"),
    # Bibliographic
    re.compile(r"(?i)\blibrary\s+of\s+congress\b"),
    re.compile(r"(?i)\bbibliograph"),
]

_MIN_BOILERPLATE_HITS = 2  # need at least 2 pattern matches to flag


def classify_chapter(
    chapter: Chapter,
    total_chapters: int,
) -> ChapterClass:
    """Classify a chapter as book content, front/back matter, or navigation.

    Uses multiple signals — never removes based on a single keyword in prose.
    """
    title = (chapter.title or "").strip()
    pos = chapter.spine_position
    score_front = 0.0
    score_back = 0.0
    score_nav = 0.0

    # --- Signal 1: Title / heading keywords ---
    if _TITLE_FRONT_MATTER.search(title):
        score_front += 3.0
    if _TITLE_BACK_MATTER.search(title):
        score_back += 3.0
    if _TITLE_NAVIGATION.search(title):
        score_nav += 4.0

    # --- Signal 2: Spine position ---
    if total_chapters > 0:
        rel_pos = pos / total_chapters
        if rel_pos < 0.12:
            score_front += 1.0
        elif rel_pos > 0.88:
            score_back += 1.0

    # --- Signal 3: Content analysis ---
    soup = BeautifulSoup(chapter.html, "xml")
    text = soup.get_text(" ", strip=True)
    text_lower = text.lower()

    # Paragraph density
    paras = soup.find_all(["p", "li"])
    substantive_paras = [p for p in paras if len(p.get_text(strip=True)) > 20]

    if len(text) < 200 and len(substantive_paras) < 2:
        # Very short page — likely boilerplate
        score_front += 1.5
        score_back += 1.5

    # Boilerplate pattern hits
    hits = sum(1 for pat in _BOILERPLATE_PATTERNS if pat.search(text))
    if hits >= _MIN_BOILERPLATE_HITS:
        # Multiple boilerplate patterns → strong signal
        score_front += hits * 0.8
        score_back += hits * 0.8

    # Navigation detection: mostly links
    links = soup.find_all("a")
    if len(links) > 5 and len(substantive_paras) < 3:
        score_nav += 3.0

    # --- Decision ---
    threshold = 3.5

    if score_nav >= threshold:
        return ChapterClass.NAVIGATION
    if score_front >= threshold and score_front >= score_back:
        return ChapterClass.FRONT_MATTER
    if score_back >= threshold and score_back > score_front:
        return ChapterClass.BACK_MATTER

    # If some evidence but not enough, mark UNKNOWN
    if max(score_front, score_back, score_nav) >= 2.0:
        return ChapterClass.UNKNOWN

    return ChapterClass.BOOK_CONTENT


def filter_book_content(
    chapters: list[Chapter],
) -> list[Chapter]:
    """Return only chapters classified as book content or uncertain.

    Discards FRONT_MATTER, BACK_MATTER, and NAVIGATION.
    Retains BOOK_CONTENT and UNKNOWN.
    """
    total = len(chapters)
    kept = []
    for ch in chapters:
        cls = classify_chapter(ch, total)
        if cls in (ChapterClass.BOOK_CONTENT, ChapterClass.UNKNOWN):
            kept.append(ch)
    return kept


def _count_text_units(chapter: Chapter) -> int:
    from .segment import content_units_from_xhtml

    return sum(1 for u in content_units_from_xhtml(chapter.html) if u.kind == "TEXT")


def split_front_body_back(
    chapters: List[Chapter],
    min_text_units: int = 30,
) -> Tuple[List[Chapter], List[Chapter], List[Chapter]]:
    """Split chapters into (front_matter, body, back_matter).

    A chapter is "weak" (front/back-matter-flavored, or below min_text_units)
    but that only removes it from the body when it sits in an unbroken run at
    the very start or end of the book. A weak chapter sandwiched between two
    substantive chapters (e.g. a short interlude) stays in the body.

    NAVIGATION-classified chapters (in-body TOC pages) are always dropped.
    """
    total = len(chapters)
    kept: List[Chapter] = []
    is_core: List[bool] = []
    for ch in chapters:
        cls = classify_chapter(ch, total)
        if cls == ChapterClass.NAVIGATION:
            continue
        weak = (
            cls in (ChapterClass.FRONT_MATTER, ChapterClass.BACK_MATTER)
            or _count_text_units(ch) < min_text_units
        )
        kept.append(ch)
        is_core.append(not weak)

    core_positions = [i for i, core in enumerate(is_core) if core]
    if not core_positions:
        # Nothing looks substantive — treat everything kept as body.
        return [], kept, []

    first_core, last_core = core_positions[0], core_positions[-1]
    front = kept[:first_core]
    body = kept[first_core : last_core + 1]
    back = kept[last_core + 1 :]
    return front, body, back
