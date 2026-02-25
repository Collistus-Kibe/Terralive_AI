from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from core.config import settings
from core.database import init_db_engine, engine
from core.models import Base
from api.routes import router as api_router
from api.websockets import ws_router
from services.earth_engine import init_ee
from services.rag_engine import init_vertex
from services.firebase_client import init_firebase

app = FastAPI(title=settings.PROJECT_NAME)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Startup ──────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    """Create database tables and authenticate external services."""
    # Initialise the async database engine
    init_db_engine()

    # Import engine reference after initialisation
    from core.database import engine as db_engine

    # Create all SQLAlchemy tables in TiDB
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[DB] Tables created / verified.")

    # Authenticate Google Earth Engine
    await init_ee()

    # Initialise Vertex AI for RAG embeddings
    await init_vertex()

    # Initialise Firebase Admin SDK
    init_firebase()


# ── Include routers ──────────────────────────────────────
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)


# ── Frontend ─────────────────────────────────────────────
@app.get("/")
async def root():
    """Serve the main frontend page."""
    return FileResponse("static/index.html")


@app.get("/health")
async def health_check():
    """Simple health-check endpoint."""
    return {"status": "ok", "project": settings.PROJECT_NAME}
