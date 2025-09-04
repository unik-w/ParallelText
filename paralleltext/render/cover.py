"""Modular cover art generation for parallel text EPUBs."""

from typing import Optional, Tuple, Union
from PIL import Image, ImageDraw
import io
import zipfile
import xml.etree.ElementTree as ET
import pathlib


class CoverGenerator:
    """Base class for cover generation strategies."""

    def generate_cover(
        self,
        src_cover_data: Optional[bytes],
        tgt_cover_data: Optional[bytes],
        output_size: Tuple[int, int] = (600, 800),
    ) -> bytes:
        """Generate combined cover image.

        Args:
            src_cover_data: Source language cover image data
            tgt_cover_data: Target language cover image data
            output_size: Desired output size (width, height)

        Returns:
            Combined cover image as bytes
        """
        raise NotImplementedError


class DiagonalSplitCoverGenerator(CoverGenerator):
    """Generates cover by splitting images diagonally (upper/lower triangular)."""

    def generate_cover(
        self,
        src_cover_data: Optional[bytes],
        tgt_cover_data: Optional[bytes],
        output_size: Tuple[int, int] = (600, 800),
    ) -> bytes:
        """Generate diagonal split cover image.

        Uses upper triangular area for target (English) image and
        lower triangular area for source image.
        """
        width, height = output_size

        # Create base canvas
        combined = Image.new("RGB", (width, height), color="white")

        # Load and process images
        src_img = (
            self._load_and_resize_image(src_cover_data, output_size)
            if src_cover_data
            else None
        )
        tgt_img = (
            self._load_and_resize_image(tgt_cover_data, output_size)
            if tgt_cover_data
            else None
        )

        # Create diagonal mask
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)

        # Fill upper triangle (for target image)
        draw.polygon([(0, 0), (width, 0), (width, height)], fill=255)

        # Apply target image to upper triangle
        if tgt_img:
            combined.paste(tgt_img, (0, 0))

        # Apply source image to lower triangle using inverted mask
        if src_img:
            # Create inverted mask for lower triangle
            inv_mask = Image.new("L", (width, height), 255)
            inv_draw = ImageDraw.Draw(inv_mask)
            inv_draw.polygon([(0, 0), (width, 0), (width, height)], fill=0)

            # Paste source image in lower triangle
            combined.paste(src_img, (0, 0), inv_mask)

        # Convert to bytes
        output = io.BytesIO()
        combined.save(output, format="JPEG", quality=85)
        return output.getvalue()

    def _load_and_resize_image(
        self, image_data: bytes, target_size: Tuple[int, int]
    ) -> Image.Image:
        """Load image from bytes and resize to target size."""
        try:
            img = Image.open(io.BytesIO(image_data))
            # Convert to RGB if necessary
            if img.mode != "RGB":
                img = img.convert("RGB")
            return img.resize(target_size, Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"Warning: Could not process image: {e}")
            # Return a solid color image as fallback
            return Image.new("RGB", target_size, color="lightgray")


class SideBySideCoverGenerator(CoverGenerator):
    """Alternative generator that places images side by side."""

    def generate_cover(
        self,
        src_cover_data: Optional[bytes],
        tgt_cover_data: Optional[bytes],
        output_size: Tuple[int, int] = (600, 800),
    ) -> bytes:
        """Generate side-by-side cover image."""
        width, height = output_size
        half_width = width // 2

        # Create base canvas
        combined = Image.new("RGB", (width, height), color="white")

        # Load and resize images to half width
        if tgt_cover_data:
            tgt_img = self._load_and_resize_image(tgt_cover_data, (half_width, height))
            combined.paste(tgt_img, (0, 0))

        if src_cover_data:
            src_img = self._load_and_resize_image(src_cover_data, (half_width, height))
            combined.paste(src_img, (half_width, 0))

        # Convert to bytes
        output = io.BytesIO()
        combined.save(output, format="JPEG", quality=85)
        return output.getvalue()

    def _load_and_resize_image(
        self, image_data: bytes, target_size: Tuple[int, int]
    ) -> Image.Image:
        """Load image from bytes and resize to target size."""
        try:
            img = Image.open(io.BytesIO(image_data))
            if img.mode != "RGB":
                img = img.convert("RGB")
            return img.resize(target_size, Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"Warning: Could not process image: {e}")
            return Image.new("RGB", target_size, color="lightgray")


def get_cover_generator(strategy: str = "diagonal") -> CoverGenerator:
    """Factory function to get cover generator by strategy name.

    Args:
        strategy: Cover generation strategy ("diagonal", "side_by_side")

    Returns:
        CoverGenerator instance

    Raises:
        ValueError: If strategy is not supported
    """
    strategies = {
        "diagonal": DiagonalSplitCoverGenerator,
        "side_by_side": SideBySideCoverGenerator,
    }

    if strategy not in strategies:
        raise ValueError(
            f"Unsupported cover strategy: {strategy}. Supported strategies: {list(strategies.keys())}"
        )

    generator_class = strategies[strategy]
    return generator_class()


def generate_combined_cover(
    src_cover_data: Optional[bytes],
    tgt_cover_data: Optional[bytes],
    strategy: str = "diagonal",
    output_size: Tuple[int, int] = (600, 800),
) -> bytes:
    """Convenience function to generate combined cover.

    Args:
        src_cover_data: Source language cover image data
        tgt_cover_data: Target language cover image data
        strategy: Cover generation strategy
        output_size: Desired output size

    Returns:
        Combined cover image as bytes
    """
    generator = get_cover_generator(strategy)
    return generator.generate_cover(src_cover_data, tgt_cover_data, output_size)


def extract_cover_from_epub(epub_path: str) -> Optional[bytes]:
    """Extract cover image data from an EPUB file.

    Args:
        epub_path: Path to the EPUB file

    Returns:
        Cover image data as bytes, or None if not found
    """
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            # Find OPF file
            container_xml = zf.read("META-INF/container.xml")
            container_root = ET.fromstring(container_xml)
            ns_container = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
            rootfiles = container_root.findall(".//c:rootfile", ns_container)
            if not rootfiles:
                return None
            opf_path = rootfiles[0].attrib.get("full-path")
            opf_dir = str(pathlib.PurePosixPath(opf_path).parent)

            # Read OPF file
            opf_xml = zf.read(opf_path)
            opf_root = ET.fromstring(opf_xml)

            ns_opf = {
                "opf": "http://www.idpf.org/2007/opf",
                "dc": "http://purl.org/dc/elements/1.1/",
            }

            # Find cover image - try multiple strategies
            manifest_items = opf_root.findall(".//opf:manifest/opf:item", ns_opf)

            # Strategy 1: Look for cover metadata reference
            cover_meta = opf_root.find('.//opf:meta[@name="cover"]', ns_opf)
            if cover_meta is not None:
                cover_id = cover_meta.attrib.get("content")
                for item in manifest_items:
                    if item.attrib.get("id") == cover_id:
                        href = item.attrib.get("href", "")
                        abs_path = (
                            str(pathlib.PurePosixPath(opf_dir, href))
                            if opf_dir != "."
                            else href
                        )
                        try:
                            return zf.read(abs_path)
                        except KeyError:
                            continue

            # Strategy 2: Look for cover properties or obvious cover names
            for item in manifest_items:
                item_id = item.attrib.get("id", "")
                href = item.attrib.get("href", "")
                media_type = item.attrib.get("media-type", "")
                properties = item.attrib.get("properties", "")

                # Check if it's a cover by various criteria
                if media_type.startswith("image/") and (
                    "cover" in properties.lower()
                    or "cover" in item_id.lower()
                    or "cover" in href.lower()
                    or "frontcover" in href.lower()
                    or href.lower().startswith("cover")
                ):
                    abs_path = (
                        str(pathlib.PurePosixPath(opf_dir, href))
                        if opf_dir != "."
                        else href
                    )
                    try:
                        return zf.read(abs_path)
                    except KeyError:
                        continue

            # Strategy 3: Look for any image that might be a cover
            image_candidates = []
            for item in manifest_items:
                href = item.attrib.get("href", "")
                media_type = item.attrib.get("media-type", "")
                if media_type.startswith("image/"):
                    # Score based on filename likelihood
                    score = 0
                    href_lower = href.lower()
                    if "cover" in href_lower:
                        score += 10
                    if "front" in href_lower:
                        score += 8
                    if "title" in href_lower:
                        score += 6
                    if href_lower.endswith((".jpg", ".jpeg", ".png")):
                        score += 2
                    if score > 0:
                        image_candidates.append((score, href))

            # Try the highest scoring candidate
            if image_candidates:
                image_candidates.sort(reverse=True)
                for score, href in image_candidates:
                    abs_path = (
                        str(pathlib.PurePosixPath(opf_dir, href))
                        if opf_dir != "."
                        else href
                    )
                    try:
                        return zf.read(abs_path)
                    except KeyError:
                        continue

    except Exception as e:
        print(f"Warning: Could not extract cover from {epub_path}: {e}")

    return None


def test_cover_generation_and_save(
    src_epub_path: str,
    tgt_epub_path: str,
    output_dir: str = ".",
    strategies: Optional[list] = None,
) -> None:
    """Test cover generation and save results to disk for inspection.

    Args:
        src_epub_path: Path to source language EPUB
        tgt_epub_path: Path to target language EPUB
        output_dir: Directory to save test images
        strategies: List of strategies to test (defaults to all)
    """
    if strategies is None:
        strategies = ["diagonal", "side_by_side"]

    print("=== Cover Generation Test ===")

    # Extract original covers
    print("Extracting original covers...")
    src_cover_data = extract_cover_from_epub(src_epub_path)
    tgt_cover_data = extract_cover_from_epub(tgt_epub_path)

    output_path = pathlib.Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Save original covers for comparison
    if src_cover_data:
        src_path = output_path / "original_source_cover.jpg"
        with open(src_path, "wb") as f:
            f.write(src_cover_data)
        print(f"✅ Saved original source cover: {src_path}")

        # Also save info about the source cover
        try:
            src_img = Image.open(io.BytesIO(src_cover_data))
            print(f"   Source cover: {src_img.size} ({src_img.mode})")
        except Exception as e:
            print(f"   Could not analyze source cover: {e}")
    else:
        print("❌ No source cover found")

    if tgt_cover_data:
        tgt_path = output_path / "original_target_cover.jpg"
        with open(tgt_path, "wb") as f:
            f.write(tgt_cover_data)
        print(f"✅ Saved original target cover: {tgt_path}")

        # Also save info about the target cover
        try:
            tgt_img = Image.open(io.BytesIO(tgt_cover_data))
            print(f"   Target cover: {tgt_img.size} ({tgt_img.mode})")
        except Exception as e:
            print(f"   Could not analyze target cover: {e}")
    else:
        print("❌ No target cover found")

    # Test each strategy
    for strategy in strategies:
        print(f"\nTesting strategy: {strategy}")
        try:
            combined_cover_data = generate_combined_cover(
                src_cover_data, tgt_cover_data, strategy=strategy
            )

            # Save combined cover
            combined_path = output_path / f"combined_cover_{strategy}.jpg"
            with open(combined_path, "wb") as f:
                f.write(combined_cover_data)
            print(f"✅ Saved combined cover: {combined_path}")

            # Show info about the combined cover
            try:
                combined_img = Image.open(io.BytesIO(combined_cover_data))
                print(f"   Combined cover: {combined_img.size} ({combined_img.mode})")
                print(f"   File size: {len(combined_cover_data)} bytes")
            except Exception as e:
                print(f"   Could not analyze combined cover: {e}")

        except Exception as e:
            print(f"❌ Failed to generate {strategy} cover: {e}")

    print(f"\n✅ Test complete. Check {output_path} for generated images.")


def extract_and_save_epub_cover(epub_path: str, output_path: str) -> bool:
    """Extract cover from an EPUB and save it to disk.

    Args:
        epub_path: Path to the EPUB file
        output_path: Path where to save the extracted cover

    Returns:
        True if successful, False otherwise
    """
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            # Look for cover image in the zip
            cover_files = [
                f
                for f in zf.namelist()
                if "cover" in f.lower()
                and any(f.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"])
            ]

            if cover_files:
                # Use the first cover file found
                cover_data = zf.read(cover_files[0])
                with open(output_path, "wb") as f:
                    f.write(cover_data)
                print(f"✅ Extracted cover from {epub_path} to {output_path}")
                return True
            else:
                print(f"❌ No cover image found in {epub_path}")
                return False

    except Exception as e:
        print(f"❌ Error extracting cover from {epub_path}: {e}")
        return False
