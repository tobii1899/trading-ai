"""
AI Trading Decision System - FastAPI Backend
Provides prediction, backtesting, and retraining endpoints for XAU/USD, GBP/JPY, NASDAQ100
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
from datetime import datetime

from api.routes import router
from services.scheduler import DataScheduler

app = FastAPI(
    title="AI Trading Decision System",
    description="ML-powered short-term trading decision support for XAU/USD, GBP/JPY, NASDAQ100",
    version="1.0.0"
)

# Allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Background scheduler for auto-refresh
scheduler = DataScheduler()

@app.on_event("startup")
async def startup_event():
    """Initialize models and start background scheduler on startup."""
    print("🚀 Starting AI Trading System...")
    # Pre-train models on startup in background
    asyncio.create_task(scheduler.start())

@app.on_event("shutdown")
async def shutdown_event():
    await scheduler.stop()

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
