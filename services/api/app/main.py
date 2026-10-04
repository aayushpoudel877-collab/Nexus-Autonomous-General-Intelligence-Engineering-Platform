from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .core.middleware import security_middleware

from .core.config import settings
from .routes.health import router as health_router
from .routes.auth import router as auth_router
from .routes.lms import router as lms_router
from .routes.tutor import router as tutor_router
from .routes.workbench import router as workbench_router
from .routes.research import router as research_router
from .routes.ml_lifecycle import router as ml_lifecycle_router
from .routes.multimodal import router as multimodal_router
from .routes.benchmarks import router as benchmarks_router
from .routes.audit import router as audit_router
from .routes.developer import router as developer_router
from .routes.governance import router as governance_router
from .routes.execution import router as execution_router

app = FastAPI(title="NEXUS-Ω API", version="0.16.0")

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_host_list if settings.is_production else settings.allowed_host_list + ["testserver"],
)

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
app.include_router(multimodal_router, prefix="/api/v1")
app.include_router(benchmarks_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(developer_router, prefix="/api/v1")
app.include_router(governance_router, prefix="/api/v1")
app.include_router(execution_router, prefix="/api/v1")

app.middleware("http")(security_middleware)
