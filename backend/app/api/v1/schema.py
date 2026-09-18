from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.auth import User
from app.models.policy import DataSource
from app.schemas.common import StandardResponse
from app.schemas.catalog import SemanticCatalogResponse
from app.services.auth_service import get_current_user, get_effective_role_id
from app.services.semantic_catalog_service import SemanticCatalogService
from app.services.data_source_manager import DataSourceManager, DataSourceUnavailableError

router = APIRouter(prefix="/schema", tags=["Semantic Catalog"])


@router.get("", response_model=StandardResponse[SemanticCatalogResponse])
def get_schema_catalog(
    data_source_id: Optional[int] = Query(None, description="Data source identifier"),
    role_id: Optional[int] = Query(None, description="Role ID for policy filtering (Admin simulation only)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/schema — Returns policy-filtered Semantic Catalog view per role (REQ-CATALOG-01 / Task T-08).
    Strictly fail-closed: If role has no explicit permissions, returns empty tables list.
    Strictly derives effective role from authenticated session.
    """
    # If no data_source_id provided, default to first active DataSource
    if not data_source_id:
        ds = db.query(DataSource).filter(DataSource.is_active == True).first()
        if not ds:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active data source configured in system"
            )
        data_source_id = ds.data_source_id

    effective_role_id = get_effective_role_id(current_user, role_id)

    try:
        target_engine = DataSourceManager.get_engine(db, data_source_id=data_source_id)
        catalog = SemanticCatalogService.get_catalog_for_role(
            db=db,
            data_source_id=data_source_id,
            role_id=effective_role_id,
            business_engine=target_engine
        )
        return StandardResponse(
            success=True,
            message="Semantic Catalog retrieved successfully",
            data=catalog
        )
    except (ValueError, DataSourceUnavailableError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


