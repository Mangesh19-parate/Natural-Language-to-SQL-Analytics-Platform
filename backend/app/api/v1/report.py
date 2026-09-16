import os
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit import Report
from app.models.auth import User
from app.schemas.report import (
    ReportExportRequest,
    ReportGenerateResponse,
)
from app.services.auth_service import get_current_user
from app.services.report_generator import ReportGeneratorService

router = APIRouter(prefix="", tags=["Reporting"])
report_service = ReportGeneratorService()


@router.post(
    "/pdf",
    response_model=ReportGenerateResponse,
    summary="Generate PDF Report (REQ-RPT-01 / Rule R8.3)",
)
def export_pdf_report(
    request: ReportExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a high-fidelity PDF report for single query or full session scope.
    Includes NL question, executed SQL, 5-part Reliability Score breakdown, validation evidence, and data preview.
    Ties ownership to authenticated current_user.
    """
    try:
        report_id, file_path, content_hash = report_service.generate_pdf(request, user_id=current_user.user_id)
        
        # Persist report record in metadata DB
        created_at_dt = datetime.now(timezone.utc)
        try:
            report_record = Report(
                report_id=report_id,
                user_id=current_user.user_id,
                title=request.title,
                format="pdf",
                file_path=file_path,
                scope=request.scope,
                status="ready",
                content_hash=content_hash,
                created_at=created_at_dt,
            )
            db.add(report_record)
            db.commit()
        except Exception:
            db.rollback()

        return ReportGenerateResponse(
            report_id=report_id,
            title=request.title,
            format="pdf",
            scope=request.scope,
            status="ready",
            created_at=created_at_dt.isoformat(),
            download_url=f"/api/v1/report/{report_id}/download",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF report generation failed: {str(e)}",
        )


@router.post(
    "/excel",
    response_model=ReportGenerateResponse,
    summary="Generate Excel Workbook Report (REQ-RPT-01 / Rule R8.3)",
)
def export_excel_report(
    request: ReportExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a styled multi-sheet Excel report with summary metadata and formatted data tables.
    Ties ownership to authenticated current_user.
    """
    try:
        report_id, file_path, content_hash = report_service.generate_excel(request, user_id=current_user.user_id)
        
        created_at_dt = datetime.now(timezone.utc)
        try:
            report_record = Report(
                report_id=report_id,
                user_id=current_user.user_id,
                title=request.title,
                format="xlsx",
                file_path=file_path,
                scope=request.scope,
                status="ready",
                content_hash=content_hash,
                created_at=created_at_dt,
            )
            db.add(report_record)
            db.commit()
        except Exception:
            db.rollback()

        return ReportGenerateResponse(
            report_id=report_id,
            title=request.title,
            format="xlsx",
            scope=request.scope,
            status="ready",
            created_at=created_at_dt.isoformat(),
            download_url=f"/api/v1/report/{report_id}/download",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Excel report generation failed: {str(e)}",
        )


@router.get(
    "/{report_id}/download",
    summary="Download Generated Report (REQ-RPT-02 Owner-Only Download)",
)
def download_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Streams the generated report file strictly for the authenticated owner or admin (REQ-RPT-02).
    """
    report_record = db.query(Report).filter(Report.report_id == report_id).first()
    if not report_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID '{report_id}' not found.",
        )

    user_role_name = current_user.role.role_name.lower() if current_user.role else "viewer"
    if report_record.user_id != current_user.user_id and user_role_name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not authorized to download this report.",
        )

    file_info = report_service.get_report_file(report_id)
    if not file_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report file for '{report_id}' is missing from storage.",
        )

    file_path, media_type = file_info
    filename = os.path.basename(file_path)

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
    )


@router.get(
    "/list",
    summary="List Generated Reports",
)
def list_reports(
    user_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists reports belonging to the authenticated user (or all if admin).
    """
    try:
        user_role_name = current_user.role.role_name.lower() if current_user.role else "viewer"
        query = db.query(Report)

        if user_role_name == "admin" and user_id is not None:
            query = query.filter(Report.user_id == user_id)
        elif user_role_name != "admin":
            query = query.filter(Report.user_id == current_user.user_id)

        records = query.order_by(Report.created_at.desc()).limit(20).all()
        return {
            "success": True,
            "reports": [
                {
                    "report_id": r.report_id,
                    "title": r.title,
                    "format": r.format,
                    "scope": r.scope,
                    "status": r.status,
                    "content_hash": r.content_hash,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "download_url": f"/api/v1/report/{r.report_id}/download",
                }
                for r in records
            ],
        }
    except Exception as e:
        return {"success": True, "reports": []}

