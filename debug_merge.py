#!/usr/bin/env python3

import sys
import traceback

try:
    from paralleltext.io.epub_read import load_epub
    from paralleltext.text.segment import paragraphs_from_xhtml
    from paralleltext.align.naive import align_one_to_one
    from paralleltext.render.build import build_merged_epub
    
    print("=== Debug Test for Merge Process ===")
    
    print("1. Loading EPUBs...")
    src_book = load_epub('fixtures/de.epub')
    tgt_book = load_epub('fixtures/en.epub')
    print(f"Source: {len(src_book.chapters)} chapters")
    print(f"Target: {len(tgt_book.chapters)} chapters")
    
    print("\n2. Checking substantive chapters...")
    # Copy the _is_substantive logic
    import re
    _SKIP_TITLE_PAT = re.compile(
        r"(table of contents|contents|toc|nav|cover|title\s*page|impressum|"
        r"inhaltsverzeichnis|copyright|license|licence|dedication|acknowledg)",
        re.I,
    )
    _MIN_SUBSTANTIVE_PARAS = 3
    
    def _is_substantive(chapter) -> bool:
        title = (getattr(chapter, "title", "") or "").strip()
        if _SKIP_TITLE_PAT.search(title):
            print(f"    Skipping chapter '{title}' - matches skip pattern")
            return False
        # quick structural filter: need at least a handful of non-empty paragraphs
        paras = [p for p in paragraphs_from_xhtml(chapter.html) if p and p.strip()]
        print(f"    Chapter '{title}': {len(paras)} paragraphs")
        return len(paras) >= _MIN_SUBSTANTIVE_PARAS
    
    src_chaps = [c for c in src_book.chapters if _is_substantive(c)]
    tgt_chaps = [c for c in tgt_book.chapters if _is_substantive(c)]
    
    print(f"Substantive source chapters: {len(src_chaps)}")
    print(f"Substantive target chapters: {len(tgt_chaps)}")
    
    if not src_chaps or not tgt_chaps:
        print("ERROR: No substantive chapters found!")
        sys.exit(1)
    
    print("\n3. Testing alignment...")
    pair_count = min(len(src_chaps), len(tgt_chaps))
    print(f"Will process {pair_count} chapter pairs")
    
    per_chapter_units = []
    for i, (s, t) in enumerate(zip(src_chaps[:pair_count], tgt_chaps[:pair_count])):
        print(f"\n  Processing chapter pair {i+1}:")
        print(f"    Source: '{s.title}'")
        print(f"    Target: '{t.title}'")
        
        s_paras = [p for p in paragraphs_from_xhtml(s.html) if p and p.strip()]
        t_paras = [p for p in paragraphs_from_xhtml(t.html) if p and p.strip()]
        
        print(f"    Source paragraphs: {len(s_paras)}")
        print(f"    Target paragraphs: {len(t_paras)}")
        
        if not s_paras or not t_paras:
            print(f"    WARNING: empty chapter content, skipping")
            continue
            
        units = align_one_to_one(s_paras, t_paras)
        print(f"    Aligned units: {len(units)}")
        per_chapter_units.append(units)
    
    print(f"\n4. Building merged EPUB...")
    print(f"Total chapter units to merge: {len(per_chapter_units)}")
    
    output_path = 'fixtures/test_debug_output.epub'
    build_merged_epub(src_book, tgt_book, per_chapter_units, output_path)
    print(f"Successfully wrote {output_path}")
    
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
