from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import Role, User
from app.models.policy import DataPolicy, DataSource, SemanticCatalog
from app.schemas.policy import (
    DataPolicyCreate,
    DataPolicyUpdate,
    DataPolicyOut,
    DataPolicyMatrixResponse,
    PolicyMatrixTableItem,
    PolicyMatrixColumnItem,
)
from app.schemas.common import StandardResponse
from app.services.auth_service import get_current_user, require_roles

router = APIRouter(prefix="/policy", tags=["Data Policy Admin Engine"])


@router.get("", response_model=StandardResponse[List[DataPolicyOut]])
def list_policies(
    role_id: Optional[int] = Query(None, description="Filter by role ID"),
    data_source_id: Optional[int] = Query(None, description="Filter by data source ID"),
    table_name: Optional[str] = Query(None, description="Filter by table name"),
    db: Session = Depends(get_db),
):
    """
    Lists all configured data policies matching filter criteria (REQ-AUTH-02).
    """
    query = db.query(DataPolicy)
    if role_id is not None:
        query = query.filter(DataPolicy.role_id == role_id)
    if data_source_id is not None:
        query = query.filter(DataPolicy.data_source_id == data_source_id)
    if table_name is not None:
        query = query.filter(DataPolicy.table_name == table_name)

    policies = query.all()
    results = []
    for p in policies:
        results.append(
            DataPolicyOut(
                policy_id=p.policy_id,
                role_id=p.role_id,
                role_name=p.role.role_name if p.role else None,
                data_source_id=p.data_source_id,
                table_name=p.table_name,
                column_name=p.column_name,
                access_level=p.access_level,
                aggregate_allowed=p.aggregate_allowed,
                row_filter_sql=p.row_filter_sql,
            )
        )
    return StandardResponse(
        success=True,
        message="Policies retrieved successfully",
        data=results,
    )


@router.get("/matrix", response_model=StandardResponse[DataPolicyMatrixResponse])
def get_policy_matrix(
    role_id: int = Query(..., description="Role ID to inspect permissions for"),
    data_source_id: int = Query(1, description="Data source ID"),
    db: Session = Depends(get_db),
):
    """
    Constructs an explicit permissions matrix for a role across all tables and columns
    in the semantic catalog, highlighting fail-closed default-denials (REQ-AUTH-02 / Day 79).
    """
    role = db.query(Role).filter(Role.role_id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found",
        )

    # Fetch all catalog entries for the data source
    catalog_entries = (
        db.query(SemanticCatalog)
        .filter(SemanticCatalog.data_source_id == data_source_id)
        .all()
    )

    # Fetch all existing policies for this role
    policies = (
        db.query(DataPolicy)
        .filter(
            DataPolicy.role_id == role_id,
            DataPolicy.data_source_id == data_source_id,
        )
        .all()
    )

    # Group policies: table-level policies vs column-level policies
    table_policies = {p.table_name: p for p in policies if p.column_name is None}
    col_policies = {(p.table_name, p.column_name): p for p in policies if p.column_name is not None}

    # Group catalog by table
    tables_dict = {}
    for entry in catalog_entries:
        if entry.table_name not in tables_dict:
            tables_dict[entry.table_name] = []
        tables_dict[entry.table_name].append(entry)

    matrix_tables: List[PolicyMatrixTableItem] = []

    for tbl_name, cols in sorted(tables_dict.items()):
        tbl_pol = table_policies.get(tbl_name)
        has_table_policy = tbl_pol is not None

        tbl_access = tbl_pol.access_level if tbl_pol else "denied"
        tbl_agg = tbl_pol.aggregate_allowed if tbl_pol else False
        tbl_rf = tbl_pol.row_filter_sql if tbl_pol else None
        tbl_fail_closed = not has_table_policy or tbl_access == "denied"

        matrix_cols: List[PolicyMatrixColumnItem] = []
        for col in sorted(cols, key=lambda c: c.column_name):
            c_pol = col_policies.get((tbl_name, col.column_name))
            has_col_policy = c_pol is not None

            if has_col_policy:
                c_access = c_pol.access_level
                c_agg = c_pol.aggregate_allowed
                c_fail_closed = c_access == "denied"
                c_pid = c_pol.policy_id
            else:
                # Inherit table-level access unless no table policy exists
                c_access = tbl_access
                c_agg = tbl_agg
                c_fail_closed = tbl_fail_closed
                c_pid = None

            matrix_cols.append(
                PolicyMatrixColumnItem(
                    column_name=col.column_name,
                    access_level=c_access,
                    aggregate_allowed=c_agg,
                    is_explicit=has_col_policy,
                    is_fail_closed_denied=c_fail_closed,
                    sensitivity=col.sensitivity,
                    semantic_type=col.semantic_type,
                    policy_id=c_pid,
                )
            )

        matrix_tables.append(
            PolicyMatrixTableItem(
                table_name=tbl_name,
                access_level=tbl_access,
                aggregate_allowed=tbl_agg,
                row_filter_sql=tbl_rf,
                is_explicit=has_table_policy,
                is_fail_closed_denied=tbl_fail_closed,
                policy_id=tbl_pol.policy_id if tbl_pol else None,
                columns=matrix_cols,
            )
        )

    return StandardResponse(
        success=True,
        message="Policy matrix generated",
        data=DataPolicyMatrixResponse(
            role_id=role.role_id,
            role_name=role.role_name,
            data_source_id=data_source_id,
            tables=matrix_tables,
        ),
    )


@router.post("", response_model=StandardResponse[DataPolicyOut])
def create_or_upsert_policy(
    policy_data: DataPolicyCreate,
    db: Session = Depends(get_db),
):
    """
    Creates or updates a data policy rule. Enforces fail-closed semantics (REQ-AUTH-02).
    """
    # Check if a policy already exists for this role + table + column
    existing = (
        db.query(DataPolicy)
        .filter(
            DataPolicy.role_id == policy_data.role_id,
            DataPolicy.data_source_id == policy_data.data_source_id,
            DataPolicy.table_name == policy_data.table_name,
            DataPolicy.column_name == policy_data.column_name,
        )
        .first()
    )

    if existing:
        existing.access_level = policy_data.access_level
        existing.aggregate_allowed = policy_data.aggregate_allowed
        existing.row_filter_sql = policy_data.row_filter_sql
        db.commit()
        db.refresh(existing)
        target = existing
    else:
        target = DataPolicy(
            role_id=policy_data.role_id,
            data_source_id=policy_data.data_source_id,
            table_name=policy_data.table_name,
            column_name=policy_data.column_name,
            access_level=policy_data.access_level,
            aggregate_allowed=policy_data.aggregate_allowed,
            row_filter_sql=policy_data.row_filter_sql,
        )
        db.add(target)
        db.commit()
        db.refresh(target)

    return StandardResponse(
        success=True,
        message="Policy saved successfully",
        data=DataPolicyOut(
            policy_id=target.policy_id,
            role_id=target.role_id,
            role_name=target.role.role_name if target.role else None,
            data_source_id=target.data_source_id,
            table_name=target.table_name,
            column_name=target.column_name,
            access_level=target.access_level,
            aggregate_allowed=target.aggregate_allowed,
            row_filter_sql=target.row_filter_sql,
        ),
    )


@router.put("/{policy_id}", response_model=StandardResponse[DataPolicyOut])
def update_policy(
    policy_id: int,
    policy_data: DataPolicyUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates an existing data policy row.
    """
    policy = db.query(DataPolicy).filter(DataPolicy.policy_id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found",
        )

    if policy_data.access_level is not None:
        policy.access_level = policy_data.access_level
    if policy_data.aggregate_allowed is not None:
        policy.aggregate_allowed = policy_data.aggregate_allowed
    if policy_data.row_filter_sql is not None:
        policy.row_filter_sql = policy_data.row_filter_sql

    db.commit()
    db.refresh(policy)

    return StandardResponse(
        success=True,
        message="Policy updated successfully",
        data=DataPolicyOut(
            policy_id=policy.policy_id,
            role_id=policy.role_id,
            role_name=policy.role.role_name if policy.role else None,
            data_source_id=policy.data_source_id,
            table_name=policy.table_name,
            column_name=policy.column_name,
            access_level=policy.access_level,
            aggregate_allowed=policy.aggregate_allowed,
            row_filter_sql=policy.row_filter_sql,
        ),
    )


@router.delete("/{policy_id}", response_model=StandardResponse[dict])
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
):
    """
    Deletes a policy row, reverting access to fail-closed default (zero access).
    """
    policy = db.query(DataPolicy).filter(DataPolicy.policy_id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found",
        )

    db.delete(policy)
    db.commit()

    return StandardResponse(
        success=True,
        message=f"Policy {policy_id} deleted. Reverted to fail-closed deny-by-default.",
        data={"deleted_policy_id": policy_id},
    )
