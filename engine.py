import asyncio
import logging
from datetime import datetime
import pytz
from config import MONITOR_INTERVAL, TIMEZONE
import database as db
from binance_handler import get_open_positions, get_position_by_symbol, close_position_by_symbol, close_multiple_positions, get_price
from telegram_handler import send_channel_message, send_user_message

logger = logging.getLogger(__name__)
TZ = pytz.timezone(TIMEZONE)


async def check_block_conditions(block):
    """Check if block should be closed"""
    if block.status != "active":
        return
    
    positions = db.get_block_positions(block.name)
    if not positions:
        return
    
    total_pnl = 0
    symbols_to_close = []
    
    # Check each position
    for position in positions:
        current_price = get_price(position.symbol)
        if not current_price:
            continue
        
        # Calculate PnL
        if position.side == "LONG":
            pnl = (current_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - current_price) * position.quantity
        
        total_pnl += pnl
        
        # Check Stop Line
        if block.stop_line:
            if position.side == "LONG" and current_price <= block.stop_line:
                logger.warning(f"Stop Line hit for {position.symbol}")
                await close_block_by_reason(block, "stop_line", total_pnl, positions)
                return
            elif position.side == "SHORT" and current_price >= block.stop_line:
                logger.warning(f"Stop Line hit for {position.symbol}")
                await close_block_by_reason(block, "stop_line", total_pnl, positions)
                return
    
    # Check Take Profit
    if block.tp_value and total_pnl >= block.tp_value:
        logger.info(f"Take Profit hit for block {block.name}: {total_pnl}")
        await close_block_by_reason(block, "tp", total_pnl, positions)
        return


async def close_block_by_reason(block, reason, final_pnl, positions):
    """Close block and all its positions"""
    symbols = [pos.symbol for pos in positions]
    
    # Close positions on Binance
    close_multiple_positions(symbols)
    
    # Update database
    db.close_block(block.name, reason, final_pnl)
    db.log_event("block_closed", f"Block closed by {reason} with PnL {final_pnl}", block.name)
    
    # Send notifications
    if reason == "stop_line":
        emoji = "🔴"
        title = "STOP LINE HIT"
    else:
        emoji = "🟢"
        title = "TAKE PROFIT HIT"
    
    message = (
        f"{emoji} <b>{title}</b>\n"
        f"Block: {block.name}\n"
        f"💰 PnL: ${final_pnl:.2f}\n"
        f"🕐 {datetime.now(TZ).strftime('%H:%M:%S')}"
    )
    
    await send_channel_message(message)
    await send_user_message(message)


async def monitoring_loop():
    """Main monitoring loop"""
    logger.info(f"🚀 Engine started (checking every {MONITOR_INTERVAL}s)")
    
    while True:
        try:
            # Get all active blocks
            blocks = db.get_active_blocks()
            
            for block in blocks:
                await check_block_conditions(block)
            
            await asyncio.sleep(MONITOR_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            await asyncio.sleep(MONITOR_INTERVAL)


async def run_engine():
    """Start engine"""
    await monitoring_loop()