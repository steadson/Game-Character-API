from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
from app.api.routes import auth, admin, characters, chat, document
from app.db.session import engine, SessionLocal
from app.db.base import Base
from app.core.config import settings
from app.dependencies import get_db
from app.api.routes import public_chat
from app.services.scheduler import initialize_scheduler


# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # This ensures logs go to console
    ]
)
# Create tables in the database
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="Game Character API with Admin Panel",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/static/templates")

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(characters.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(document.router, prefix=f"{settings.API_V1_STR}/embed")
app.include_router(public_chat.router, tags=["public"])


# Add startup and shutdown event handlers
@app.on_event("startup")
async def startup_event():
    # Initialize the document refresh scheduler
    await initialize_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    # Stop the scheduler
    from app.services.scheduler import document_scheduler
    await document_scheduler.stop()

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request:Request):
    return templates.TemplateResponse("dashboard.html", {"request":request})
@app.get("/characters", response_class=HTMLResponse)
async def characters_page(request: Request):
    return templates.TemplateResponse("characters.html", {"request": request})

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        # Try to execute a simple query to check DB connection
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)