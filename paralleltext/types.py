from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Chapter:
    title: str
    html: str
    file_name: str = ""  # path relative to the OPF


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


@dataclass
class MergeResult:
    title: str
    chapters: List[List[AlignmentUnit]]
