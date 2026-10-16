"""OCR Service for extracting text from images and PDFs."""

import os
import io
import logging
from typing import Dict, Any, Optional
from PIL import Image, ImageEnhance
import pytesseract
from pypdf import PdfReader

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

logger = logging.getLogger(__name__)

class OCRService:
    """Service to handle text extraction from various document formats."""

    def __init__(self, tesseract_cmd: Optional[str] = None, language: str = "eng"):
        self.language = language
        if tesseract_cmd and tesseract_cmd.strip():
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd.strip()

    def extract_text(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """
        Extract text from a document.
        
        Args:
            file_path: Absolute physical path to the file.
            file_type: MIME type of the file.
            
        Returns:
            Dictionary with 'success', 'text', and 'error' keys.
        """
        if not os.path.exists(file_path):
            return {"success": False, "text": "", "error": "File does not exist."}

        try:
            if file_type.lower() == 'application/pdf':
                return self._process_pdf(file_path)
            elif file_type.lower() in ['image/png', 'image/jpeg', 'image/jpg', 'image/webp']:
                return self._process_image(file_path)
            elif file_type.lower() == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                return self._process_docx(file_path)
            else:
                return {"success": False, "text": "", "error": f"Unsupported file type: {file_type}"}
                
        except Exception as e:
            logger.error(f"OCR processing failed for {file_path}: {e}")
            return {"success": False, "text": "", "error": str(e)}

    def _process_image(self, file_path: str) -> Dict[str, Any]:
        """Extract text from an image using Tesseract."""
        try:
            image = Image.open(file_path)
            
            # Basic preprocessing to improve OCR accuracy
            # Convert to grayscale
            image = image.convert('L')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            text = pytesseract.image_to_string(image, lang=self.language)
            
            if not text.strip():
                return {"success": False, "text": "", "error": "OCR completed but no text was found."}
                
            return {"success": True, "text": text.strip(), "error": None}
            
        except pytesseract.TesseractNotFoundError:
            return {"success": False, "text": "", "error": "Tesseract OCR is not installed or not found in PATH."}
        except Exception as e:
            return {"success": False, "text": "", "error": f"Image processing error: {str(e)}"}

    def _process_pdf(self, file_path: str) -> Dict[str, Any]:
        """Extract text from a PDF, falling back to OCR if needed."""
        text_parts = []
        
        # Path A: Normal text extraction via PyPDF2
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                    
            combined_text = "\n\n".join(text_parts).strip()
            
            # If we got meaningful text, return it
            # We assume a document needs at least 50 characters to be considered "text-based"
            if len(combined_text) > 50:
                return {"success": True, "text": combined_text, "error": None}
                
        except Exception as e:
            logger.warning(f"pypdf extraction failed, attempting OCR fallback: {e}")
            
        # Path B: Scanned PDF / OCR Fallback
        if not convert_from_path:
            return {
                "success": False, 
                "text": "", 
                "error": "pdf2image library is not installed. Cannot perform OCR on scanned PDFs."
            }
            
        try:
            # Convert PDF pages to images
            # Use a sensible DPI (200) to balance performance and quality
            pages = convert_from_path(file_path, dpi=200)
            ocr_text_parts = []
            
            for page_image in pages:
                # Preprocess image
                page_image = page_image.convert('L')
                enhancer = ImageEnhance.Contrast(page_image)
                page_image = enhancer.enhance(2.0)
                
                # Extract text
                page_text = pytesseract.image_to_string(page_image, lang=self.language)
                if page_text.strip():
                    ocr_text_parts.append(page_text.strip())
                    
            combined_ocr_text = "\n\n--- Page Break ---\n\n".join(ocr_text_parts).strip()
            
            if not combined_ocr_text:
                return {"success": False, "text": "", "error": "OCR completed but no meaningful text was found in the PDF."}
                
            return {"success": True, "text": combined_ocr_text, "error": None}
            
        except pytesseract.TesseractNotFoundError:
            return {"success": False, "text": "", "error": "Tesseract OCR is not installed or not found in PATH."}
        except Exception as e:
            if "poppler" in str(e).lower():
                return {"success": False, "text": "", "error": "Poppler is not installed or not in PATH. Required for PDF OCR."}
            return {"success": False, "text": "", "error": f"PDF OCR processing error: {str(e)}"}

    def _process_docx(self, file_path: str) -> Dict[str, Any]:
        """Extract text from a DOCX file using python-docx."""
        try:
            import docx
            doc = docx.Document(file_path)
            
            text_parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text.strip())
                    
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        text_parts.append(" | ".join(row_text))
                        
            combined_text = "\n".join(text_parts).strip()
            
            if not combined_text:
                return {"success": False, "text": "", "error": "DOCX extraction completed but no text was found."}
                
            return {"success": True, "text": combined_text, "error": None}
            
        except ImportError:
            return {"success": False, "text": "", "error": "python-docx library is not installed."}
        except Exception as e:
            return {"success": False, "text": "", "error": f"DOCX processing error: {str(e)}"}
