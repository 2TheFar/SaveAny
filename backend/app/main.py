from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.files import router as files_router
from app.api.health import router as health_router
from app.api.media import router as media_router
from app.api.platforms import router as platforms_router
from app.api.system import router as system_router
from app.api.tasks import router as tasks_router
from app.api.thumbnails import router as thumbnails_router
from app.core.errors import SaveAnyBackendError

app = FastAPI(title="SaveAny Backend", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(system_router)
app.include_router(media_router)
app.include_router(platforms_router)
app.include_router(tasks_router)
app.include_router(files_router)
app.include_router(thumbnails_router)


@app.exception_handler(SaveAnyBackendError)
async def saveany_error_handler(_request, exc: SaveAnyBackendError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message, "code": exc.code})
