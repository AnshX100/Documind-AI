"""Documents routes and blueprint registration."""

import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import current_user, login_required

from app.documents.forms import UploadDocumentForm
from app.services import document_service, document_repository

documents_bp = Blueprint('documents', __name__, url_prefix='/documents')

@documents_bp.route('/', methods=['GET'])
@login_required
def index():
    """List documents with pagination, search, and filtering."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '')
    status_filter = request.args.get('status', 'all')
    
    pagination = document_repository.get_user_documents_paginated(
        user_id=current_user.id,
        page=page,
        per_page=10,
        search_query=search_query,
        status_filter=status_filter
    )
    
    return render_template(
        'documents/index.html',
        title='My Documents',
        pagination=pagination,
        search_query=search_query,
        status_filter=status_filter
    )

@documents_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload a new document."""
    form = UploadDocumentForm()
    
    if form.validate_on_submit():
        success, message, document = document_service.upload_document(
            user_id=current_user.id,
            file=form.document.data
        )
        
        if success:
            flash(message, 'success')
            return redirect(url_for('documents.index'))
        else:
            flash(message, 'danger')
            
    return render_template('documents/upload.html', title='Upload Document', form=form)

@documents_bp.route('/<int:id>', methods=['GET'])
@login_required
def detail(id):
    """View document details."""
    document = document_repository.get_by_id_and_user(id, current_user.id)
    if not document:
        flash('Document not found or you do not have permission to view it.', 'danger')
        return redirect(url_for('documents.index'))
        
    # Determine if it's an image for preview
    is_image = document.file_type.lower() in ['image/png', 'image/jpeg', 'image/jpg']
    is_pdf = document.file_type.lower() == 'application/pdf'
    
    return render_template(
        'documents/detail.html', 
        title=document.original_filename, 
        document=document,
        is_image=is_image,
        is_pdf=is_pdf
    )

@documents_bp.route('/<int:id>/download', methods=['GET'])
@login_required
def download(id):
    """Securely download a document."""
    success, result, document = document_service.get_document_for_download(id, current_user.id)
    
    if not success:
        flash(result, 'danger')
        return redirect(url_for('documents.index'))
        
    return send_file(
        result,
        as_attachment=True,
        download_name=document.original_filename,
        mimetype=document.file_type
    )

@documents_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Securely delete a document."""
    success, message = document_service.delete_document(id, current_user.id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('documents.index'))
