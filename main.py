import asyncio
import logging
from telegram_handler import main as start_bot
from engine import run_engine

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point"""
    logger.info("="*50)
    logger.info("🚀 TRADING SYSTEM v1.0 STARTED")
    logger.info("="*50)
    
    # Run bot and engine concurrently
    try:
        await asyncio.gather(
            start_bot(),
            run_engine()
        )
    except KeyboardInterrupt:
        logger.info("\n✋ Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 System stopped")