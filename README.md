# paralleltext (M1)

## Quickstart (Debian 13, headless)

1. Install pixi (https://pixi.sh):
```bash
curl -fsSL https://pixi.sh/install.sh | bash
exec $SHELL
```

2. Create and install deps:
```
pixi install
```

3. Build minimal test fixtures from your Kafka EPUBs:
```
pixi run make-fixtures --de /path/to/Der_Prozess.epub \
    --en /path/to/The_Trial.epub \
    --out tests/data
```

4. Run the M1 merge on the two-chapter fixtures:
```
pixi run merge
# output at build/kafka_parallel.epub
```

5. Or call CLI directly:
```
pixi run ptd merge --src tests/data/DE_kafka_min.epub \
--tgt tests/data/EN_kafka_min.epub \
--out build/kafka_parallel.epub
```

6. Run tests:
```
pixi run test
```

---

### What’s in scope for M1
- Paragraph extraction from both EPUBs
- Naïve 1:1 alignment (zip, truncate to shortest)
- Valid EPUB3 output with `<nav>` and CSS
- English text greyed via CSS


### Next (M2+ hooks already anticipated)
- Smarter pairing/alignment, Calibre integration, covers, metadata union, QA, etc.