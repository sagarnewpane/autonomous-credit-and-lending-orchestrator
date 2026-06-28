from fastapi import FastAPI

from app.api.admin_routes import admin_router
from app.api.login_routes import auth_router
from app.api.routes import router as api_router

app = FastAPI(title="Autonomous Credit & Lending Orchestrator")


app.include_router(api_router)
app.include_router(auth_router)
app.include_router(admin_router)
