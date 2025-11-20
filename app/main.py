"""Point d'entrée principal de l'application FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from app.api.websocket import router as websocket_router
from app.api.rest import router as rest_router
from app.utils.logger import get_logger


logger = get_logger(__name__)


# Créer l'application FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Brique LangChain modulaire pour Call Shadow AI Agent",
    debug=settings.debug
)


# Configurer CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Inclure les routers
app.include_router(websocket_router, tags=["WebSocket"])
app.include_router(rest_router, prefix="/api", tags=["REST"])


@app.on_event("startup")
async def startup_event():
    """Événement de démarrage de l'application."""
    logger.info(f"🚀 {settings.app_name} v{settings.app_version} démarrage...")
    logger.info(f"📡 WebSocket endpoint: ws://{settings.host}:{settings.port}/ws/conversation")
    logger.info(f"🔌 REST endpoint: http://{settings.host}:{settings.port}/api/process")
    logger.info(f"🤖 Modèle LLM: {settings.openai_model}")


@app.on_event("shutdown")
async def shutdown_event():
    """Événement d'arrêt de l'application."""
    logger.info(f"🛑 {settings.app_name} arrêt...")


@app.get("/", tags=["Health"])
async def root():
    """
    Endpoint racine avec informations de base.
    
    Returns:
        Informations sur l'application
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "endpoints": {
            "websocket": "/ws/conversation",
            "rest": "/api/process",
            "health": "/health",
            "docs": "/docs"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        État de santé de l'application
    """
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )

