from fastapi import FastAPI

from app.api.routes import router as api_router
from app.db import models  # noqa: F401  # ensure model metadata is registered
from app.db.database import create_db_and_tables

app = FastAPI(title="Autonomous Credit & Lending Orchestrator")


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


app.include_router(api_router)
