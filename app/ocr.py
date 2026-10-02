"""Text extraction from scanned documents and photos with Tesseract."""

import re
from pathlib import Path

from PIL import Image, ImageOps

from .config import settings
from .jobs import ProgressFn

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
PDF_EXTENSIONS = {".pdf"}

# A PDF page with at least this much embedded text is used as-is instead of OCR.
MIN_TEXT_LAYER_CHARS = 30


# Latin/symbol look-alikes Tesseract sometimes emits inside Greek words.
_HOMOGLYPHS = str.maketrans("ABEZHIKMNOPTYXoµ", "ΑΒΕΖΗΙΚΜΝΟΡΤΥΧομ")
_GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")


def fix_homoglyphs(text: str) -> str:
    """Replace look-alike characters in words that are otherwise Greek."""
    return re.sub(
        r"[^\W\d_]+",
        lambda m: m.group(0).translate(_HOMOGLYPHS) if _GREEK.search(m.group(0)) or "µ" in m.group(0) else m.group(0),
        text,
    )


def reflow(text: str) -> str:
    """Undo the hard line breaks of a scanned page while keeping paragraphs."""
    text = text.replace("\r", "")
    # Words split with a hyphen across lines: "συμ-\nβόλαιο" -> "συμβόλαιο".
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    paragraphs = re.split(r"\n\s*\n", text)
    cleaned = [re.sub(r"\s*\n\s*", " ", p).strip() for p in paragraphs]
    return "\n\n".join(re.sub(r"[ \t]{2,}", " ", p) for p in cleaned if p)


def _ocr_image(image: Image.Image) -> str:
    import pytesseract

    image = ImageOps.exif_transpose(image).convert("L")
    return pytesseract.image_to_string(image, lang=settings.ocr_languages)


def _extract_pdf(path: Path, progress: ProgressFn) -> list[str]:
    import fitz  # PyMuPDF

    pages = []
    with fitz.open(path) as doc:
        for index, page in enumerate(doc):
            text = page.get_text()
            if len(text.strip()) < MIN_TEXT_LAYER_CHARS:
                pixmap = page.get_pixmap(dpi=settings.ocr_dpi, colorspace=fitz.csGRAY)
                image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
                text = _ocr_image(image)
            pages.append(text)
            progress((index + 1) / doc.page_count)
    return pages


def _extract_image(path: Path, progress: ProgressFn) -> list[str]:
    pages = []
    with Image.open(path) as image:
        frames = getattr(image, "n_frames", 1)  # multi-page TIFF
        for index in range(frames):
            image.seek(index)
            pages.append(_ocr_image(image.copy()))
            progress((index + 1) / frames)
    return pages


def extract_text(path: Path, progress: ProgressFn) -> str:
    suffix = path.suffix.lower()
    if suffix in PDF_EXTENSIONS:
        pages = _extract_pdf(path, progress)
    elif suffix in IMAGE_EXTENSIONS:
        pages = _extract_image(path, progress)
    else:
        raise ValueError(f"Μη υποστηριζόμενος τύπος αρχείου: {suffix}")
    return "\n\n".join(p for p in (fix_homoglyphs(reflow(page)) for page in pages) if p)
