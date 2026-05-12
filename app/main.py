from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_swagger import patch_fastapi
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints.users import router as users_router 
from app.api.endpoints.login import router as login_router
from app.api.endpoints.videos import router as videos_router
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(app:FastAPI):
    Base.metadata.create_all(engine)
    print("✅ Database tables created successfully")
    print("Service is running..")
    yield
    print("Shuting down..")


app = FastAPI(
    title="Todo Application",
    version="0.1.0",
    docs_url=None,
    swagger_ui_oauth2_redirect_url=None,
    lifespan=lifespan
)
patch_fastapi(app)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(login_router)
app.include_router(users_router)
app.include_router(videos_router)