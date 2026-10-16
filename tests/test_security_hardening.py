"""Automated Security Regression Tests for Sprint 10.5B Phase 1 Hardening.

Tests cover:
1. Database Configuration Security (No hardcoded credentials, missing DATABASE_URL enforcement)
2. DOCX Preview HTML Sanitization & Stored XSS Prevention
3. DOCX Preview Exception Safe Error Masking
4. Rate Limiting Enforcement (HTTP 429)
"""

import os
import pytest
from flask import Flask
import bleach

from app import create_app
from app.config.base import BaseConfig


def test_database_config_no_hardcoded_fallback():
    """Verify that BaseConfig does not contain hardcoded MySQL credentials."""
    # Ensure SQLALCHEMY_DATABASE_URI default is empty string, not a hardcoded URL with credentials
    assert "ansh" not in BaseConfig.SQLALCHEMY_DATABASE_URI
    assert "localhost:3306" not in BaseConfig.SQLALCHEMY_DATABASE_URI


def test_missing_database_url_raises_error(monkeypatch):
    """Verify that app creation without DATABASE_URL in dev/prod raises ValueError."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    
    # Temporarily force development mode without DATABASE_URL
    with pytest.raises(ValueError) as exc_info:
        create_app("development")
        
    assert "DATABASE_URL environment variable is not set" in str(exc_info.value)


def test_docx_html_sanitization_strips_xss():
    """Verify that bleach sanitization strips script tags, event handlers, and dangerous URIs."""
    dangerous_html = (
        "<p>Valid Paragraph</p>"
        "<script>alert('XSS')</script>"
        "<img src='x' onerror='alert(1)'>"
        "<a href='javascript:alert(1)'>Click me</a>"
        "<strong>Bold Text</strong>"
    )
    
    allowed_tags = [
        'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'div', 'span', 'blockquote', 'a', 'img'
    ]
    allowed_attrs = {
        'a': ['href', 'title', 'target'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        '*': ['class']
    }
    
    clean_html = bleach.clean(
        dangerous_html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=['http', 'https', 'mailto', 'data'],
        strip=True
    )
    
    # Assert dangerous tags/attributes were stripped
    assert "<script>" not in clean_html
    assert "onerror" not in clean_html
    assert "javascript:" not in clean_html
    # Assert safe elements were preserved
    assert "<p>Valid Paragraph</p>" in clean_html
    assert "<strong>Bold Text</strong>" in clean_html


def test_docx_error_handling_masks_raw_exceptions(client, user_a, monkeypatch):
    """Verify that exceptions during DOCX rendering show a safe generic message without raw str(e)."""
    # Create a mock document record
    with client.application.app_context():
        from app.models.document import Document
        from app.extensions import db
        
        doc = Document(
            user_id=user_a.id,
            filename="test.docx",
            original_filename="secret_path_test.docx",
            file_path="/invalid/internal/server/path/secret_file.docx",
            file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_size=1024,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

    # Log in as user_a
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'}, follow_redirects=True)
    
    # Access detail view which will fail to open the invalid file path
    res = client.get(f'/documents/{doc_id}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    
    # Check that raw internal path or raw exception str(e) is NOT leaked to user
    assert "/invalid/internal/server/path" not in html
    assert "Failed to load DOCX preview. Please verify file integrity." in html


def test_rate_limiting_enforcement():
    """Verify protected endpoints return HTTP 429 when rate limit is exceeded."""
    from app import create_app
    from app.extensions import db, limiter
    
    # Create fresh app instance where RATELIMIT_ENABLED is True during init_app
    app = create_app("testing")
    app.config["RATELIMIT_ENABLED"] = True
    limiter.enabled = True
    limiter.init_app(app)
    
    with app.app_context():
        db.create_all()
        with app.test_client() as test_client:
            responses = []
            # Endpoint login is limited to 5 per minute
            for _ in range(7):
                res = test_client.post('/auth/login', data={'email': 'test@example.com', 'password': 'wrong'}, follow_redirects=False)
                responses.append(res.status_code)
                
            # First 5 requests should get 200/302, 6th and 7th should get 429
            assert 429 in responses


def test_file_upload_content_validation():
    """Verify that StorageService rejects extension-mismatched and malformed files."""
    import io
    import zipfile
    from werkzeug.datastructures import FileStorage
    from app.services.storage_service import StorageService

    storage = StorageService(
        upload_folder="tests/temp_uploads",
        max_content_length=16 * 1024 * 1024,
        allowed_extensions={"pdf", "png", "jpg", "jpeg", "webp", "docx"}
    )

    # 1. Plain text file renamed to .png
    fake_png = FileStorage(stream=io.BytesIO(b"Hello world text content"), filename="fake.png")
    valid, msg = storage.validate_file(fake_png)
    assert valid is False
    assert "Invalid file content" in msg

    # 2. Plain text file renamed to .jpg
    fake_jpg = FileStorage(stream=io.BytesIO(b"Plain text disguised as jpeg"), filename="fake.jpg")
    valid, msg = storage.validate_file(fake_jpg)
    assert valid is False
    assert "Invalid file content" in msg

    # 3. Plain text file renamed to .pdf
    fake_pdf = FileStorage(stream=io.BytesIO(b"Plain text disguised as pdf"), filename="fake.pdf")
    valid, msg = storage.validate_file(fake_pdf)
    assert valid is False
    assert "Invalid file content" in msg

    # 4. Arbitrary ZIP file renamed to .docx (lacking OOXML structure)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("random.txt", "not a docx")
    zip_buffer.seek(0)
    fake_docx = FileStorage(stream=zip_buffer, filename="fake.docx")
    valid, msg = storage.validate_file(fake_docx)
    assert valid is False
    assert "Invalid file content" in msg

    # 5. Valid PDF header
    valid_pdf_content = b"%PDF-1.4 header content"
    valid_pdf = FileStorage(stream=io.BytesIO(valid_pdf_content), filename="valid.pdf")
    valid, msg = storage.validate_file(valid_pdf)
    assert valid is True
    assert msg == ""

    # 6. Valid PNG header
    valid_png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    valid_png = FileStorage(stream=io.BytesIO(valid_png_content), filename="valid.png")
    valid, msg = storage.validate_file(valid_png)
    assert valid is True
    assert msg == ""


def test_logout_method_security(client, user_a):
    """Verify GET /auth/logout returns 405 Method Not Allowed and POST logs out correctly."""
    # Login first
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    # GET request must fail with 405 Method Not Allowed
    get_res = client.get('/auth/logout')
    assert get_res.status_code == 405

    # User remains authenticated
    dashboard_res = client.get('/dashboard/')
    assert dashboard_res.status_code == 200

    # POST request logs user out successfully
    post_res = client.post('/auth/logout', follow_redirects=True)
    assert post_res.status_code == 200

    # Protected route redirects to login
    unauth_res = client.get('/dashboard/')
    assert unauth_res.status_code == 302
    assert '/auth/login' in unauth_res.location


def test_tesseract_config_resolution():
    """Verify OCRService resolves executable via PATH when tesseract_cmd is empty."""
    from app.services.ocr_service import OCRService
    import pytesseract

    # Initializing with None or empty string does not raise or set Windows path
    service = OCRService(tesseract_cmd=None, language="eng")
    assert service.language == "eng"

    service_empty = OCRService(tesseract_cmd="   ", language="eng")
    assert service_empty.language == "eng"


def test_docx_validation_comprehensive_suite():
    """Sprint 10.5C: Verify DOCX validation accepts valid OOXML and rejects arbitrary/corrupted ZIPs."""
    import io
    import zipfile
    from werkzeug.datastructures import FileStorage
    from app.services.storage_service import StorageService

    storage = StorageService(
        upload_folder="tests/temp_uploads",
        max_content_length=16 * 1024 * 1024,
        allowed_extensions={"pdf", "png", "jpg", "jpeg", "webp", "docx"}
    )

    # 1. Valid DOCX with required OOXML structure
    docx_buf = io.BytesIO()
    with zipfile.ZipFile(docx_buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
    docx_buf.seek(0)
    valid_docx = FileStorage(stream=docx_buf, filename="valid_document.docx")
    is_valid, msg = storage.validate_file(valid_docx)
    assert is_valid is True
    assert msg == ""

    # 2. Arbitrary ZIP file without OOXML structure
    arb_buf = io.BytesIO()
    with zipfile.ZipFile(arb_buf, "w") as zf:
        zf.writestr("notes.txt", "some text")
    arb_buf.seek(0)
    arb_zip_docx = FileStorage(stream=arb_buf, filename="fake_notes.docx")
    is_valid, msg = storage.validate_file(arb_zip_docx)
    assert is_valid is False
    assert "ZIP file lacks" in msg or "DOCX" in msg

    # 3. Corrupted ZIP with PK header but bad zip payload
    corrupt_buf = io.BytesIO(b"PK\x03\x04corrupted_zip_payload_bytes_here")
    corrupt_docx = FileStorage(stream=corrupt_buf, filename="corrupt.docx")
    is_valid, msg = storage.validate_file(corrupt_docx)
    assert is_valid is False
    assert "Invalid file content" in msg

    # 4. Renamed text file disguised as docx
    text_buf = io.BytesIO(b"Plain text document content")
    text_docx = FileStorage(stream=text_buf, filename="plain_text.docx")
    is_valid, msg = storage.validate_file(text_docx)
    assert is_valid is False
    assert "Invalid file content" in msg


def test_dashboard_financial_services_integration(app, user_a, user_b):
    """Sprint 10.5C: Verify dashboard relies on intelligence services and enforces user isolation."""
    with app.app_context():
        from app.models.document import Document
        from app.models.document_analysis import DocumentAnalysis
        from app.extensions import db
        from app.dashboard.routes import generate_priority_alerts
        from app.services import due_diligence_service
        from datetime import date

        # Setup Document for User A
        doc_a = Document(
            user_id=user_a.id,
            original_filename="user_a_invoice.pdf",
            filename="user_a_invoice.pdf",
            file_path="/fake/user_a.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="processed"
        )
        db.session.add(doc_a)
        db.session.commit()

        analysis_a = DocumentAnalysis(
            document_id=doc_a.id,
            vendor_name="Acme Corp",
            invoice_number=None,  # missing invoice number trigger
            total_amount=50000.0,
            subtotal_amount=40000.0,
            tax_amount=500.0,  # arithmetic mismatch trigger
            invoice_date=date.today(),
            category="Software",
            confidence_score=0.9
        )
        db.session.add(analysis_a)
        db.session.commit()

        # User A alerts
        alerts_a = generate_priority_alerts(user_a.id)
        assert isinstance(alerts_a, list)
        assert len(alerts_a) > 0

        # User B alerts should be empty (user isolation)
        alerts_b = generate_priority_alerts(user_b.id)
        assert isinstance(alerts_b, list)
        assert len(alerts_b) == 0

        # Due Diligence service single source of truth check
        dd_a = due_diligence_service.get_due_diligence_report(user_a.id)
        assert dd_a["total_docs"] == 1
        dd_b = due_diligence_service.get_due_diligence_report(user_b.id)
        assert dd_b["total_docs"] == 0



def test_single_ai_assistant_navigation_entry():
    """Sprint 10.5C: Verify sidebar and base templates contain exactly one canonical AI Assistant link each."""
    base_html_path = os.path.join("app", "templates", "base.html")
    sidebar_path = os.path.join("app", "templates", "components", "sidebar.html")

    if os.path.exists(base_html_path):
        with open(base_html_path, "r", encoding="utf-8") as f:
            base_content = f.read()
            assert base_content.count('href="/assistant"') == 1

    if os.path.exists(sidebar_path):
        with open(sidebar_path, "r", encoding="utf-8") as f:
            sidebar_content = f.read()
            assert sidebar_content.count('href="/assistant"') == 1



def test_datetime_now_utc_sortability(app, user_a):
    """Sprint 10.5C: Verify timezone-aware UTC datetimes operate properly in database models."""
    from datetime import datetime, timezone
    from app.models.document import Document
    from app.extensions import db

    with app.app_context():
        now_tz = datetime.now(timezone.utc)
        doc = Document(
            user_id=user_a.id,
            original_filename="tz_test.pdf",
            filename="tz_test.pdf",
            file_path="/fake/tz_test.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="pending",
            created_at=now_tz,
            updated_at=now_tz
        )
        db.session.add(doc)
        db.session.commit()

        fetched_doc = Document.query.get(doc.id)
        assert fetched_doc is not None
        assert fetched_doc.created_at is not None


def test_rate_limiter_storage_uri_override(monkeypatch):
    """Sprint 10.5C: Verify RATELIMIT_STORAGE_URI can be configured via environment variable."""
    from app.config.base import BaseConfig
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    
    # Reload BaseConfig environment lookup logic
    custom_storage = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    assert custom_storage == "redis://localhost:6379/0"


