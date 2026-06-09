import asyncio
import logging
from telegram_bot import main as start_bot
from engine import start_engine
from block_manager import BlockManager

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point"""
    logger.info("Starting Trading Engine Pro v2")
    
    # Create block manager
    async def dummy_send(msg):
        pass
    
    block_manager = BlockManager(dummy_send, dummy_send)
    
    # Run bot and engine concurrently
    try:
        await asyncio.gather(
            start_bot(),
            start_engine(block_manager)
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())