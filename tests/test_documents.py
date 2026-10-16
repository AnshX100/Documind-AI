import pytest
from app.extensions import db
from app.models.document import Document
import io

def test_document_list(client, app, user_a):
    """Test that documents list loads without error."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    response = client.get('/documents/')
    assert response.status_code == 200

def test_dashboard_loads(client, app, user_a):
    """Test dashboard loads."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    response = client.get('/dashboard/')
    assert response.status_code == 200

def test_document_upload_success(client, app, user_a):
    """Test that valid document uploads succeed."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    
    data = {
        'document': (io.BytesIO(b"%PDF-1.4 mock pdf content"), 'test.pdf')
    }
    
    response = client.post('/documents/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
    
    # Normally redirects to dashboard or documents
    assert response.status_code == 200
    
    # Verify in DB
    with app.app_context():
        doc = Document.query.filter_by(user_id=user_a.id, original_filename='test.pdf').first()
        assert doc is not None
        assert doc.status in ['pending', 'processed', 'failed']

def test_document_deletion(client, app, user_a):
    """Test document deletion."""
    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            original_filename="to_delete.pdf",
            filename="to_delete.pdf",
            file_path="/fake/path/to_delete.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="pending"
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id
        
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    
    response = client.post(f'/documents/{doc_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        deleted_doc = Document.query.get(doc_id)
        assert deleted_doc is None


