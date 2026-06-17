from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.database import init_db
from app.paths import static_dir

STATIC_DIR = static_dir()

app = FastAPI(
    title="다제약물 응급 QR 시스템 MVP",
    description="노인 다제약물 환자의 응급의료정보를 QR 코드에 임베딩.",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(api_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(STATIC_DIR / "index.html")
