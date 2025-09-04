#!/usr/bin/env python3
"""Test semantic alignment with actual content."""

from paralleltext.io.epub_read import load_epub
from paralleltext.text.sentence import sentences_from_xhtml
from paralleltext.align.ollama_semantic import OllamaSemanticAligner
from paralleltext.services.ollama_client import OllamaClient
import numpy as np
from scipy.spatial.distance import cosine


def main():
    print("🔍 Testing Semantic Alignment with Actual Content")
    print("=" * 60)

    # Load books
    de_book = load_epub("./tests/fixtures/de.epub")
    en_book = load_epub("./tests/fixtures/en.epub")

    # Get substantive chapters (should be chapter 2 for both)
    de_chapter = de_book.chapters[1]  # Second chapter
    en_chapter = en_book.chapters[1]  # Second chapter

    print(f"🇩🇪 German chapter: {de_chapter.title}")
    print(f"🇺🇸 English chapter: {en_chapter.title}")

    # Extract sentences
    de_sentences = sentences_from_xhtml(de_chapter.html)
    en_sentences = sentences_from_xhtml(en_chapter.html)

    print(f"\n📝 Content:")
    print(f"  German sentences: {len(de_sentences)}")
    print(f"  English sentences: {len(en_sentences)}")

    # Show first few sentences (cleaned text)
    print(f"\n🇩🇪 First 3 German sentences:")
    for i in range(min(3, len(de_sentences))):
        from bs4 import BeautifulSoup

        text = BeautifulSoup(de_sentences[i], "html.parser").get_text()
        print(f"  {i+1}: {text[:100]}...")

    print(f"\n🇺🇸 First 3 English sentences:")
    for i in range(min(3, len(en_sentences))):
        from bs4 import BeautifulSoup

        text = BeautifulSoup(en_sentences[i], "html.parser").get_text()
        print(f"  {i+1}: {text[:100]}...")

    # Test with smaller subset first
    test_size = 10
    de_test = de_sentences[:test_size]
    en_test = en_sentences[:test_size]

    print(f"\n🧪 Testing with first {test_size} sentences each...")

    # Initialize Ollama client
    client = OllamaClient(host="192.168.178.88", port=11434)
    model = "snowflake-arctic-embed2:latest"

    try:
        # Generate embeddings
        print(f"🤖 Generating embeddings with {model}...")
        de_embeddings = client.get_embeddings(de_test, model=model)
        en_embeddings = client.get_embeddings(en_test, model=model)

        print(f"✅ DE embeddings: {len(de_embeddings)} x {len(de_embeddings[0])}")
        print(f"✅ EN embeddings: {len(en_embeddings)} x {len(en_embeddings[0])}")

        # Compute similarity matrix
        print(f"\n📊 Computing similarity matrix...")
        similarity_matrix = np.zeros((len(de_embeddings), len(en_embeddings)))

        for i, de_emb in enumerate(de_embeddings):
            for j, en_emb in enumerate(en_embeddings):
                similarity = 1 - cosine(de_emb, en_emb)
                similarity_matrix[i, j] = similarity

        print(f"Similarity matrix: {similarity_matrix.shape}")
        print(f"Max similarity: {np.max(similarity_matrix):.4f}")
        print(f"Min similarity: {np.min(similarity_matrix):.4f}")
        print(f"Mean similarity: {np.mean(similarity_matrix):.4f}")

        # Find best matches
        threshold = 0.3  # Same as config
        print(f"\n🎯 Best matches (threshold={threshold}):")

        matches = 0
        for i in range(len(de_embeddings)):
            best_j = np.argmax(similarity_matrix[i])
            best_sim = similarity_matrix[i, best_j]

            if best_sim >= threshold:
                matches += 1
                de_text = BeautifulSoup(de_test[i], "html.parser").get_text()
                en_text = BeautifulSoup(en_test[best_j], "html.parser").get_text()
                print(f"  DE[{i}] -> EN[{best_j}] (sim={best_sim:.4f}):")
                print(f"    DE: {de_text[:80]}...")
                print(f"    EN: {en_text[:80]}...")
            else:
                print(
                    f"  DE[{i}]: best match EN[{best_j}] sim={best_sim:.4f} < {threshold}"
                )

        print(f"\n📈 Results: {matches}/{len(de_embeddings)} matches above threshold")

        # Now test with the actual semantic aligner
        print(f"\n🔧 Testing OllamaSemanticAligner...")
        aligner = OllamaSemanticAligner()
        result = aligner.align_with_threshold(de_test, en_test)

        print(f"📊 Aligner result: {len(result.source)} aligned pairs")

        for i in range(min(3, len(result.source))):
            de_text = BeautifulSoup(result.source[i], "html.parser").get_text()
            en_text = BeautifulSoup(result.target[i], "html.parser").get_text()
            print(f"  Pair {i+1}:")
            print(f"    DE: {de_text[:80]}...")
            print(f"    EN: {en_text[:80]}...")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
