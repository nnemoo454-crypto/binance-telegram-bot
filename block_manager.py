import logging
from datetime import datetime
import pytz
from database import (
    get_active_block,
    get_block_positions,
    close_block,
    log_event,
    SessionLocal,
    Block as BlockModel,
    Position as PositionModel
)
from binance_api import get_open_positions, get_current_price, close_position

logger = logging.getLogger(__name__)
TZ = pytz.timezone('Asia/Almaty')


class BlockManager:
    """Manages trading blocks"""
    
    def __init__(self, telegram_send_func, channel_send_func):
        self.telegram_send_func = telegram_send_func
        self.channel_send_func = channel_send_func
    
    async def create_block(self, block_name, stop_line=None, tp_price=None):
        """Create new block"""
        from database import create_block
        block = create_block(block_name, stop_line, tp_price)
        
        message = (
            f"✅ <b>Блок {block_name} создан</b>\n"
            f"🕒 {datetime.now(TZ).strftime('%H:%M:%S')}\n"
            f"🛑 Stop Line: {stop_line}\n"
            f"🎯 TP: {tp_price}"
        )
        
        await self.channel_send_func(message)
        return block
    
    async def add_position(self, block_name, symbol, side, entry_price, quantity):
        """Add position to block"""
        from database import add_position_to_block
        position = add_position_to_block(block_name, symbol, side, entry_price, quantity)
        
        message = (
            f"📊 <b>Позиция добавлена в блок {block_name}</b>\n"
            f"{symbol} {side}\n"
            f"Entry: {entry_price}\n"
            f"Qty: {quantity}"
        )
        
        await self.channel_send_func(message)
        return position
    
    async def monitor_block(self, block_name):
        """Monitor block for close conditions"""
        block = get_active_block(block_name)
        if not block:
            logger.warning(f"Block {block_name} not found or not active")
            return
        
        positions = get_block_positions(block_name)
        if not positions:
            logger.warning(f"No positions in block {block_name}")
            return
        
        # Calculate block PnL
        total_pnl = 0
        for position in positions:
            current_price = get_current_price(position.symbol)
            if current_price:
                if position.side == "LONG":
                    pnl = (current_price - position.entry_price) * position.quantity
                else:
                    pnl = (position.entry_price - current_price) * position.quantity
                total_pnl += pnl
        
        # Check stop line
        if block.stop_line:
            for position in positions:
                current_price = get_current_price(position.symbol)
                if current_price and current_price <= block.stop_line:
                    await self.close_block_by_stopline(block_name, position.symbol)
                    return
        
        # Check TP
        if block.tp_price and total_pnl >= block.tp_price:
            await self.close_block_by_tp(block_name, total_pnl)
            return
    
    async def close_block_by_stopline(self, block_name, triggered_symbol):
        """Close block by stop line"""
        positions = get_block_positions(block_name)
        
        # Close all positions
        for position in positions:
            close_position(position.symbol, position.quantity)
        
        close_block(block_name, "stop_line", 0)
        
        message = (
            f"🛑 <b>Блок {block_name} закрыт по Stop Line</b>\n"
            f"Сработал: {triggered_symbol}\n"
            f"🕒 {datetime.now(TZ).strftime('%H:%M:%S')}"
        )
        
        await self.channel_send_func(message)
        await self.telegram_send_func(message)
    
    async def close_block_by_tp(self, block_name, final_pnl):
        """Close block by TP"""
        positions = get_block_positions(block_name)
        
        # Close all positions
        for position in positions:
            close_position(position.symbol, position.quantity)
        
        close_block(block_name, "tp", final_pnl)
        
        message = (
            f"🎯 <b>Блок {block_name} закрыт по TP</b>\n"
            f"💰 PnL: {final_pnl:.2f}\n"
            f"🕒 {datetime.now(TZ).strftime('%H:%M:%S')}"
        )
        
        await self.channel_send_func(message)
        await self.telegram_send_func(message)
    
    async def update_stop_line(self, block_name, new_stop_line):
        """Update block stop line"""
        db = SessionLocal()
        block = db.query(BlockModel).filter(BlockModel.block_name == block_name).first()
        if block:
            block.stop_line = new_stop_line
            db.commit()
        db.close()
        
        message = (
            f"✏️ <b>Stop Line блока {block_name} изменена</b>\n"
            f"Новое значение: {new_stop_line}"
        )
        await self.channel_send_func(message)
    
    async def get_block_status(self, block_name):
        """Get block status"""
        block = get_active_block(block_name)
        if not block:
            return None
        
        positions = get_block_positions(block_name)
        total_pnl = 0
        
        status_text = f"<b>📊 Блок {block_name}</b>\n\n"
        
        for position in positions:
            current_price = get_current_price(position.symbol)
            if current_price:
                if position.side == "LONG":
                    pnl = (current_price - position.entry_price) * position.quantity
                    pnl_pct = ((current_price / position.entry_price) - 1) * 100
                else:
                    pnl = (position.entry_price - current_price) * position.quantity
                    pnl_pct = ((position.entry_price / current_price) - 1) * 100
                
                total_pnl += pnl
                
                status_text += (
                    f"{position.symbol} {position.side}\n"
                    f"Entry: {position.entry_price}\n"
                    f"Now: {current_price}\n"
                    f"PnL: {pnl:.2f} ({pnl_pct:.2f}%)\n\n"
                )
        
        status_text += f"💰 Общий PnL: {total_pnl:.2f}\n"
        status_text += f"🛑 Stop Line: {block.stop_line}\n"
        status_text += f"🎯 TP: {block.tp_price}"
        
        return status_text