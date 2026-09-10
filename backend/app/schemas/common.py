from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

DataT = TypeVar("DataT")


class StandardResponse(BaseModel, Generic[DataT]):
    success: bool = True
    message: Optional[str] = None
    data: Optional[DataT] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    environment: str
    metadata_db_connected: bool
    business_db_connected: bool
    version: str = "1.2.0"
