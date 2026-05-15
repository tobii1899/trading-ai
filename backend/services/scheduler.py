"""
Data Scheduler - Background task that refreshes predictions periodically.
Uses asyncio for non-blocking execution.
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 300  # 5 minutes default


class DataScheduler:
    """Manages background refresh of market data and predictions."""

    def __init__(self, interval_seconds: int = REFRESH_INTERVAL_SECONDS):
        self.interval = interval_seconds
        self._running = False
        self._task = None
        self.last_refresh: datetime | None = None

    async def start(self):
        """Start the background refresh loop."""
        self._running = True
        logger.info(f"📅 Scheduler started (interval: {self.interval}s)")
        
        # Initial model training on startup
        await self._initial_train()
        
        while self._running:
            await asyncio.sleep(self.interval)
            if self._running:
                await self._refresh()

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _initial_train(self):
        """Train all models on startup if not already trained."""
        try:
            from services.ml_service import train_all_models, get_model
            from services.data_service import get_supported_assets
            
            # Check if any model needs training
            needs_training = False
            for asset_info in get_supported_assets():
                model = get_model(asset_info["id"])
                model._load()
                if not model.is_trained:
                    needs_training = True
                    break
            
            if needs_training:
                logger.info("🤖 Initial model training started...")
                results = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: asyncio.run(train_all_models())
                )
                logger.info(f"✅ Initial training complete: {results}")
            else:
                logger.info("✅ Pre-trained models found, skipping initial training")
                
        except Exception as e:
            logger.error(f"Initial training failed: {e}")

    async def _refresh(self):
        """Periodic data refresh (light operation - just updates latest data cache)."""
        try:
            self.last_refresh = datetime.utcnow()
            logger.info(f"🔄 Data refresh at {self.last_refresh.isoformat()}")
            # In production: could cache latest OHLCV and news here
        except Exception as e:
            logger.error(f"Refresh error: {e}")
