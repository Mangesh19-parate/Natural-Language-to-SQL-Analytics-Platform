from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.schema import router as schema_router
from app.api.v1.intent import router as intent_router
from app.api.v1.sql import router as sql_router
from app.api.v1.lab import router as lab_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="")
api_router.include_router(auth_router, prefix="")
api_router.include_router(schema_router, prefix="")
api_router.include_router(intent_router, prefix="")
api_router.include_router(sql_router, prefix="")
api_router.include_router(lab_router, prefix="")

