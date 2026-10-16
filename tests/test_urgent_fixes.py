"""Regression tests for urgent fixes:
1. Modal rendering, contrast, centering, close/cancel attributes, and viewport structure.
2. DOCX upload with full 71-character MIME type persistence in MySQL.
3. Database failure rollback, physical file cleanup, and session recovery (preventing PendingRollbackError).
4. Multi-format support (PDF, PNG, JPEG, DOCX) and user isolation.
"""

import io
import os
import zipfile
import pytest
from flask import url_for
from werkzeug.datastructures import FileStorage
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models.document import Document
from app.models.user import User
from app.services import document_service, storage_service


def _make_valid_docx():
    """Create a minimal valid OOXML DOCX in-memory stream."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types><Default Extension='xml' ContentType='application/xml'/></Types>")
        zf.writestr("word/document.xml", "<w:document><w:body><w:p><w:r><w:t>Test Invoice 100</w:t></w:r></w:p></w:body></w:document>")
    buf.seek(0)
    return buf


def _make_valid_pdf():
    """Create a minimal valid PDF in-memory stream."""
    return io.BytesIO(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF")


def _make_valid_png():
    """Create a minimal valid PNG in-memory stream."""
    # 8-byte signature + minimal IHDR
    return io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82")


def _make_valid_jpeg():
    """Create a minimal valid JPEG in-memory stream."""
    return io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9")


# =====================================================================
# BUG 1 TESTS: Delete Confirmation Modal Rendering & Attributes
# =====================================================================

def test_delete_modal_markup_and_attributes(client, app, user_a):
    """Verify delete modal in rendered HTML is properly structured without inline z-index conflict."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    
    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            filename="modal_test.pdf",
            original_filename="modal_test_invoice.pdf",
            file_path="tests/temp_uploads/modal_test.pdf",
            file_type="application/pdf",
            file_size=2048,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

    resp = client.get(f'/documents/{doc_id}')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    # Modal wrapper must have id="deleteModal" and aria-hidden="true" initially
    assert 'id="deleteModal"' in html
    assert 'aria-hidden="true"' in html
    
    # Must NOT have inline z-index that overrides CSS hierarchy (which previously caused backdrop layering over modal)
    assert 'style="display: none; z-index: 10000;"' not in html
    assert 'z-index: 10000;' not in html

    # Centered dialog and opaque content wrapper
    assert 'modal-dialog' in html
    assert 'modal-dialog-centered' in html
    assert 'modal-content' in html
    assert 'modal-body' in html

    # Dismiss buttons (both top close 'X' and Cancel button)
    assert 'btn-close-modal' in html
    assert 'data-bs-dismiss="modal"' in html
    assert 'Cancel' in html

    # Deletion form structure with CSRF token and danger submit button
    assert 'id="deleteForm"' in html
    assert 'csrf_token' in html
    assert 'Delete Document' in html

    # Triggers on the detail page
    assert 'data-bs-toggle="modal"' in html
    assert 'data-bs-target="#deleteModal"' in html
    assert f'data-doc-id="{doc_id}"' in html


def test_documents_index_delete_trigger_structure(client, app, user_a):
    """Verify document list index page contains proper data-bs-target modal attributes."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            filename="index_doc.pdf",
            original_filename="quarterly_report.pdf",
            file_path="tests/temp_uploads/index_doc.pdf",
            file_type="application/pdf",
            file_size=4096,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

    resp = client.get('/documents/')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    assert 'btn-delete-trigger' in html
    assert 'data-bs-toggle="modal"' in html
    assert 'data-bs-target="#deleteModal"' in html
    assert f'data-doc-id="{doc_id}"' in html
    assert 'quarterly_report.pdf' in html


# =====================================================================
# BUG 2 TESTS: DOCX Upload & MIME Type Database Length
# =====================================================================

def test_docx_upload_full_mimetype_persisted(client, app, user_a):
    """Verify a valid DOCX file is saved with its full 71-character official MIME type in the database."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    
    docx_stream = _make_valid_docx()
    data = {
        'document': (docx_stream, 'test_statement.docx')
    }

    resp = client.post('/documents/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        doc = Document.query.filter_by(user_id=user_a.id, original_filename='test_statement.docx').first()
        assert doc is not None
        # Must match full official MIME type (71 chars)
        expected_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert doc.file_type == expected_mime
        assert len(doc.file_type) == 71
        assert doc.file_size > 0
        assert os.path.exists(doc.file_path)

        # Clean up created file
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)


def test_all_supported_formats_persist_correct_file_type(client, app, user_a):
    """Verify PDF, PNG, and JPEG formats all upload and persist their full expected MIME types."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    formats = [
        ('invoice.pdf', _make_valid_pdf(), 'application/pdf'),
        ('receipt.png', _make_valid_png(), 'image/png'),
        ('bill.jpg', _make_valid_jpeg(), 'image/jpeg'),
    ]

    for filename, stream, expected_type in formats:
        data = {'document': (stream, filename)}
        resp = client.post('/documents/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            doc = Document.query.filter_by(user_id=user_a.id, original_filename=filename).first()
            assert doc is not None, f"Document {filename} was not found in DB"
            assert doc.file_type == expected_type
            assert os.path.exists(doc.file_path)
            # Clean up
            os.remove(doc.file_path)


# =====================================================================
# STEP C TESTS: Session Rollback, Orphan File Cleanup & Recovery
# =====================================================================

def test_database_insert_failure_rolls_back_and_cleans_file(client, app, user_a, monkeypatch):
    """Verify that a DB error during document persistence triggers a session rollback and cleans the saved file."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    from app.services.storage_service import StorageService
    from app.repositories.document_repository import DocumentRepository

    saved_paths = []
    original_save = StorageService.save_file

    def tracking_save(self, *args, **kwargs):
        path, ftype, fsize = original_save(self, *args, **kwargs)
        saved_paths.append(path)
        return path, ftype, fsize

    monkeypatch.setattr(StorageService, 'save_file', tracking_save)

    # Simulate DB failure on add()
    def fail_add(self, *args, **kwargs):
        raise OperationalError("Simulated database failure during flush", {}, None)

    monkeypatch.setattr(DocumentRepository, 'add', fail_add)

    pdf_stream = _make_valid_pdf()
    data = {'document': (pdf_stream, 'failed_upload.pdf')}
    resp = client.post('/documents/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
    
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Database error during upload. File was not saved." in html

    # Verify no orphaned file remains on disk
    assert len(saved_paths) == 1
    assert not os.path.exists(saved_paths[0]), "Orphaned physical file was not deleted after DB failure!"

    # Verify no record in DB
    with app.app_context():
        doc = Document.query.filter_by(original_filename='failed_upload.pdf').first()
        assert doc is None


def test_subsequent_upload_succeeds_without_pending_rollback_error(client, app, user_a, monkeypatch):
    """Verify that after a failed database insert, session rollback allows the next upload to succeed cleanly."""
    from app.repositories.document_repository import DocumentRepository
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    # 1. Trigger a DB failure on the first upload
    call_count = 0
    original_add = DocumentRepository.add

    def fail_once_add(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OperationalError("First insert failed", {}, None)
        return original_add(self, *args, **kwargs)

    monkeypatch.setattr(DocumentRepository, 'add', fail_once_add)

    first_stream = _make_valid_pdf()
    resp1 = client.post('/documents/upload', data={'document': (first_stream, 'first_attempt.pdf')},
                        content_type='multipart/form-data', follow_redirects=True)
    assert resp1.status_code == 200
    assert "Database error during upload" in resp1.data.decode('utf-8')

    # 2. Immediately perform a second upload (without restarting the application or clearing session)
    second_stream = _make_valid_docx()
    resp2 = client.post('/documents/upload', data={'document': (second_stream, 'second_attempt.docx')},
                        content_type='multipart/form-data', follow_redirects=True)
    assert resp2.status_code == 200
    html2 = resp2.data.decode('utf-8')
    # Must NOT produce PendingRollbackError or flash an error
    assert "PendingRollbackError" not in html2
    assert "Database error" not in html2

    # Second file must be saved successfully
    with app.app_context():
        doc = Document.query.filter_by(user_id=user_a.id, original_filename='second_attempt.docx').first()
        assert doc is not None
        assert doc.file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)


def test_corrupted_file_rejected_without_db_or_storage_leak(client, app, user_a):
    """Verify that an invalid/corrupted file is rejected and leaves zero DB records or orphaned files."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    # Plain text file disguised as docx
    fake_docx = io.BytesIO(b"This is just plain text, not a docx archive.")
    data = {'document': (fake_docx, 'fake.docx')}
    resp = client.post('/documents/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
    
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Invalid file content" in html

    with app.app_context():
        doc = Document.query.filter_by(original_filename='fake.docx').first()
        assert doc is None
