"""Storage service for managing physical document files safely."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from flask import current_app

class StorageService:
    """Handles secure file storage, validation, and deletion."""

    def __init__(self, upload_folder: str, max_content_length: int, allowed_extensions: set[str]):
        """Initialize with configuration values."""
        self.upload_folder = Path(upload_folder)
        self.max_content_length = max_content_length
        self.allowed_extensions = allowed_extensions

    def is_allowed_extension(self, filename: str) -> bool:
        """Check if the filename has an allowed extension."""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.allowed_extensions

    def get_extension(self, filename: str) -> str:
        """Extract the extension from a filename."""
        if '.' in filename:
            return filename.rsplit('.', 1)[1].lower()
        return ""

    def validate_file(self, file: FileStorage) -> tuple[bool, str]:
        """Validate file size and extension.
        
        Note: File size validation on the server side requires seeking to the end 
        of the file stream and back, or relying on Content-Length which can be spoofed.
        Flask's MAX_CONTENT_LENGTH prevents excessively large requests, but we also 
        check stream length here for precise file limits if multiple files were supported.
        """
        if not file or not file.filename:
            return False, "No file provided."

        if not self.is_allowed_extension(file.filename):
            return False, f"File type not allowed. Allowed types: {', '.join(self.allowed_extensions)}."
            
        # Check size safely
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0, os.SEEK_SET)

        if file_size > self.max_content_length:
            return False, f"File is too large. Maximum size is {self.max_content_length // (1024*1024)}MB."

        # Deep Content & Signature Validation
        ext = self.get_extension(file.filename)
        header = file.read(4096)
        file.seek(0, os.SEEK_SET)

        if ext == "pdf":
            if not header.startswith(b"%PDF-"):
                return False, "Invalid file content. Uploaded file is not a valid PDF document."
        elif ext == "png":
            if not header.startswith(b"\x89PNG\r\n\x1a\n"):
                return False, "Invalid file content. Uploaded file is not a valid PNG image."
        elif ext in ["jpg", "jpeg"]:
            if not header.startswith(b"\xff\xd8\xff"):
                return False, "Invalid file content. Uploaded file is not a valid JPEG image."
        elif ext == "webp":
            if not (header.startswith(b"RIFF") and header[8:12] == b"WEBP"):
                return False, "Invalid file content. Uploaded file is not a valid WEBP image."
        elif ext == "docx":
            if not header.startswith(b"PK\x03\x04"):
                return False, "Invalid file content. Uploaded file is not a valid DOCX document."
            import zipfile
            try:
                with zipfile.ZipFile(file) as zf:
                    if zf.testzip() is not None:
                        file.seek(0, os.SEEK_SET)
                        return False, "Invalid file content. Corrupted or unreadable DOCX archive."
                    namelist = zf.namelist()
                    if "[Content_Types].xml" not in namelist or "word/document.xml" not in namelist:
                        file.seek(0, os.SEEK_SET)
                        return False, "Invalid file content. The uploaded ZIP file lacks standard DOCX package structure."
            except zipfile.BadZipFile:
                file.seek(0, os.SEEK_SET)
                return False, "Invalid file content. Malformed or corrupted DOCX archive."
            except RuntimeError as re:
                if "encrypted" in str(re).lower() or "password" in str(re).lower():
                    file.seek(0, os.SEEK_SET)
                    return False, "Invalid file content. Encrypted DOCX files are not supported."
                file.seek(0, os.SEEK_SET)
                return False, "Invalid file content. Unable to process DOCX file."
            except Exception:
                file.seek(0, os.SEEK_SET)
                return False, "Invalid file content. Uploaded file is not a valid DOCX document."
            finally:
                file.seek(0, os.SEEK_SET)

        return True, ""

    def save_file(self, file: FileStorage, user_id: int) -> tuple[str, str, int]:
        """Saves a file securely to the filesystem.
        
        Args:
            file: The uploaded FileStorage object.
            user_id: The ID of the user uploading the file.
            
        Returns:
            Tuple of (physical_file_path, file_type, file_size)
            
        Raises:
            ValueError: If the file is invalid.
        """
        is_valid, error_msg = self.validate_file(file)
        if not is_valid:
            raise ValueError(error_msg)

        now = datetime.now(timezone.utc)
        extension = self.get_extension(file.filename or "")
        file_type = file.mimetype or "application/octet-stream"
        
        # Normalize file_type for standard handling
        if extension == "docx":
            file_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif extension == "pdf":
            file_type = "application/pdf"
        elif extension in ["jpg", "jpeg"]:
            file_type = "image/jpeg"
        elif extension == "png":
            file_type = "image/png"
        elif extension == "webp":
            file_type = "image/webp"
        
        # Determine file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0, os.SEEK_SET)

        # Generate secure unique filename and directory structure
        # e.g., uploads/user_1/2026/08/uuid4.pdf
        unique_filename = f"{uuid.uuid4().hex}.{extension}"
        relative_dir = Path(f"user_{user_id}") / f"{now.year:04d}" / f"{now.month:02d}"
        absolute_dir = self.upload_folder / relative_dir
        
        # Ensure directory exists
        os.makedirs(absolute_dir, exist_ok=True)
        
        physical_path = absolute_dir / unique_filename
        
        # Save file
        file.save(str(physical_path))
        
        # Return the absolute path as string
        return str(physical_path), file_type, file_size

    def delete_file(self, file_path: str) -> bool:
        """Deletes a file safely from the filesystem.
        
        Args:
            file_path: Absolute path to the file.
            
        Returns:
            bool: True if deleted or missing, False if deletion failed due to other errors.
        """
        if not file_path:
            return True

        path = Path(file_path)
        
        # Path traversal protection: Ensure the path is within the upload folder
        try:
            # resolve() handles symlinks and normalizes paths
            resolved_path = path.resolve()
            resolved_upload = self.upload_folder.resolve()
            
            # Check if resolved_path starts with resolved_upload
            if not str(resolved_path).startswith(str(resolved_upload)):
                current_app.logger.warning(f"Attempted path traversal deletion blocked: {file_path}")
                return False
        except Exception:
            pass # Continue to try removal if resolve fails (e.g. file doesn't exist)

        if not os.path.exists(path):
            # File already missing, treat as success for cleanup purposes
            current_app.logger.info(f"File to delete not found, continuing: {file_path}")
            return True
            
        try:
            os.remove(path)
            return True
        except OSError as e:
            current_app.logger.error(f"Failed to delete file {file_path}: {e}")
            return False
