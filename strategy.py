import asyncio
import logging
from datetime import datetime
import pytz
from binance_api import (
    get_current_price, 
    get_order_status, 
    cancel_order, 
    place_market_order
)
from database import (
    get_active_blocks, 
    update_block_status, 
    get_block_history,
    SessionLocal,
    TradingBlock as TradingBlockModel,
    OrderRecord
)

logger = logging.getLogger(__name__)

# Store for managing blocks
active_blocks = {}


class TradingBlock:
    """Trading block manager"""
    
    def __init__(self, block_id, pair, entry_price, stop_line, tp, volume, order_ids, telegram_send_func):
        self.block_id = block_id
        self.pair = pair
        self.entry_price = entry_price
        self.stop_line = stop_line
        self.tp = tp
        self.volume = volume
        self.order_ids = order_ids  # List of 8 order IDs
        self.status = "active"
        self.telegram_send_func = telegram_send_func
        self.filled_order = None
        self.initial_volume = sum([vol for vol in volume]) if isinstance(volume, list) else volume
        
    async def monitor(self):
        """Monitor block for conditions"""
        while self.status == "active":
            try:
                current_price = get_current_price(self.pair)
                
                if current_price is None:
                    await asyncio.sleep(5)
                    continue
                
                # Check stop line condition
                if current_price <= self.stop_line:
                    await self.cancel_all_orders()
                    await self.close_block("stop_line", 0)
                    break
                
                # Check if any order filled
                for order_id in self.order_ids:
                    order_status = get_order_status(self.pair, order_id)
                    
                    if order_status and float(order_status['filled_qty']) > 0:
                        # Order filled - execute TP and cancel rest
                        self.filled_order = order_id
                        await self.handle_order_filled(order_status)
                        break
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring block {self.block_id}: {e}")
                await asyncio.sleep(5)
    
    async def cancel_all_orders(self):
        """Cancel all orders in block"""
        for order_id in self.order_ids:
            result = cancel_order(self.pair, order_id)
            if result:
                logger.info(f"Cancelled order {order_id}")
    
    async def handle_order_filled(self, order_status):
        """Handle when one order is filled"""
        filled_qty = float(order_status['filled_qty'])
        
        # Calculate PnL (simplified)
        current_price = get_current_price(self.pair)
        pnl = (current_price - self.entry_price) * filled_qty
        
        # Place market order at TP
        await self.place_tp_order(filled_qty)
        
        # Cancel remaining orders
        await self.cancel_all_orders()
        
        # Close block
        await self.close_block("tp_hit", pnl)
    
    async def place_tp_order(self, quantity):
        """Place market order to close at TP"""
        # Determine side (opposite of entry)
        side = "SELL" if "BUY" in self.pair else "BUY"
        result = place_market_order(self.pair, side, quantity)
        if result:
            logger.info(f"Placed TP order: {result}")
    
    async def close_block(self, reason, pnl):
        """Close trading block"""
        self.status = "closed"
        
        # Update database
        update_block_status(self.block_id, "closed", pnl, reason)
        
        # Send notification
        message = (
            f"🔴 <b>Блок закрыт</b>\n"
            f"📊 ID: {self.block_id}\n"
            f"💱 Пара: {self.pair}\n"
            f"💰 PnL: {pnl:.2f}\n"
            f"📍 Причина: {reason}\n"
            f"⏰ {datetime.now(pytz.timezone('Asia/Almaty')).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await self.telegram_send_func(message)
    
    async def set_stop_line(self, new_stop_line):
        """Update stop line"""
        self.stop_line = new_stop_line
        message = (
            f"✏️ <b>Стоп-линия изменена</b>\n"
            f"📊 ID блока: {self.block_id}\n"
            f"📍 Новая стоп-линия: {new_stop_line}"
        )
        await self.telegram_send_func(message)


async def monitor_all_blocks(telegram_send_func):
    """Monitor all active blocks"""
    while True:
        try:
            db = SessionLocal()
            blocks = db.query(TradingBlockModel).filter(TradingBlockModel.status == "active").all()
            db.close()
            
            for block in blocks:
                block_manager = active_blocks.get(block.block_id)
                if not block_manager:
                    # Create manager for existing block
                    db = SessionLocal()
                    order_records = db.query(OrderRecord).filter(
                        OrderRecord.block_id == block.block_id
                    ).all()
                    db.close()
                    order_ids = [int(rec.order_id) for rec in order_records]
                    
                    block_manager = TradingBlock(
                        block.block_id,
                        block.pair,
                        block.entry_price,
                        block.stop_line,
                        block.tp,
                        block.volume,
                        order_ids,
                        telegram_send_func
                    )
                    active_blocks[block.block_id] = block_manager
                    asyncio.create_task(block_manager.monitor())
            
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in monitor_all_blocks: {e}")
            await asyncio.sleep(5)