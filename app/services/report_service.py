"""Report Service orchestrator for validating inputs, assembling datasets, building PDFs, and managing report lifecycles."""

import os
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from flask import current_app

from app.models.report import Report
from app.repositories.report_repository import ReportRepository
from app.services.report_data_service import ReportDataService
from app.services.report_pdf_service import ReportPDFService

logger = logging.getLogger(__name__)

VALID_REPORT_TYPES = {
    "EXECUTIVE": "Executive Financial Summary",
    "SPENDING": "Spending Analysis Report",
    "ANOMALY": "Anomaly & Risk Report",
    "DUE_DILIGENCE": "Due Diligence Report",
    "COMPREHENSIVE": "Comprehensive Financial Report"
}

VALID_PERIODS = {
    "all_time", "current_month", "previous_month",
    "current_quarter", "previous_quarter", "current_year", "previous_year", "custom"
}


class ReportService:
    """Orchestrator for financial report generation, secure storage, and user-isolated downloads."""

    def __init__(
        self,
        report_repo: Optional[ReportRepository] = None,
        data_service: Optional[ReportDataService] = None,
        pdf_service: Optional[ReportPDFService] = None
    ) -> None:
        self.report_repo = report_repo or ReportRepository()
        self.data_service = data_service or ReportDataService()
        self.pdf_service = pdf_service or ReportPDFService()

    def generate_report(
        self,
        user_id: int,
        report_type: str,
        period: str = "all_time",
        report_title: Optional[str] = None,
        custom_start: Optional[Any] = None,
        custom_end: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Generates a professional financial PDF report and persists metadata record."""
        type_clean = (report_type or "").upper().strip()
        if type_clean not in VALID_REPORT_TYPES:
            return {"status": "error", "message": f"Invalid report type '{report_type}'."}

        period_clean = (period or "all_time").lower().strip()
        if period_clean not in VALID_PERIODS:
            return {"status": "error", "message": f"Invalid reporting period '{period}'."}

        title_clean = (report_title or "").strip()
        if not title_clean:
            title_clean = f"{VALID_REPORT_TYPES[type_clean]}"
        elif len(title_clean) > 200:
            title_clean = title_clean[:200]

        # Validate custom period bounds early
        if period_clean == "custom":
            if not custom_start or not custom_end:
                return {"status": "error", "message": "Custom period requires both start and end dates."}
            start_d = self.data_service._to_date(custom_start)
            end_d = self.data_service._to_date(custom_end)
            if not start_d or not end_d:
                return {"status": "error", "message": "Invalid date format for custom period. Expected YYYY-MM-DD."}
            if start_d > end_d:
                return {"status": "error", "message": "Invalid custom date range. Start date must be before or equal to end date."}

        # 1. Create initial DB record in 'generating' status
        report_record = Report(
            user_id=user_id,
            report_name=title_clean,
            report_type=type_clean,
            status="generating",
            format="pdf"
        )
        report_record = self.report_repo.create(report_record)

        # Generate opaque stored filename (<uuid>.pdf) to prevent path traversal & user spoofing
        opaque_filename = f"report_{user_id}_{uuid.uuid4().hex}.pdf"
        reports_dir = self._get_reports_dir()
        file_disk_path = os.path.join(reports_dir, opaque_filename)

        try:
            # 2. Assemble verified dataset
            dataset = self.data_service.get_report_dataset(
                user_id=user_id,
                report_type=type_clean,
                period=period_clean,
                custom_start=custom_start,
                custom_end=custom_end
            )

            # 3. Build PDF file on disk
            self.pdf_service.generate_pdf(
                report_name=title_clean,
                dataset=dataset,
                output_path=file_disk_path
            )

            # 4. Update DB record to completed
            overview = dataset.get("overview", {})
            report_record.period_start = dataset.get("period_start")
            report_record.period_end = dataset.get("period_end")
            report_record.total_expenses = overview.get("total_spending", 0.0)
            report_record.total_documents = overview.get("analyzed_documents", 0)
            report_record.file_path = opaque_filename
            report_record.status = "completed"

            self.report_repo.update(report_record)

            return {
                "status": "success",
                "message": "Report generated successfully.",
                "report_id": report_record.id,
                "report": report_record
            }

        except Exception as e:
            logger.error(f"Failed to generate report for user {user_id}: {e}", exc_info=True)
            # Cleanup disk file if partially created
            if os.path.exists(file_disk_path):
                try:
                    os.remove(file_disk_path)
                except OSError:
                    pass

            # Update status to failed
            report_record.status = "failed"
            self.report_repo.update(report_record)

            return {
                "status": "error",
                "message": f"An error occurred while compiling the report PDF: {str(e)}",
                "report_id": report_record.id
            }

    def get_user_reports(self, user_id: int) -> List[Report]:
        """Fetch all reports for a user."""
        return self.report_repo.get_all_by_user(user_id)

    def get_user_report(self, report_id: int, user_id: int) -> Optional[Report]:
        """Fetch a specific report enforcing ownership."""
        return self.report_repo.get_by_id_and_user(report_id, user_id)

    def get_report_download_path(self, report_id: int, user_id: int) -> Tuple[Optional[str], Optional[str]]:
        """Validates ownership and returns (reports_directory, safe_filename) for secure download."""
        report = self.get_user_report(report_id, user_id)
        if not report or not report.file_path or report.status != "completed":
            return None, None

        # Sanitize filename using os.path.basename to prevent path traversal
        safe_filename = os.path.basename(report.file_path)
        reports_dir = self._get_reports_dir()
        full_path = os.path.join(reports_dir, safe_filename)

        if not os.path.exists(full_path):
            logger.error(f"Report file missing on disk: {full_path}")
            return None, None

        return reports_dir, safe_filename

    def delete_report(self, report_id: int, user_id: int) -> bool:
        """Deletes a report record and its associated disk file securely."""
        report = self.get_user_report(report_id, user_id)
        if not report:
            return False

        if report.file_path:
            safe_filename = os.path.basename(report.file_path)
            full_path = os.path.join(self._get_reports_dir(), safe_filename)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except OSError as ex:
                    logger.warning(f"Could not remove report file {full_path}: {ex}")

        return self.report_repo.delete(report.id)

    def _get_reports_dir(self) -> str:
        """Resolves the report storage directory inside uploads/reports."""
        if current_app:
            upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        else:
            upload_folder = "uploads"

        reports_dir = os.path.join(upload_folder, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        return reports_dir
