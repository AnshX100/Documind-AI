from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded for local execution entrypoint
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

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
