"""Main entry point for running the DocuMind AI application."""

from app import create_app
from app.extensions import db
from app.models import User, Document, DocumentAnalysis, Report, ChatHistory

app = create_app()

@app.shell_context_processor
def make_shell_context():
    """Provides shell context for flask shell command."""
    return {
        'db': db,
        'User': User,
        'Document': Document,
        'DocumentAnalysis': DocumentAnalysis,
        'Report': Report,
        'ChatHistory': ChatHistory
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
