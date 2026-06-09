import logging
import asyncio
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_CHANNEL_ID,
    AVAILABLE_BLOCKS,
    TIMEZONE
)
import database as db
from binance_handler import get_open_positions, get_price, close_position_by_symbol, close_multiple_positions

logger = logging.getLogger(__name__)
TZ = pytz.timezone(TIMEZONE)

app = None


async def send_channel_message(message):
    """Send message to channel"""
    try:
        if app:
            await app.bot.send_message(
                chat_id=TELEGRAM_CHANNEL_ID,
                text=message,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Error sending to channel: {e}")


async def send_user_message(message):
    """Send message to user"""
    try:
        if app:
            await app.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Error sending to user: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    keyboard = [
        [InlineKeyboardButton("➕ Новый блок", callback_data="new_block")],
        [InlineKeyboardButton("📊 Статус", callback_data="status")],
        [InlineKeyboardButton("📈 Статистика", callback_data="stats")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🏧 <b>Trading System</b>\n\n"
        "Система управления блоками сделок\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_block":
        await create_block_handler(query)
    elif query.data == "status":
        await status_handler(query)
    elif query.data == "stats":
        await stats_handler(query)
    elif query.data == "help":
        await help_handler(query)
    elif query.data.startswith("block_"):
        block_name = query.data.split("_")[1]
        await activate_block(query, block_name)


async def create_block_handler(query):
    """Create new block"""
    keyboard = []
    for block_name in AVAILABLE_BLOCKS:
        block = db.get_block(block_name)
        status = "✅" if block and block.status == "active" else "❌"
        keyboard.append([InlineKeyboardButton(
            f"{block_name} {status}",
            callback_data=f"block_{block_name}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="Выберите блок для активации:",
        reply_markup=reply_markup
    )


async def activate_block(query, block_name):
    """Activate block"""
    block = db.get_block(block_name)
    
    if block and block.status == "active":
        await query.edit_message_text(
            text=f"❌ Блок {block_name} уже активен\n"
                 f"SL: {block.stop_line}\n"
                 f"TP: {block.tp_value}"
        )
        return
    
    if block:
        db.close_block(block_name, "manual", 0)  # Close old block first
    
    db.create_block(block_name)
    db.log_event("block_created", f"Block {block_name} created", block_name)
    
    await query.edit_message_text(
        text=f"✅ Блок {block_name} активирован\n\n"
             f"Используйте команды:\n"
             f"/sl {block_name} 42000 - Set Stop Line\n"
             f"/tp {block_name} 45000 - Set TP\n"
             f"/add {block_name} BTCUSDT 1.5 - Add position"
    )
    
    await send_channel_message(
        f"🟢 <b>Block {block_name} activated</b>\n"
        f"🕐 {datetime.now(TZ).strftime('%H:%M:%S')}"
    )


async def status_handler(query):
    """Show block status"""
    blocks = db.get_active_blocks()
    
    if not blocks:
        await query.edit_message_text(text="❌ Нет активных блоков")
        return
    
    message = "<b>📊 Статус блоков:</b>\n\n"
    
    for block in blocks:
        positions = db.get_block_positions(block.name)
        total_pnl = 0
        
        message += f"<b>Блок {block.name}</b>\n"
        message += f"Статус: {'🟢 Active' if block.status == 'active' else '🔴 Closed'}\n"
        message += f"Позиций: {len(positions)}\n"
        
        for pos in positions:
            current_price = get_price(pos.symbol)
            if current_price:
                if pos.side == "LONG":
                    pnl = (current_price - pos.entry_price) * pos.quantity
                else:
                    pnl = (pos.entry_price - current_price) * pos.quantity
                
                total_pnl += pnl
                message += f"  {pos.symbol}: {pos.side} | PnL: ${pnl:.2f}\n"
        
        message += f"SL: {block.stop_line} | TP: {block.tp_value}\n"
        message += f"<b>Total PnL: ${total_pnl:.2f}</b>\n\n"
    
    await query.edit_message_text(text=message, parse_mode='HTML')


async def stats_handler(query):
    """Show statistics"""
    today = datetime.now().strftime("%Y-%m-%d")
    stats = db.get_daily_stats(today)
    
    if not stats:
        await query.edit_message_text(
            text="📈 <b>Статистика сегодня:</b>\n\n"
                 "Данных нет",
            parse_mode='HTML'
        )
        return
    
    winrate = (stats.winning_blocks / stats.total_blocks * 100) if stats.total_blocks > 0 else 0
    
    await query.edit_message_text(
        text=f"📈 <b>Статистика за {today}:</b>\n\n"
             f"💰 Total PnL: ${stats.total_pnl:.2f}\n"
             f"📦 Блоков: {stats.total_blocks}\n"
             f"✅ Побед: {stats.winning_blocks}\n"
             f"❌ Поражений: {stats.losing_blocks}\n"
             f"📊 Winrate: {winrate:.1f}%\n"
             f"📋 Позиций: {stats.total_positions}",
        parse_mode='HTML'
    )


async def help_handler(query):
    """Show help"""
    await query.edit_message_text(
        text="<b>ℹ️ Справка:</b>\n\n"
             "<b>Команды:</b>\n"
             "/start - Главное меню\n"
             "/sl BLOCK PRICE - Установить Stop Line\n"
             "/tp BLOCK PRICE - Установить TP\n"
             "/close BLOCK - Закрыть блок\n\n"
             "<b>Примеры:</b>\n"
             "/sl A 42000\n"
             "/tp A 45000\n"
             "/close A",
        parse_mode='HTML'
    )


async def cmd_set_sl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set stop line"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /sl BLOCK PRICE\n"
            "Example: /sl A 42000"
        )
        return
    
    block_name = context.args[0].upper()
    try:
        sl_price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid price")
        return
    
    block = db.get_block(block_name)
    if not block:
        await update.message.reply_text(f"❌ Block {block_name} not found")
        return
    
    db.update_block_sl(block_name, sl_price)
    db.log_event("sl_updated", f"SL updated to {sl_price}", block_name)
    
    await update.message.reply_text(
        f"✅ Stop Line для блока {block_name} установлен: {sl_price}"
    )
    
    await send_channel_message(
        f"🔴 <b>Block {block_name} - Stop Line Updated</b>\n"
        f"New SL: {sl_price}"
    )


async def cmd_set_tp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set take profit"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /tp BLOCK VALUE\n"
            "Example: /tp A 50 (for $50 profit)"
        )
        return
    
    block_name = context.args[0].upper()
    try:
        tp_value = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid value")
        return
    
    block = db.get_block(block_name)
    if not block:
        await update.message.reply_text(f"❌ Block {block_name} not found")
        return
    
    db.update_block_tp(block_name, tp_value)
    db.log_event("tp_updated", f"TP updated to {tp_value}", block_name)
    
    await update.message.reply_text(
        f"✅ Take Profit для блока {block_name} установлен: ${tp_value}"
    )
    
    await send_channel_message(
        f"🟢 <b>Block {block_name} - Take Profit Updated</b>\n"
        f"New TP: ${tp_value}"
    )


async def cmd_close_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close block manually"""
    if not context.args:
        await update.message.reply_text("Usage: /close BLOCK\nExample: /close A")
        return
    
    block_name = context.args[0].upper()
    
    block = db.get_block(block_name)
    if not block:
        await update.message.reply_text(f"❌ Block {block_name} not found")
        return
    
    positions = db.get_block_positions(block_name)
    symbols = [pos.symbol for pos in positions]
    
    if symbols:
        close_multiple_positions(symbols)
    
    total_pnl = db.get_block_pnl(block_name)
    db.close_block(block_name, "manual", total_pnl)
    db.log_event("block_closed", f"Block closed manually with PnL {total_pnl}", block_name)
    
    await update.message.reply_text(
        f"✅ Блок {block_name} закрыт\n"
        f"Total PnL: ${total_pnl:.2f}"
    )
    
    await send_channel_message(
        f"🔵 <b>Block {block_name} Closed (Manual)</b>\n"
        f"💰 PnL: ${total_pnl:.2f}"
    )


async def main():
    """Start bot"""
    global app
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sl", cmd_set_sl))
    app.add_handler(CommandHandler("tp", cmd_set_tp))
    app.add_handler(CommandHandler("close", cmd_close_block))
    
    # Buttons
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("✅ Bot started")
    await app.run_polling()
