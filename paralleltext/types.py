from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ChapterClass(str, Enum):
    """Classification of a chapter/document within an EPUB."""

    BOOK_CONTENT = "BOOK_CONTENT"
    FRONT_MATTER = "FRONT_MATTER"
    BACK_MATTER = "BACK_MATTER"
    NAVIGATION = "NAVIGATION"
    UNKNOWN = "UNKNOWN"


@dataclass
class ContentUnit:
    """A single unit of content from an EPUB chapter, preserving DOM order."""

    kind: str  # "TEXT", "IMAGE", "OTHER"
    html: str  # original HTML fragment
    text: str = ""  # plain text (for TEXT units, used in alignment)
    index: int = 0  # position in the original DOM order


@dataclass
class Chapter:
    title: str
    html: str
    spine_position: int = 0


@dataclass
class Book:
    language: str
    title: str
    authors: List[str]
    chapters: List[Chapter]


@dataclass
class AlignmentUnit:
    src_html: str
    tgt_html: str
    images_before: List[str] = field(default_factory=list)


@dataclass
class MergeResult:
    title: str
    chapters: List[List[AlignmentUnit]]
