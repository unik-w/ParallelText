from bs4 import BeautifulSoup
from typing import List


def paragraphs_from_xhtml(xhtml: str) -> List[str]:
    """Return a list of paragraph-level HTML strings.

    Keeps inline markup; normalizes <p> and list items as blocks.
    """
    soup = BeautifulSoup(xhtml, "lxml")

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
