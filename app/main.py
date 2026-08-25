from fastapi import FastAPI
from app.api.v1.auth import router as auth_router
from app.api.v1.workspaces import router as workspace_router
from app.api.v1.document import router as document_router
from app.api.v1.telegram import router as telegram_router
from app.api.v1.dialogs import router as dialogs_router


app = FastAPI()


@app.get("/healhty")
async def get_health():
    return {'status': 'Helalthy'}

app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(document_router)
app.include_router(telegram_router)
app.include_router(dialogs_router)