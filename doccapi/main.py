from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from doccapi.database import database
from doccapi.routers.user import router as user_router
from doccapi.routers.role import router as role_router
from doccapi.routers.uploads import router as uploads_router
from doccapi.routers.form import router as form_router
from doccapi.routers.workflow import router as workflow_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # connect database
    await database.connect()
    yield
    # disconnect database
    await database.disconnect()

app = FastAPI(
    title="Docc Backend API",
    description="API for Documents Management in CIT",
    lifespan=lifespan
)

origins = [
    "http://localhost",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router, prefix="/api/user", tags=["User"])
app.include_router(role_router, prefix="/api/role", tags=["Role"])
app.include_router(uploads_router, prefix="/api/upload", tags=["Uploads"])
app.include_router(form_router, prefix="/api/form", tags=["Form"])
app.include_router(workflow_router, prefix="/api/workflow", tags=["Workflow"])

