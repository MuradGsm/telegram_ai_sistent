from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.auth import router as auth_router
from app.api.v1.workspaces import router as workspace_router
from app.api.v1.document import router as document_router
from app.api.v1.telegram import router as telegram_router
from app.api.v1.dialogs import router as dialogs_router
from app.api.v1.channel import router as channel_router
from app.api.v1.widget import router as widget_router
from app.api.v1.dialog_ws import router as dialog_ws_router


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://telegram-ai-frontend.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthy")
async def get_health():
    return {"status": "Healthy"}


app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(document_router)
app.include_router(telegram_router)
app.include_router(dialogs_router)
app.include_router(channel_router)
app.include_router(widget_router)
app.include_router(dialog_ws_router)

# widget.js раздаётся отсюда как публичный статический файл.
# CORS для него не нужен: браузер не применяет CORS-политику к <script src="...">.
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")