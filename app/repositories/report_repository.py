"""Report repository for database operations on generated reports."""

from typing import List, Optional
from app.repositories.base_repository import BaseRepository
from app.models.report import Report
from app.extensions import db


class ReportRepository(BaseRepository[Report]):
    """Repository handling report entity access and queries."""

    def __init__(self) -> None:
        super().__init__(Report)

    def create(self, report: Report) -> Report:
        """Create and persist a new Report record."""
        db.session.add(report)
        db.session.commit()
        return report

    def update(self, report: Report) -> Report:
        """Persist changes to an existing Report record."""
        db.session.commit()
        return report

    def delete(self, report_id: int) -> bool:
        """Delete a report record by ID."""
        report = self.get_by_id(report_id)
        if report:
            db.session.delete(report)
            db.session.commit()
            return True
        return False

    def get_by_id_and_user(self, report_id: int, user_id: int) -> Optional[Report]:
        """Fetch a report ensuring it belongs to the specified user."""
        return Report.query.filter_by(id=report_id, user_id=user_id).first()

    def get_all_by_user(self, user_id: int) -> List[Report]:
        """Fetch all reports owned by a user, newest first."""
        return Report.query.filter_by(user_id=user_id).order_by(Report.created_at.desc()).all()

    def get_recent_by_user(self, user_id: int, limit: int = 5) -> List[Report]:
        """Fetch the most recent reports for a user."""
        return Report.query.filter_by(user_id=user_id).order_by(Report.created_at.desc()).limit(limit).all()

    def update_status(self, report_id: int, status: str) -> Optional[Report]:
        """Update report status ('pending', 'generating', 'completed', 'failed')."""
        report = self.get_by_id(report_id)
        if report:
            report.status = status
            db.session.commit()
        return report
