from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import init_db
    from app.services.vector_store import get_vector_store
    from app.services.scheduler import start_scheduler

    init_db()
    get_vector_store()
    scheduler = start_scheduler()
    yield
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title="SmartReco", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="app/templates")

from app.routers import auth, admin, catalog, events, recommendations  # noqa: E402

app.include_router(auth.router)
app.include_router(admin.router, prefix="/admin")
app.include_router(catalog.router)
app.include_router(events.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
