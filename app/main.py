from fastapi import FastAPI

app = FastAPI()


@app.get("/healhty")
async def get_health():
    return {'status': 'Helalthy'}