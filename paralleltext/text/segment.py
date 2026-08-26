from bs4 import BeautifulSoup
from typing import List

from ..types import ContentUnit


def paragraphs_from_xhtml(xhtml: str) -> List[str]:
    """Return a list of paragraph-level HTML strings.

    Keeps inline markup; normalizes <p> and list items as blocks.
    """
    soup = BeautifulSoup(xhtml, "xml")

    # Remove scripts/styles
    for bad in soup.find_all(["script", "style"]):
        bad.decompose()

    blocks = []
    for el in soup.find_all(["p", "li"]):
        blocks.append(str(el))

    # Fallback: if no <p> or <li>, split by double <br>
    if not blocks:
        for br in soup.find_all("br"):
            br.replace_with("\n")
            text = soup.get_text("\n")
            chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
            blocks = [f"<p>{c}</p>" for c in chunks]

    return blocks


def content_units_from_xhtml(xhtml: str) -> List[ContentUnit]:
    """Walk DOM in document order, return TEXT, IMAGE, OTHER units.

    Preserves original HTML formatting and document ordering so that
    images can be placed at their correct source positions after alignment.
    """
    soup = BeautifulSoup(xhtml, "xml")

    # Remove scripts/styles
    for bad in soup.find_all(["script", "style"]):
        bad.decompose()

    body = soup.find("body")
    if body is None:
        body = soup

    BLOCK_TAGS = ("p", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6")

    # Text-bearing "leaf" blocks (no nested block children) whose HTML will be
    # emitted verbatim below. Any <img>/<svg> nested inside one of these is an
    # inline glyph already covered by that block's HTML, not a standalone
    # illustration — track by id() to avoid bs4's content-based Tag equality.
    leaf_text_ids = {
        id(el)
        for el in body.find_all(BLOCK_TAGS)
        if not el.find_parent("figure")
        and not el.find(BLOCK_TAGS)
        and el.get_text(strip=True)
    }

    units: List[ContentUnit] = []
    index = 0

    # Walk all top-level and nested block elements in document order
    for el in body.descendants:
        # Only process element nodes (not NavigableString)
        if not hasattr(el, "name") or el.name is None:
            continue

        # IMAGE elements
        if el.name in ("img", "svg"):
            # Skip inline glyphs already contained in a leaf text block above
            if el.find_parent("figure") or any(
                id(p) in leaf_text_ids for p in el.parents
            ):
                continue
            units.append(
                ContentUnit(
                    kind="IMAGE",
                    html=str(el),
                    text="",
                    index=index,
                )
            )
            index += 1

        # FIGURE elements (may contain img + caption)
        elif el.name == "figure":
            units.append(
                ContentUnit(
                    kind="IMAGE",
                    html=str(el),
                    text="",
                    index=index,
                )
            )
            index += 1

        # TEXT block elements
        elif el.name in ("p", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6"):
            # Skip if this element is inside a <figure> (already captured)
            if el.find_parent("figure"):
                continue
            # Skip if this element contains another block element inside it
            if el.find(["p", "div", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
                continue
            
            text = el.get_text(strip=True)
            if not text:
                continue
            units.append(
                ContentUnit(
                    kind="TEXT",
                    html=str(el),
                    text=text,
                    index=index,
                )
            )
            index += 1

    return units
