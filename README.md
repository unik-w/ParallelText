# ParallelText

A Python tool for creating bilingual parallel text EPUBs by merging and aligning chapters from source and target language books. Generate side-by-side text layouts with intelligent alignment, preserved metadata, and combined cover art.

## ✨ Features

### Core Functionality
- **Chapter Extraction & Alignment**: Intelligent 1:1 paragraph alignment between source and target language EPUBs
- **Metadata Preservation**: Complete Dublin Core metadata extraction and preservation (title, author, publisher, date, etc.)
- **Cover Art Generation**: Modular system for combining cover images with multiple strategies
- **EPUB3 Output**: Valid EPUB3 files with proper navigation, CSS styling, and structure
- **Language Support**: Optimized for German ↔ English pairs, extensible to other languages

### Advanced Features
- **Smart Chapter Detection**: Automatically filters out TOC, copyright, and non-substantive content
- **Flexible Cover Strategies**: 
  - Diagonal split (upper/lower triangular masks)
  - Side-by-side composition
- **CSS Styling**: English text styling with visual differentiation
- **Configurable Output**: Control chapter limits, cover strategies, and output paths

## 🚀 Quick Start

### 1. Installation

Install [pixi](https://pixi.sh) package manager:
```bash
curl -fsSL https://pixi.sh/install.sh | bash
exec $SHELL
```

Install dependencies:
```bash
pixi install
```

### 2. Prepare Test Data

Generate minimal test fixtures from your full EPUBs:
```bash
pixi run make-fixtures --de /path/to/Der_Prozess.epub \
    --en /path/to/The_Trial.epub \
    --out tests/data
```

### 3. Create Parallel EPUB

**Simple merge** (using test fixtures):
```bash
pixi run merge
# Output: tests/fixtures/kafka_parallel.epub
```

**Custom merge** with full control:
```bash
pixi run ptd merge \
    --src tests/data/DE_kafka_min.epub \
    --tgt tests/data/EN_kafka_min.epub \
    --out build/my_parallel.epub \
    --cover-strategy diagonal \
    --chapters 5
```

### 4. Run Tests
```bash
pixi run test
```

## 📖 Usage

### Command Line Interface

The `ptd` (Parallel Text Daemon) CLI provides flexible merging options:

```bash
# Basic usage
pixi run ptd merge --src source.epub --tgt target.epub --out merged.epub

# Advanced options
pixi run ptd merge \
    --src german_book.epub \           # Source language EPUB
    --tgt english_book.epub \          # Target language EPUB  
    --out parallel_output.epub \       # Output file path
    --chapters 10 \                    # Limit to first 10 chapters (0 = all)
    --cover-strategy side_by_side      # Cover combination strategy
```

### Cover Generation Strategies

**Diagonal Split** (`diagonal`):
- Upper triangular area: Target language cover
- Lower triangular area: Source language cover
- Creates seamless diagonal blend

**Side by Side** (`side_by_side`):
- Left half: Source language cover
- Right half: Target language cover
- Clean vertical division

### Fixture Generation

Create lightweight test EPUBs for development:

```bash
python tools/make_fixtures.py \
    --de full_german_book.epub \
    --en full_english_book.epub \
    --out tests/fixtures/ \
    --chapters 2                       # Extract first 2 chapters only
```

## 🏗️ Architecture

### Project Structure
```
paralleltext/
├── cli/                    # Command-line interface
│   ├── ptd.py             # Main CLI with typer
│   └── __main__.py        # Module entry point
├── io/                    # EPUB I/O operations
│   ├── epub_read.py       # EPUB loading and parsing
│   └── epub_write.py      # EPUB generation
├── text/                  # Text processing
│   └── segment.py         # Paragraph extraction from HTML
├── align/                 # Alignment algorithms
│   └── naive.py           # 1:1 paragraph alignment
└── render/                # Output generation
    ├── build.py           # Main EPUB building logic
    └── cover.py           # Modular cover generation

tools/
├── make_fixtures.py       # Test fixture generation
├── epub_chapter_extractor.py  # Chapter extraction utilities
└── inspect_metadata.py    # Metadata inspection tools
```

### Core Components

**EPUB Processing Pipeline**:
1. **Load** source and target EPUBs with metadata extraction
2. **Filter** substantive chapters (excludes TOC, copyright, etc.)
3. **Extract** paragraphs from XHTML content
4. **Align** paragraphs using 1:1 naive alignment
5. **Generate** combined cover art with chosen strategy
6. **Build** final EPUB3 with preserved metadata and styling

**Metadata Preservation**:
- Dublin Core elements (title, creator, publisher, date, language, etc.)
- OPF manifest and spine structure
- Cover image references and embedding
- CSS and navigation structure

**Cover Generation System**:
- Modular `CoverGenerator` base class
- Strategy pattern for different combination approaches
- Automatic cover extraction from source EPUBs
- Fallback handling for missing covers

## 🔧 Configuration

### Environment
- **Python**: 3.12+
- **Dependencies**: ebooklib, Pillow, typer, beautifulsoup4, lxml
- **Platform**: Linux (tested on Debian 13)

### Chapter Detection
Configure substantive content filtering in `paralleltext/cli/ptd.py`:
```python
_SKIP_TITLE_PAT = re.compile(
    r"(table of contents|contents|toc|nav|cover|title\s*page|impressum|"
    r"inhaltsverzeichnis|copyright|license|licence|dedication|acknowledg)",
    re.I,
)
_MIN_SUBSTANTIVE_PARAS = 3  # Minimum paragraphs per chapter
```

### CSS Styling
Customize appearance in `paralleltext/css/base.css`:
- Paragraph alignment and spacing
- Language-specific styling
- Font and color schemes

## 🧪 Testing

### Test Suite
```bash
pixi run test                    # Run all tests
pytest tests/test_smoke.py       # Specific test file
```

### Manual Testing
```bash
# Generate fresh fixtures
pixi run make-fixtures --de your_book_de.epub --en your_book_en.epub --out tests/fixtures/

# Test merge with different strategies
pixi run ptd merge --src tests/fixtures/de.epub --tgt tests/fixtures/en.epub --out test_diagonal.epub --cover-strategy diagonal
pixi run ptd merge --src tests/fixtures/de.epub --tgt tests/fixtures/en.epub --out test_side_by_side.epub --cover-strategy side_by_side
```

## 🛠️ Development

### Adding New Cover Strategies
1. Create new class inheriting from `CoverGenerator`
2. Implement `generate_cover()` method
3. Add strategy to `generate_combined_cover()` function
4. Update CLI options in `ptd.py`

### Extending Alignment Algorithms
1. Add new alignment module in `paralleltext/align/`
2. Implement alignment function matching the interface
3. Integrate in `build.py` pipeline

### Custom Metadata Handling
Extend `extract_epub_metadata()` in `paralleltext/render/build.py` for additional metadata fields.

## 📝 Current Scope (M1)

**Implemented**:
- ✅ Paragraph extraction from EPUB chapters
- ✅ Naïve 1:1 alignment (zip, truncate to shortest)
- ✅ Valid EPUB3 output with navigation and CSS
- ✅ Complete metadata preservation system
- ✅ Modular cover art generation (diagonal/side-by-side)
- ✅ English text styling and differentiation
- ✅ Comprehensive CLI with flexible options

**Future Enhancements (M2+)**:
- Smarter alignment algorithms (semantic, length-based)
- Calibre integration for format conversion
- Quality assurance and validation tools
- Multi-language support beyond German/English
- Advanced styling and typography options
- Batch processing capabilities

## 📄 License

This project is for educational and research purposes. Ensure you have proper rights to the EPUB files you process.
