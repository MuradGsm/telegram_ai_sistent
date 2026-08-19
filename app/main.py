from fastapi import FastAPI
from app.api.v1.auth import router as auth_router

app = FastAPI()


@app.get("/healhty")
async def get_health():
    return {'status': 'Helalthy'}

app.include_router(auth_router)