from typing import Any
import pytesseract
import spacy
from PIL import Image
from core.logging import get_logger

logger = get_logger(__name__)


class DocumentProcessor:

    def __init__(self) -> None:
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.info("Downloading spaCy model 'en_core_web_sm'...")
            spacy.cli.download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

    def extract_text_from_image(self, image_path: Any) -> Any:
        try:
            text = pytesseract.image_to_string(Image.open(image_path))
            return text
        except Exception as e:
            logger.info(f"Error during OCR: {e}")
            return None

    def analyze_text(self, text: Any) -> Any:
        if text is None:
            return {"entities": [], "summary": ""}
        doc = self.nlp(text)
        entities = [
            {
                "text": ent.text,
                "label": ent.label_,
                "start_char": ent.start_char,
                "end_char": ent.end_char,
            }
            for ent in doc.ents
        ]
        sentences = [sent.text for sent in doc.sents]
        summary = " ".join(sentences[:3]) if sentences else ""
        return {"entities": entities, "summary": summary}


if __name__ == "__main__":
    processor = DocumentProcessor()
    try:
        from PIL import Image, ImageDraw, ImageFont

        img_path = "/tmp/dummy_invoice.png"
        img = Image.new("RGB", (600, 200), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        try:
            fnt = ImageFont.truetype("Pillow/Tests/fonts/FreeMono.ttf", 20)
        except IOError:
            fnt = ImageFont.load_default()
        d.text(
            (10, 10),
            "Invoice #12345\nDate: 2023-01-01\nAmount: $1500.00\nFrom: ABC Corp",
            fill=(0, 0, 0),
            font=fnt,
        )
        img.save(img_path)
        logger.info(f"Dummy image saved to {img_path}")
        extracted_text = processor.extract_text_from_image(img_path)
        logger.info("\nExtracted Text:\n", extracted_text)
        analysis_results = processor.analyze_text(extracted_text)
        logger.info("\nAnalysis Results:\n", analysis_results)
    except ImportError:
        logger.info(
            "Pillow not installed. Cannot create dummy image for demonstration."
        )
        logger.info("Please install Pillow (pip install Pillow) to run the example.")
    except Exception as e:
        logger.info(f"An error occurred during example execution: {e}")
    import os

    if os.path.exists(img_path):
        os.remove(img_path)
        logger.info(f"Cleaned up dummy image {img_path}")
