import pytest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from datetime import datetime

@pytest.fixture
def app():
    # Use testing config
    app = create_app("testing")
    app.config.update({
        "UPLOAD_FOLDER": "tests/temp_uploads"
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def user_a(app):
    with app.app_context():
        user = User(username="usera", email="usera@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        
        # Need to return a detached or fresh instance bound to tests
        return User.query.filter_by(username="usera").first()

@pytest.fixture
def user_b(app):
    with app.app_context():
        user = User(username="userb", email="userb@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        return User.query.filter_by(username="userb").first()
