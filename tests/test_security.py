import pytest
from app.extensions import db
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.services import financial_intelligence_service, anomaly_detection_service
import io

def test_user_data_isolation(client, app, user_a, user_b):
    """Test that User B cannot access User A's documents."""
    
    # Setup: Create a document owned by User A
    with app.app_context():
        # Ensure we bind to current session
        doc = Document(
            user_id=user_a.id,
            original_filename="user_a_secret.pdf",
            filename="user_a_secret.pdf",
            file_path="/fake/path/user_a_secret.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id
        
    # User B logs in
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})
    
    # User B tries to view User A's document details
    response = client.get(f'/documents/{doc_id}')
    assert response.status_code in [403, 404], "User B should not be able to view User A's document"
    
    # User B tries to download User A's document
    response = client.get(f'/documents/{doc_id}/download')
    assert response.status_code in [403, 404], "User B should not be able to download User A's document"

    # User B tries to delete User A's document
    response = client.post(f'/documents/{doc_id}/delete')
    assert response.status_code in [403, 404], "User B should not be able to delete User A's document"


def test_financial_intelligence_data_isolation(client, app, user_a, user_b):
    """Test that User B cannot see User A's financial intelligence or spending."""
    with app.app_context():
        doc_a = Document(
            user_id=user_a.id,
            original_filename="confidential_invoice.pdf",
            filename="confidential_invoice.pdf",
            file_path="/fake/confidential.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="processed"
        )
        db.session.add(doc_a)
        db.session.commit()

        analysis_a = DocumentAnalysis(
            document_id=doc_a.id,
            vendor_name="Secret Defense Vendor",
            invoice_number="TOPSECRET-001",
            total_amount=999999.0,
            subtotal_amount=900000.0,
            tax_amount=99999.0,
            confidence_score=0.95
        )
        db.session.add(analysis_a)
        db.session.commit()

        # Direct service query isolation check
        overview_b = financial_intelligence_service.get_financial_overview(user_b.id)
        assert overview_b["total_spending"] == 0.0
        assert overview_b["analyzed_documents"] == 0

        anomalies_b = anomaly_detection_service.get_user_anomalies(user_b.id)
        assert len(anomalies_b) == 0

    # User B logs in via web client
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})
    
    # User B views financial intelligence page
    resp = client.get('/financial-intelligence')
    assert resp.status_code == 200
    assert b"Secret Defense Vendor" not in resp.data
    assert b"999,999" not in resp.data


def test_document_upload_constraints(client, app, user_a):
    """Test document upload validation (invalid extensions)."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    
    # Test uploading a .exe file
    data = {
        'file': (io.BytesIO(b"malicious code"), 'virus.exe')
    }
    
    response = client.post('/documents/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
    
    # Expect failure/validation message
    assert b'File type not allowed' in response.data or b'virus.exe' not in response.data or response.status_code == 400
