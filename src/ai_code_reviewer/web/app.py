"""FastAPI web application for AI Code Reviewer."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routers import analysis, config, costs, history

app = FastAPI(
    title="AI Code Reviewer",
    description="AI-powered code review tool for GitHub pull requests",
    version="1.0.0",
)

# CORS - allow localhost for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files directory
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Jinja2 templates
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Register API routers
app.include_router(analysis.router)
app.include_router(history.router)
app.include_router(config.router)
app.include_router(costs.router)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint - serves the main page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/analyze", response_class=HTMLResponse)
async def analyze_page(request: Request):
    """Analyze page - dedicated PR analysis with progress tracking."""
    return templates.TemplateResponse("analyze.html", {"request": request})
