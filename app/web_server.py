from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Standup Reels AI Agent")

@app.get("/")
@app.get("/health")
async def health_check():
    return JSONResponse(
        status_code=200,
        content={"status": "online", "agent": "Standup Reels Bot", "uptime": "healthy"}
    )

