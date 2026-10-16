from flask import current_app
from werkzeug.local import LocalProxy

from app.services.auth_service import AuthService
from app.services.storage_service import StorageService
from app.services.document_service import DocumentService
from app.services.ocr_service import OCRService
from app.services.ai_service import AIService
from app.services.document_processing_service import DocumentProcessingService
from app.services.financial_intelligence_service import FinancialIntelligenceService
from app.services.anomaly_detection_service import AnomalyDetectionService
from app.services.due_diligence_service import DueDiligenceService

from app.repositories.user_repository import UserRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_analysis_repository import DocumentAnalysisRepository
from app.repositories.report_repository import ReportRepository

from app.services.report_data_service import ReportDataService
from app.services.report_pdf_service import ReportPDFService
from app.services.report_service import ReportService

# Repositories
user_repository = UserRepository()
document_repository = DocumentRepository()
document_analysis_repository = DocumentAnalysisRepository()
report_repository = ReportRepository()

# Services
auth_service = AuthService(user_repo=user_repository)

# LocalProxy for StorageService (needs app config)
def _get_storage_service():
    return StorageService(
        upload_folder=current_app.config['UPLOAD_FOLDER'],
        max_content_length=current_app.config['MAX_CONTENT_LENGTH'],
        allowed_extensions=current_app.config['ALLOWED_EXTENSIONS']
    )

storage_service = LocalProxy(_get_storage_service)
document_service = DocumentService(document_repo=document_repository, storage_service=storage_service)

# LocalProxy for OCRService (needs app config for tesseract)
def _get_ocr_service():
    return OCRService(
        tesseract_cmd=current_app.config.get('TESSERACT_CMD'),
        language=current_app.config.get('OCR_LANGUAGE', 'eng')
    )

ocr_service = LocalProxy(_get_ocr_service)

# LocalProxy for AIService (needs app config)
def _get_ai_service():
    return AIService(
        provider=current_app.config.get('AI_PROVIDER', 'none'),
        openai_api_key=current_app.config.get('OPENAI_API_KEY'),
        model=current_app.config.get('OPENAI_MODEL', 'gpt-4o-mini')
    )

ai_service = LocalProxy(_get_ai_service)

document_processing_service = DocumentProcessingService(
    document_repo=document_repository,
    analysis_repo=document_analysis_repository,
    ocr_service=ocr_service,
    ai_service=ai_service
)

financial_intelligence_service = FinancialIntelligenceService(
    document_repo=document_repository,
    analysis_repo=document_analysis_repository
)

anomaly_detection_service = AnomalyDetectionService(
    document_repo=document_repository,
    analysis_repo=document_analysis_repository
)

due_diligence_service = DueDiligenceService(
    financial_service=financial_intelligence_service,
    anomaly_service=anomaly_detection_service
)

report_data_service = ReportDataService(
    financial_service=financial_intelligence_service,
    anomaly_service=anomaly_detection_service,
    due_diligence_service=due_diligence_service,
    document_repo=document_repository
)

report_pdf_service = ReportPDFService()

report_service = ReportService(
    report_repo=report_repository,
    data_service=report_data_service,
    pdf_service=report_pdf_service
)

from app.services.intent_detection_service import IntentDetectionService
from app.services.evidence_retrieval_service import EvidenceRetrievalService
from app.services.answer_generation_service import AnswerGenerationService
from app.services.financial_assistant_service import FinancialAssistantService

intent_detection_service = IntentDetectionService()
evidence_retrieval_service = EvidenceRetrievalService(
    financial_service=financial_intelligence_service,
    anomaly_service=anomaly_detection_service,
    due_diligence_service=due_diligence_service,
    document_repo=document_repository,
    analysis_repo=document_analysis_repository
)
answer_generation_service = AnswerGenerationService()

financial_assistant_service = FinancialAssistantService(
    intent_detector=intent_detection_service,
    evidence_retriever=evidence_retrieval_service,
    answer_generator=answer_generation_service
)

__all__ = [
    "auth_service", 
    "storage_service", 
    "document_service", 
    "ocr_service", 
    "ai_service",
    "document_processing_service",
    "financial_intelligence_service",
    "anomaly_detection_service",
    "due_diligence_service",
    "report_data_service",
    "report_pdf_service",
    "report_service",
    "intent_detection_service",
    "evidence_retrieval_service",
    "answer_generation_service",
    "financial_assistant_service",
    "user_repository",
    "document_repository",
    "document_analysis_repository",
    "report_repository"
]

