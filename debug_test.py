#!/usr/bin/env python3

try:
    from paralleltext.io.epub_read import load_epub
    print("Testing EPUB loading...")
    
    print("Loading DE book...")
    book_de = load_epub('fixtures/de.epub')
    print(f'DE book - Title: {book_de.title}')
    print(f'DE book - Language: {book_de.language}') 
    print(f'DE book - Chapters: {len(book_de.chapters)}')
    for i, ch in enumerate(book_de.chapters):
        print(f'  Chapter {i}: {ch.title}')
    
    print("\nLoading EN book...")
    book_en = load_epub('fixtures/en.epub')
    print(f'EN book - Title: {book_en.title}')
    print(f'EN book - Language: {book_en.language}')
    print(f'EN book - Chapters: {len(book_en.chapters)}')
    for i, ch in enumerate(book_en.chapters):
        print(f'  Chapter {i}: {ch.title}')
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
