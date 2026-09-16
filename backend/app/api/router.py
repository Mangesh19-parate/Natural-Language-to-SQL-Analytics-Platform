from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.schema import router as schema_router
from app.api.v1.intent import router as intent_router
from app.api.v1.sql import router as sql_router
from app.api.v1.lab import router as lab_router
from app.api.v1.vis import router as vis_router
from app.api.v1.report import router as report_router
from app.api.v1.optimize import router as optimize_router
from app.api.v1.policy import router as policy_router
from app.api.v1.history import router as history_router
from app.api.v1.replay import router as replay_router
from app.api.v1.observatory import router as observatory_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="")
api_router.include_router(auth_router, prefix="")
api_router.include_router(schema_router, prefix="")
api_router.include_router(intent_router, prefix="")
api_router.include_router(sql_router, prefix="")
api_router.include_router(lab_router, prefix="")
api_router.include_router(vis_router, prefix="/vis")
api_router.include_router(report_router, prefix="/report")
api_router.include_router(optimize_router, prefix="/optimize")
api_router.include_router(policy_router, prefix="")
api_router.include_router(history_router, prefix="")
api_router.include_router(replay_router, prefix="")
api_router.include_router(observatory_router, prefix="")




