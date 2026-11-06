from app.api.routes.ai_detector_explanations import (
    router as ai_detector_explanations_router,)
from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine
from app.api.routes.auth import router as auth_router
from app.api.routes.admin import router as admin_router
from app.api.routes.model_comparer import router as model_comparer_router
from app.api.routes.reference import router as reference_router
from app.api.routes.scan import (
    router as scans_router,
)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
)
app.include_router(admin_router)
app.include_router(model_comparer_router)
app.include_router(reference_router)
app.include_router(auth_router)
app.include_router(scans_router)
app.include_router(ai_detector_explanations_router)

@app.get("/")
def root():
    return {
        "message": "FTER Plagiarism and AI Detection API is running",
        "environment": settings.app_env,
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/health/database")
def database_health():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            value = result.scalar()

        return {
            "database": "connected",
            "test_query_result": value,
        }

    except Exception as e:
        return {
            "database": "error",
            "message": str(e),
        }
@app.get("/health/schema")
def schema_health():
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """)
            )

            table_count = result.scalar()

        return {
            "database": "connected",
            "public_table_count": table_count,
        }

    except Exception as e:
        return {
            "database": "error",
            "message": str(e),
        }
@app.get("/health/vector")
def vector_health():
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("""
                    SELECT extname
                    FROM pg_extension
                    WHERE extname = 'vector'
                """)
            )

            extension = result.scalar()

        return {
            "pgvector": "installed" if extension else "not installed"
        }

    except Exception as e:
        return {
            "pgvector": "error",
            "message": str(e),
        }

app.include_router(auth_router)