from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.router import api_router
from app.db.base import Base, BusinessBase
from app.db.session import metadata_engine, business_admin_engine

# Initialize tables for dev/local setup if they don't exist
Base.metadata.create_all(bind=metadata_engine)
BusinessBase.metadata.create_all(bind=business_admin_engine)

app = FastAPI(
    title="Intelligent SQL Assistant (Trust Engine) API",
    version="1.2.0",
    description="A Trustworthy Natural-Language Analytics Engine with Verification, Self-Correction and Evidence-Grounded Query Execution.",
    debug=settings.DEBUG
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {
        "app": "Intelligent SQL Assistant (Trust Engine)",
        "version": "1.2.0",
        "docs": "/docs",
        "health": "/api/health"
    }
