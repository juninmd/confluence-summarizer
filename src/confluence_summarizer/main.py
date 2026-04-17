import logging
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from src.confluence_summarizer.config import settings
from src.confluence_summarizer.database import init_db
from src.confluence_summarizer.deps import limiter
from src.confluence_summarizer.routes import router
from src.confluence_summarizer.services import confluence

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing application...")
    init_db()
    await confluence.init_client()
    yield
    # Shutdown
    logger.info("Shutting down application...")
    await confluence.close_client()


app = FastAPI(
    title="Confluence Summarizer",
    description="A service to ingest, index, analyze, and refine Confluence documentation.",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter

# Need to import _rate_limit_exceeded_handler inside to avoid slowapi init issue
from slowapi import _rate_limit_exceeded_handler  # noqa: E402

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    return response


app.include_router(router)
