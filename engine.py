import asyncio
import logging
from datetime import datetime
import pytz
from binance_api import get_open_positions, get_current_price
from database import (
    get_all_blocks,
    SessionLocal,
    Block as BlockModel,
    Position as PositionModel
)
from block_manager import BlockManager

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TZ = pytz.timezone('Asia/Almaty')


async def monitor_loop(block_manager, check_interval=5):
    """Main monitoring loop"""
    logger.info("Starting monitoring loop")
    
    while True:
        try:
            # Get all active blocks
            db = SessionLocal()
            blocks = db.query(BlockModel).filter(BlockModel.status == "active").all()
            db.close()
            
            for block in blocks:
                logger.info(f"Monitoring block {block.block_name}")
                await block_manager.monitor_block(block.block_name)
            
            await asyncio.sleep(check_interval)
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            await asyncio.sleep(check_interval)


async def start_engine(block_manager):
    """Start trading engine"""
    logger.info("🚀 Trading Engine Pro v2 started")
    await monitor_loop(block_manager)