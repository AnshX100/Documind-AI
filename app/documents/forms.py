"""WTForms for document upload."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SubmitField
from flask import current_app

class UploadDocumentForm(FlaskForm):
    """Form for uploading documents."""
    
    # We use a dummy list for FileAllowed initially, and update it in __init__ 
    # to read dynamically from current_app config if we wanted. 
    # For now, hardcode the allowed types to match the config so WTF validation passes early.
    document = FileField(
        'Upload Document',
        validators=[
            FileRequired(message='Please select a file to upload.'),
            FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'webp', 'docx'], 'Only PDF, DOCX, PNG, JPG, JPEG, and WEBP files are allowed.')
        ]
    )
    submit = SubmitField('Upload')
