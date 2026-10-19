from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_case_or_404, require_api_token, require_case_id
from ..schemas.report import ReportCreate, ReportRead
from ..services import report_service, storage_service

router = APIRouter(tags=["reports"], dependencies=[Depends(require_api_token)])


@router.post("/cases/{case_id}/reports", response_model=ReportRead, status_code=201)
def create_report(
    case_id: str,
    payload: ReportCreate,
    db: Session = Depends(get_db),
) -> ReportRead:
    get_case_or_404(db, case_id)
    return report_service.generate_report(db, case_id, payload.report_type)


@router.get("/cases/{case_id}/reports", response_model=list[ReportRead])
def list_reports(case_id: str, db: Session = Depends(get_db)) -> list[ReportRead]:
    get_case_or_404(db, case_id)
    return report_service.list_reports(db, case_id)


@router.get("/reports/{report_id}", response_model=ReportRead)
def get_report(
    report_id: str,
    case_id: str = Depends(require_case_id),
    db: Session = Depends(get_db),
) -> ReportRead:
    return report_service.get_report(db, report_id, case_id)


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    case_id: str = Depends(require_case_id),
    db: Session = Depends(get_db),
):
    report = report_service.get_report(db, report_id, case_id)
    media_type = "application/pdf" if report.report_type == "pdf" else "application/json"
    try:
        stream = storage_service.iter_object(report.relative_path)
    except storage_service.StorageObjectNotFound as error:
        raise HTTPException(status_code=404, detail="Report file is missing.") from error
    except storage_service.StorageError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return StreamingResponse(
        stream,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{report.filename}"'},
    )
