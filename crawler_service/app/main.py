from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.crawler import crawler
from app.db import DB
import asyncio
import uvicorn
from dotenv import load_dotenv
import os

load_dotenv()

@asynccontextmanager
async def fastapi_lifespan(app: FastAPI):
    db = DB()
    await db.connect(os.getenv("DATABASE_URL"))
    yield
    await db.dispose()

app = FastAPI(lifespan=fastapi_lifespan, openapi_url="/api/v1/crawler/openapi.json", docs_url="/api/v1/crawler/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def index():
    return {"message": "API Service is running"}

app.include_router(crawler, prefix="/api/v1/crawler", tags=["crawler"])

async def main():    
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST"),
        port=int(os.getenv("PORT")),
        log_level="debug",
        reload=True,
    )

if __name__ == "__main__":
    asyncio.run(main())