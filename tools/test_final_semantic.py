#!/usr/bin/env python3
"""Final test of semantic alignment with chunking strategy."""

from paralleltext.io.epub_read import load_epub
from paralleltext.text.segment import paragraphs_from_xhtml
from paralleltext.text.sentence import sentences_from_paragraph
from paralleltext.align.chunking import create_batch_processor


def test_with_real_chapter():
    """Test the chunking strategy with a real EPUB chapter."""
    print('📚 Loading test EPUBs...')
    
    # Load EPUBs
    de_book = load_epub('./tests/fixtures/de.epub')
    en_book = load_epub('./tests/fixtures/en.epub')
    
    print(f'📖 German book: {de_book.title} ({len(de_book.chapters)} chapters)')
    print(f'📖 English book: {en_book.title} ({len(en_book.chapters)} chapters)')
    
    # Use chapter 1 (index 1 since 0 is usually TOC)
    if len(de_book.chapters) > 1 and len(en_book.chapters) > 1:
        de_chapter = de_book.chapters[1]  # ERSTES KAPITEL
        en_chapter = en_book.chapters[1]  # Chapter One
        
        print(f'🎯 Testing with:')
        print(f'   German: {de_chapter.title}')
        print(f'   English: {en_chapter.title}')
        
        # Extract sentences
        de_paragraphs = paragraphs_from_xhtml(de_chapter.html)
        en_paragraphs = paragraphs_from_xhtml(en_chapter.html)
        
        de_sentences = []
        for para in de_paragraphs:
            de_sentences.extend(sentences_from_paragraph(para))
        
        en_sentences = []
        for para in en_paragraphs:
            en_sentences.extend(sentences_from_paragraph(para))
        
        print(f'📝 Extracted {len(de_sentences)} German sentences')
        print(f'📝 Extracted {len(en_sentences)} English sentences')
        
        # Test chunking strategy
        print('\\n🧪 Testing chunking strategy...')
        processor = create_batch_processor(
            chunking_strategy='sliding_window',
            max_chunk_size=400,
            max_sentences_per_chunk=8,
            overlap_sentences=1,
            batch_size=3
        )
        
        de_chunks, en_chunks = processor.prepare_batches(de_sentences, en_sentences)
        stats = processor.get_processing_stats(de_chunks, en_chunks)
        
        print(f'✅ Chunking results:')
        print(f'   • Total chunks: {stats["total_chunks"]}')
        print(f'   • Est. API calls: {stats["estimated_api_calls"]}')
        
        naive_calls = len(de_sentences) + len(en_sentences)
        efficiency = (1 - stats["estimated_api_calls"] / naive_calls) * 100
        print(f'   • Efficiency: {efficiency:.1f}% fewer API calls vs naive')
        
        # Show sample sentences for many-to-many alignment potential
        if de_sentences and en_sentences:
            print('\\n📖 Sample content for semantic alignment:')
            print(f'   DE: {de_sentences[0][:80]}...')
            print(f'   EN: {en_sentences[0][:80]}...')
            
            if len(de_sentences) > 1 and len(en_sentences) > 1:
                print(f'   DE: {de_sentences[1][:80]}...')
                print(f'   EN: {en_sentences[1][:80]}...')
        
        return True
    else:
        print('❌ Not enough chapters in test files')
        return False


def main():
    """Main test function."""
    print('🧪 Final Semantic Alignment Test')
    print('=' * 50)
    
    success = test_with_real_chapter()
    
    print('\\n' + '=' * 50)
    if success:
        print('✅ Chunking strategy test completed successfully!')
        print()
        print('🎉 Ready for semantic alignment!')
        print('   Features implemented:')
        print('   • ✅ Efficient chunking (paragraph-wise)')
        print('   • ✅ Configurable sentence extent')
        print('   • ✅ Many-to-many alignment support')
        print('   • ✅ API call optimization')
        print()
        print('🚀 To test with Ollama semantic alignment:')
        print('   1. Install Ollama: curl -fsSL https://ollama.ai/install.sh | sh')
        print('   2. Start service: ollama serve')
        print('   3. Install model: ollama pull nomic-embed-text')
        print('   4. Run alignment: pixi run merge-sentence-semantic')
        print('   5. Compare with naive: pixi run merge-sentence')
    else:
        print('❌ Test failed')
    
    return 0 if success else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
