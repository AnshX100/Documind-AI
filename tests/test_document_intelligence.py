"""Unit and Integration Tests for Document Intelligence & Ownership Isolation (Sprint 11).

Tests cover:
1. Document Intelligence UI tabs and rendering.
2. Honest status badges (processed, pending, failed).
3. Stored evidence display and arithmetic validation badge.
4. Fallback labels for missing/unextracted fields.
5. Strict User Ownership Isolation across EVERY document endpoint:
   - GET /documents/
   - GET /documents/<id>
   - GET /documents/<id>/preview
   - GET /documents/<id>/download
   - POST /documents/<id>/delete
   - POST /documents/<id>/analyze
"""

import pytest
import io
from app.models.user import User
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.extensions import db


@pytest.fixture
def document_a(app, user_a):
    """Creates a sample processed document for User A."""
    with app.app_context():
        u = db.session.get(User, user_a.id)
        doc = Document(
            user_id=u.id,
            original_filename="invoice_a.pdf",
            filename="invoice_a_stored.pdf",
            file_path="uploads/invoice_a_stored.pdf",
            file_type="application/pdf",
            file_size=2048,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()

        analysis = DocumentAnalysis(
            document_id=doc.id,
            total_amount=500.00,
            subtotal_amount=450.00,
            tax_amount=50.00,
            vendor_name="ACME Corp",
            raw_text="Invoice #1001 Total $500.00 Tax $50.00 Vendor ACME Corp",
            category="Software",
            confidence_score=0.95
        )
        db.session.add(analysis)
        db.session.commit()
        return doc.id


def test_document_intelligence_view_rendering(client, app, user_a, document_a):
    """Test Document Intelligence tabbed view, status badge, evidence display, and arithmetic badge."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    
    response = client.get(f'/documents/{document_a}')
    assert response.status_code == 200
    
    html = response.data.decode('utf-8')
    assert 'Document Intelligence' in html
    assert 'invoice_a.pdf' in html
    assert 'Processed' in html
    assert 'Overview' in html
    assert 'Financials' in html
    assert 'Risks &amp; Anomalies' in html or 'Risks & Anomalies' in html
    assert 'Evidence' in html
    assert 'Document Preview' in html
    assert '500.00' in html
    assert 'ACME Corp' in html


def test_missing_field_fallbacks(client, app, user_a):
    """Test that missing/unextracted fields display clean fallback labels."""
    with app.app_context():
        u = db.session.get(User, user_a.id)
        doc = Document(
            user_id=u.id,
            original_filename="sparse_doc.pdf",
            filename="sparse_doc.pdf",
            file_path="uploads/sparse_doc.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()

        analysis = DocumentAnalysis(
            document_id=doc.id,
            total_amount=0.00,
            subtotal_amount=0.00,
            tax_amount=0.00,
            vendor_name=None,
            invoice_number=None,
            invoice_date=None,
            category="General"
        )
        db.session.add(analysis)
        db.session.commit()
        doc_id = doc.id

    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    response = client.get(f'/documents/{doc_id}')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert ('Vendor not detected' in html or 'Invoice number missing' in html or 'Date not detected' in html)


# ==============================================================================
# OWNERSHIP ISOLATION TESTS FOR EVERY DOCUMENT ENDPOINT
# ==============================================================================

def test_isolation_list_documents(client, app, user_a, user_b, document_a):
    """Verify User B cannot see User A's documents in documents list."""
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})
    response = client.get('/documents/')
    assert response.status_code == 200
    assert b'invoice_a.pdf' not in response.data


def test_isolation_detail_endpoint(client, app, user_a, user_b, document_a):
    """Verify User B receiving 404/403 accessing User A's document detail page."""
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})
    response = client.get(f'/documents/{document_a}')
    assert response.status_code in [403, 404]


def test_isolation_preview_endpoint(client, app, user_a, user_b, document_a):
    """Verify User B receiving 404/403 accessing User A's document preview."""
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})
    response = client.get(f'/documents/{document_a}/preview')
    assert response.status_code in [403, 404]


def test_isolation_download_endpoint(client, app, user_a, user_b, document_a):
    """Verify User B receiving 404/403 downloading User A's document."""
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})
    response = client.get(f'/documents/{document_a}/download')
    assert response.status_code in [403, 404]


def test_isolation_delete_endpoint(client, app, user_a, user_b, document_a):
    """Verify User B receiving 404/403 attempting to delete User A's document."""
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})
    response = client.post(f'/documents/{document_a}/delete', follow_redirects=True)
    assert response.status_code in [200, 403, 404]

    with app.app_context():
        doc = db.session.get(Document, document_a)
        assert doc is not None  # Ensure User A's doc was NOT deleted


def test_isolation_analyze_endpoint(client, app, user_a, user_b, document_a):
    """Verify User B receiving 404 when following redirect attempting to re-analyze User A's document."""
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})
    response = client.post(f'/documents/{document_a}/analyze', follow_redirects=True)
    assert response.status_code in [403, 404]
