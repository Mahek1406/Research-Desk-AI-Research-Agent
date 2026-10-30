"""
FastAPI application entrypoint for ResearchDesk.
Provides endpoints for service health verification and structured AI research queries.
"""

from contextlib import asynccontextmanager
import time
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.orchestrator import ResearchOrchestrator
from backend.schemas import HealthResponse, ResearchRequest, ResearchResponse
from backend.utils.logging_config import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle handler."""
    logger.info(f"Starting {settings.app_name} (version {settings.app_version})")
    logger.info(f"LLM Provider: {settings.llm_provider} (Configured: {settings.is_llm_configured})")
    logger.info(f"Search Provider: {settings.search_provider}")
    yield
    logger.info(f"Shutting down {settings.app_name}")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-oriented AI Research Agent API with tool execution, source filtering, and grounded synthesis.",
    lifespan=lifespan,
)

# CORS configuration for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = ResearchOrchestrator()


@app.middleware("http")
async def add_request_trace(request: Request, call_next):
    """Adds a unique Request ID and logs request latency."""
    request_id = str(uuid4())[:8]
    request.state.request_id = request_id
    start_time = time.time()

    logger.info(f"[{request_id}] Incoming request: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        duration = (time.time() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-MS"] = f"{duration:.2f}"
        logger.info(
            f"[{request_id}] Completed {request.method} {request.url.path} - HTTP {response.status_code} ({duration:.2f}ms)"
        )
        return response
    except Exception as exc:
        duration = (time.time() - start_time) * 1000
        logger.error(f"[{request_id}] Unhandled error after {duration:.2f}ms: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred during the research workflow.",
                "request_id": request_id,
            },
        )


@app.get("/", tags=["General"])
async def root():
    """Root info endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs_url": "/docs",
        "health_url": f"{settings.api_prefix}/health",
        "research_url": f"{settings.api_prefix}/research",
    }


@app.get(f"{settings.api_prefix}/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check():
    """Health check endpoint. Exposes service readiness without revealing credentials."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        llm_configured=settings.is_llm_configured,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        search_provider=settings.search_provider,
    )


@app.post(
    f"{settings.api_prefix}/research",
    response_model=ResearchResponse,
    status_code=status.HTTP_200_OK,
    tags=["Research Agent"],
)
async def conduct_research(payload: ResearchRequest):
    """
    Executes an end-to-end grounded research query:
    1. Analyzes question & drafts structured plan
    2. Selects search & retrieval tools
    3. Executes real web searches
    4. Extracts text from top candidate pages
    5. Deduplicates, sanitizes, and filters sources
    6. Synthesizes source-anchored findings and confidence metrics
    7. Validates and returns structured result
    """
    cleaned_question = payload.question.strip()
    if len(cleaned_question) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The research question must be at least 5 characters long.",
        )

    try:
        result = orchestrator.run(payload)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error executing research workflow")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Research agent error: {str(e)}",
        )
