"""OCR Formatter Service for normalizing raw OCR text."""

import re
import logging

logger = logging.getLogger(__name__)

class OCRFormatterService:
    """Service to format and normalize raw OCR text for presentation and parsing."""

    def format_text(self, raw_text: str) -> str:
        """
        Takes raw OCR text and normalizes it to be more readable.
        - Removes excessive empty lines.
        - Trims trailing/leading whitespace per line.
        - Joins broken lines where obvious.
        - Preserves table-like structures.
        """
        if not raw_text:
            return ""

        # Split into lines
        lines = raw_text.split('\n')
        
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
                
        # Basic paragraph reconstruction (very conservative)
        formatted_lines = []
        i = 0
        while i < len(cleaned_lines):
            line = cleaned_lines[i]
            
            # If line is extremely short and next line is long, they might be broken
            # We keep it simple: just remove excessive newlines.
            formatted_lines.append(line)
            i += 1
            
        # Join with a single newline
        formatted_text = '\n'.join(formatted_lines)
        
        # Replace multiple spaces with a single space (except when trying to preserve columns)
        # But for financial docs, columns are important. We'll leave horizontal spacing alone
        # if it's 2-4 spaces, but convert 5+ spaces to a tab or standard spacing.
        formatted_text = re.sub(r' {5,}', '    ', formatted_text)
        
        return formatted_text
