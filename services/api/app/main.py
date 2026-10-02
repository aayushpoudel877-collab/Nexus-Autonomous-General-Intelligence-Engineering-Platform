from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .routes.health import router as health_router
from .routes.auth import router as auth_router
from .routes.lms import router as lms_router
from .routes.tutor import router as tutor_router
from .routes.workbench import router as workbench_router
from .routes.research import router as research_router
from .routes.ml_lifecycle import router as ml_lifecycle_router

app = FastAPI(title="NEXUS-Ω API", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(lms_router, prefix="/api/v1")
app.include_router(tutor_router, prefix="/api/v1")
app.include_router(workbench_router, prefix="/api/v1")
app.include_router(research_router, prefix="/api/v1")
app.include_router(ml_lifecycle_router, prefix="/api/v1")
