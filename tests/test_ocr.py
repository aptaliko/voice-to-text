import shutil

import fitz
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.ocr import extract_text

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def test_pdf_text_layer_is_used_without_ocr(tmp_path):
    path = tmp_path / "contract.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Contract of sale between seller and buyer, Athens.")
    doc.save(path)
    assert extract_text(path, lambda p: None) == "Contract of sale between seller and buyer, Athens."


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_greek_ocr_on_image(tmp_path):
    try:
        font = ImageFont.truetype(FONT, 48)
    except OSError:
        pytest.skip("DejaVu font not available")
    image = Image.new("RGB", (1400, 200), "white")
    ImageDraw.Draw(image).text((40, 60), "Συμβόλαιο αγοραπωλησίας ακινήτου", fill="black", font=font)
    path = tmp_path / "scan.png"
    image.save(path)
    text = extract_text(path, lambda p: None)
    assert "Συμβόλαιο" in text and "ακινήτου" in text
