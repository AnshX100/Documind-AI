"""Documents routes and blueprint registration."""

import os
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, abort
from flask_login import current_user, login_required

from app.documents.forms import UploadDocumentForm
from app.services import document_service, document_repository, document_processing_service, anomaly_detection_service
from app.extensions import limiter

logger = logging.getLogger(__name__)
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
@limiter.limit("10 per minute", methods=["POST"])
def upload():
    """Upload a new document and process it via OCR immediately."""
    form = UploadDocumentForm()
    
    if form.validate_on_submit():
        # 1. Upload and save the file securely
        success, message, document = document_service.upload_document(
            user_id=current_user.id,
            file=form.document.data
        )
        
        if success and document:
            # 2. Immediately attempt to process via OCR
            ocr_success, ocr_message = document_processing_service.process_document(
                document_id=document.id,
                user_id=current_user.id
            )
            
            if ocr_success:
                flash(f"{message} OCR completed successfully.", 'success')
            else:
                flash(f"{message} However, OCR failed: {ocr_message}", 'warning')
                
            return redirect(url_for('documents.detail', id=document.id))
        else:
            flash(message, 'danger')
            
    return render_template('documents/upload.html', title='Upload Document', form=form)

@documents_bp.route('/<int:id>/process', methods=['POST'])
@login_required
def process(id):
    """Manually trigger OCR processing for a document."""
    success, message = document_processing_service.process_document(
        document_id=id,
        user_id=current_user.id
    )
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('documents.detail', id=id))

@documents_bp.route('/<int:id>/analyze', methods=['POST'])
@login_required
def analyze(id):
    """Manually trigger financial data extraction without re-running OCR."""
    success, message = document_processing_service.reanalyze_document(
        document_id=id,
        user_id=current_user.id
    )
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('documents.detail', id=id))

@documents_bp.route('/<int:id>', methods=['GET'])
@login_required
def detail(id):
    """View document details."""
    document = document_repository.get_by_id_and_user(id, current_user.id)
    if not document:
        abort(404)
        
    # Determine if it's an image for preview
    is_image = document.file_type.lower() in ['image/png', 'image/jpeg', 'image/jpg', 'image/webp']
    is_pdf = document.file_type.lower() == 'application/pdf'
    is_docx = document.file_type.lower() == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    
    docx_html = None
    if is_docx:
        try:
            import mammoth
            import bleach
            with open(document.file_path, "rb") as docx_file:
                result = mammoth.convert_to_html(docx_file)
                raw_html = result.value
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
                docx_html = bleach.clean(
                    raw_html,
                    tags=allowed_tags,
                    attributes=allowed_attrs,
                    protocols=['http', 'https', 'mailto', 'data'],
                    strip=True
                )
        except Exception as e:
            logger.error(f"Failed to load DOCX preview for document {id}: {e}")
            docx_html = "<div class='alert alert-danger'>Failed to load DOCX preview. Please verify file integrity.</div>"
    
    formatted_text = None
    effective_tax_rate = 0.0
    evidence_items = []
    arithmetic_valid = True
    arithmetic_diff = 0.0

    if document.analysis:
        subtotal = float(document.analysis.subtotal_amount or 0.0)
        tax = float(document.analysis.tax_amount or 0.0)
        total = float(document.analysis.total_amount or 0.0)
        
        if subtotal > 0 and tax > 0:
            effective_tax_rate = round((tax / subtotal) * 100, 2)
            
        arithmetic_diff = round(abs((subtotal + tax) - total), 2)
        if subtotal > 0 and arithmetic_diff > 0.05:
            arithmetic_valid = False

        if document.analysis.raw_text:
            from app.services.ocr_formatter_service import OCRFormatterService
            formatter = OCRFormatterService()
            formatted_text = formatter.format_text(document.analysis.raw_text)

        conf = float(document.analysis.confidence_score or 0.0)
        evidence_items = [
            {
                "field": "Vendor Name",
                "value": document.analysis.vendor_name or "Vendor not detected",
                "confidence": conf,
                "verified": bool(document.analysis.vendor_name)
            },
            {
                "field": "Invoice / Receipt Number",
                "value": document.analysis.invoice_number or "Invoice number missing",
                "confidence": conf,
                "verified": bool(document.analysis.invoice_number)
            },
            {
                "field": "Invoice Date",
                "value": document.analysis.invoice_date.strftime('%d %b %Y') if document.analysis.invoice_date else "Date not detected",
                "confidence": conf,
                "verified": bool(document.analysis.invoice_date)
            },
            {
                "field": "Total Amount",
                "value": f"₹{total:,.2f}",
                "confidence": conf,
                "verified": total > 0
            },
            {
                "field": "Tax Amount",
                "value": f"₹{tax:,.2f}",
                "confidence": conf,
                "verified": True
            },
            {
                "field": "Category",
                "value": document.analysis.category or "General",
                "confidence": conf,
                "verified": True
            }
        ]
    
    anomalies = anomaly_detection_service.get_document_anomalies(document.id, current_user.id)
    
    return render_template(
        'documents/detail.html', 
        title=document.original_filename, 
        document=document,
        is_image=is_image,
        is_pdf=is_pdf,
        is_docx=is_docx,
        docx_html=docx_html,
        formatted_text=formatted_text,
        anomalies=anomalies,
        effective_tax_rate=effective_tax_rate,
        evidence_items=evidence_items,
        arithmetic_valid=arithmetic_valid,
        arithmetic_diff=arithmetic_diff
    )


@documents_bp.route('/<int:id>/download', methods=['GET'])
@login_required
def download(id):
    """Securely download a document."""
    success, result, document = document_service.get_document_for_download(id, current_user.id)
    
    if not success:
        abort(404)
        
    return send_file(
        result,
        as_attachment=True,
        download_name=document.original_filename,
        mimetype=document.file_type
    )

@documents_bp.route('/<int:id>/preview', methods=['GET'])
@login_required
def preview(id):
    """Securely preview a document inline (no automatic download)."""
    success, result, document = document_service.get_document_for_download(id, current_user.id)
    
    if not success:
        abort(404)
        
    return send_file(
        result,
        as_attachment=False,
        mimetype=document.file_type
    )

@documents_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Securely delete a document."""
    success, message = document_service.delete_document(id, current_user.id)
    
    if success:
        flash(message, 'success')
        return redirect(url_for('documents.index'))
    else:
        if "Document not found or access denied" in message:
            abort(404)
        flash(message, 'danger')
        
    return redirect(url_for('documents.index'))

@documents_bp.route('/<int:id>/download-text', methods=['GET'])
@login_required
def download_text(id):
    """Download extracted formatted OCR text as a txt file."""
    document = document_repository.get_by_id_and_user(id, current_user.id)
    if not document or not document.analysis or not document.analysis.raw_text:
        abort(404)
        
    from app.services.ocr_formatter_service import OCRFormatterService
    from flask import Response
    import re
    
    formatter = OCRFormatterService()
    formatted_text = formatter.format_text(document.analysis.raw_text)
    
    # Filename format: invoice_{invoice_number or id}_extracted.txt
    inv_num = document.analysis.invoice_number
    if inv_num and inv_num.strip() != "":
        safe_inv_num = re.sub(r'[^a-zA-Z0-9_\-]', '_', inv_num.strip())
        filename = f"invoice_{safe_inv_num}_extracted.txt"
    else:
        filename = f"invoice_{document.id}_extracted.txt"
        
    return Response(
        formatted_text,
        mimetype="text/plain",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )
