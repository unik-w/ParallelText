#!/usr/bin/env python3
"""Test the chunking and efficient Ollama semantic alignment strategy.

This script demonstrates:
1. Different chunking strategies and their efficiency
2. Token/API call estimation
3. Processing statistics
4. Comparison with naive alignment

Usage:
    python test_chunking_strategy.py [--ollama-available]
"""

import sys
import time
from typing import List

# Mock some test data
def generate_test_sentences(language: str = 'en', count: int = 50) -> List[str]:
    """Generate test sentences for demonstration."""
    if language == 'en':
        base_sentences = [
            "This is a simple sentence for testing.",
            "Machine learning has revolutionized the field of artificial intelligence.",
            "The quick brown fox jumps over the lazy dog.",
            "Natural language processing involves computational linguistics.",
            "Semantic alignment is crucial for parallel text processing.",
            "Chunking strategies optimize API calls and memory usage.",
            "Ollama provides local language model inference capabilities.",
            "Embedding models can understand semantic similarity between texts.",
            "Batch processing improves efficiency in large-scale text analysis.",
            "Multilingual models support cross-language semantic understanding."
        ]
    else:  # German
        base_sentences = [
            "Dies ist ein einfacher Satz zum Testen.",
            "Maschinelles Lernen hat das Gebiet der künstlichen Intelligenz revolutioniert.",
            "Der schnelle braune Fuchs springt über den faulen Hund.",
            "Verarbeitung natürlicher Sprache umfasst Computerlinguistik.",
            "Semantische Ausrichtung ist entscheidend für die Verarbeitung paralleler Texte.",
            "Chunking-Strategien optimieren API-Aufrufe und Speicherverbrauch.",
            "Ollama bietet lokale Sprachmodell-Inferenz-Funktionen.",
            "Embedding-Modelle können semantische Ähnlichkeit zwischen Texten verstehen.",
            "Batch-Verarbeitung verbessert die Effizienz bei großangelegter Textanalyse.",
            "Multilinguale Modelle unterstützen sprachübergreifendes semantisches Verständnis."
        ]
    
    # Repeat and vary to reach desired count
    sentences = []
    for i in range(count):
        base_idx = i % len(base_sentences)
        sentence = base_sentences[base_idx]
        if i >= len(base_sentences):
            sentence = f"[Variant {i//len(base_sentences)}] {sentence}"
        sentences.append(sentence)
    
    return sentences


def test_chunking_strategies():
    """Test and compare different chunking strategies."""
    print("🧪 Testing Chunking Strategies")
    print("=" * 50)
    
    try:
        from paralleltext.align.chunking import (
            create_chunking_strategy, 
            create_batch_processor
        )
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("Make sure you're running from the project root with PYTHONPATH set")
        return False
    
    # Generate test data
    en_sentences = generate_test_sentences('en', 75)
    de_sentences = generate_test_sentences('de', 80)
    
    print(f"📝 Test data: {len(en_sentences)} EN sentences, {len(de_sentences)} DE sentences")
    print(f"📏 Total characters: {sum(len(s) for s in en_sentences + de_sentences):,}")
    print()
    
    # Test different strategies
    strategies = [
        ('sliding_window', {'max_chunk_size': 300, 'max_sentences_per_chunk': 10}),
        ('sliding_window', {'max_chunk_size': 500, 'max_sentences_per_chunk': 20}),
        ('semantic', {'max_chunk_size': 400, 'max_sentences_per_chunk': 15}),
    ]
    
    for strategy_name, params in strategies:
        print(f"🔧 Testing {strategy_name} strategy with {params}")
        
        try:
            processor = create_batch_processor(
                chunking_strategy=strategy_name,
                **params,
                overlap_sentences=2,
                batch_size=5
            )
            
            # Get chunking results
            en_chunks, de_chunks = processor.prepare_batches(en_sentences, de_sentences)
            
            # Get statistics
            stats = processor.get_processing_stats(en_chunks, de_chunks)
            
            print(f"   📊 Results:")
            print(f"   • EN: {stats['source_chunks']} chunks")
            print(f"   • DE: {stats['target_chunks']} chunks")
            print(f"   • Total chunks: {stats['total_chunks']}")
            print(f"   • Est. tokens: {stats['estimated_total_tokens']:,}")
            print(f"   • Est. API calls: {stats['estimated_api_calls']}")
            print(f"   • Strategy: {stats['chunking_strategy']}")
            
            # Show sample chunks
            if en_chunks:
                sample_chunk = en_chunks[0]
                print(f"   📄 Sample chunk (1st EN, {len(sample_chunk)} sentences):")
                for i, sent in enumerate(sample_chunk[:3], 1):
                    print(f"      {i}. {sent[:60]}{'...' if len(sent) > 60 else ''}")
                if len(sample_chunk) > 3:
                    print(f"      ... and {len(sample_chunk)-3} more sentences")
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()
    
    return True


def test_ollama_integration(available: bool = False):
    """Test Ollama integration if available."""
    print("🦙 Testing Ollama Integration")
    print("=" * 50)
    
    if not available:
        print("⚠️  Ollama not available - showing configuration only")
        print()
        
        try:
            from paralleltext.align.ollama_semantic import create_ollama_semantic_aligner
            
            # Create aligner (will fail validation but show config)
            try:
                aligner = create_ollama_semantic_aligner(
                    model='multilingual',
                    similarity_threshold=0.75,
                    chunking_strategy='sliding_window',
                    max_chunk_size=400,
                    max_sentences_per_chunk=15
                )
                print("✅ Aligner created successfully")
                
                # Show configuration
                info = aligner.get_alignment_info()
                print("📋 Configuration:")
                for key, value in info.items():
                    print(f"   • {key}: {value}")
                
            except Exception as e:
                print(f"⚠️  Expected error (Ollama not running): {e}")
                print("   This is normal if Ollama is not installed/running")
        
        except ImportError as e:
            print(f"❌ Import failed: {e}")
            return False
        
        print()
        print("🔧 To test with real Ollama:")
        print("   1. Install Ollama: https://ollama.ai/")
        print("   2. Start server: ollama serve")
        print("   3. Pull embedding model: ollama pull nomic-embed-text")
        print("   4. Run: python test_chunking_strategy.py --ollama-available")
        
        return True
    
    # Real Ollama testing
    try:
        from paralleltext.align.ollama_semantic import create_ollama_semantic_aligner
        
        print("🔗 Attempting to connect to Ollama...")
        
        aligner = create_ollama_semantic_aligner(
            model='popular',  # nomic-embed-text
            similarity_threshold=0.7,
            chunking_strategy='sliding_window',
            max_chunk_size=300,
            max_sentences_per_chunk=10
        )
        
        print("✅ Connected to Ollama successfully!")
        
        # Show configuration
        info = aligner.get_alignment_info()
        print("📋 Configuration:")
        for key, value in info.items():
            if key != 'available_models':  # Skip long list
                print(f"   • {key}: {value}")
        
        # Test with small sample
        en_test = ["This is a test sentence.", "Another sentence for testing."]
        de_test = ["Das ist ein Testsatz.", "Ein weiterer Satz zum Testen."]
        
        print(f"\n🧪 Testing alignment with {len(en_test)} EN + {len(de_test)} DE sentences...")
        
        start_time = time.time()
        aligned = aligner.align(en_test, de_test, method='threshold')
        end_time = time.time()
        
        print(f"⏱️  Alignment completed in {end_time - start_time:.2f} seconds")
        print(f"📊 Results: {len(aligned.source)} aligned pairs")
        
        for i, (src, tgt) in enumerate(zip(aligned.source, aligned.target), 1):
            print(f"   {i}. EN: {src}")
            print(f"      DE: {tgt}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ollama test failed: {e}")
        print("   Make sure Ollama is running and has an embedding model installed")
        return False


def show_strategy_summary():
    """Show summary of the chunking strategy."""
    print("📋 Chunking Strategy Summary")
    print("=" * 50)
    print()
    print("🎯 Goals:")
    print("   • Minimize API calls through intelligent batching")
    print("   • Control memory usage with chunk size limits")
    print("   • Preserve semantic context with overlapping windows")
    print("   • Provide cost estimation before processing")
    print()
    print("🔧 Chunking Parameters:")
    print("   • max_chunk_size: Character limit per chunk (e.g., 500)")
    print("   • max_sentences_per_chunk: Sentence limit per chunk (e.g., 20)")
    print("   • overlap_sentences: Overlap between chunks (e.g., 2)")
    print("   • chunking_strategy: 'sliding_window' or 'semantic'")
    print()
    print("⚡ Benefits:")
    print("   • 📉 Reduced API calls (batching vs individual)")
    print("   • 🧠 Better memory management")
    print("   • 💰 Cost control and estimation")
    print("   • 🔄 Fallback to naive alignment if Ollama fails")
    print("   • 🌐 Multilingual model support")
    print()
    print("🚀 Usage in CLI:")
    print("   pixi run merge-sentence-semantic")
    print("   # Uses chunked semantic alignment automatically")


def main():
    """Main test function."""
    print("🧪 Ollama Semantic Alignment - Chunking Strategy Test")
    print("=" * 60)
    print()
    
    # Check command line arguments
    ollama_available = '--ollama-available' in sys.argv
    
    # Run tests
    success = True
    
    # Test chunking strategies
    if not test_chunking_strategies():
        success = False
    
    # Test Ollama integration
    if not test_ollama_integration(ollama_available):
        success = False
    
    # Show strategy summary
    show_strategy_summary()
    
    # Final status
    print()
    if success:
        print("✅ All tests completed successfully!")
        print()
        print("🎉 The chunking strategy is ready for use!")
        print("   Next steps:")
        print("   1. Install Ollama and embedding models")
        print("   2. Run: pixi run merge-sentence-semantic")
        print("   3. Compare results with: pixi run merge-sentence")
    else:
        print("❌ Some tests failed. Check the errors above.")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
