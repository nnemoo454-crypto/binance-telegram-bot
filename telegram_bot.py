import logging
import asyncio
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from database import get_all_blocks, create_block, log_event
from block_manager import BlockManager

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TZ = pytz.timezone('Asia/Almaty')

# Conversation states
BLOCK_SELECT, INPUT_SL, INPUT_TP, SYMBOL_SELECT, SIDE_SELECT, ENTRY_INPUT, QTY_INPUT = range(7)

bot_app = None
block_manager = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    keyboard = [
        [InlineKeyboardButton("➕ Новый блок", callback_data="new_block")],
        [InlineKeyboardButton("📊 Статус всех блоков", callback_data="status_all")],
        [InlineKeyboardButton("🎯 Мой блоки", callback_data="my_blocks")],
        [InlineKeyboardButton("📈 История", callback_data="history")],
        [InlineKeyboardButton("❓ Справка", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 <b>Trading Engine Pro v2</b>\n\n"
        "Система управления блоками сделок на Binance Futures\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_block":
        await create_new_block(query, context)
    elif query.data == "status_all":
        await show_all_blocks(query)
    elif query.data == "my_blocks":
        await show_my_blocks(query)
    elif query.data == "history":
        await show_history(query)
    elif query.data == "help":
        await show_help(query)


async def create_new_block(query, context):
    """Create new block"""
    keyboard = [
        [InlineKeyboardButton("A", callback_data="block_A"),
         InlineKeyboardButton("B", callback_data="block_B"),
         InlineKeyboardButton("C", callback_data="block_C")],
        [InlineKeyboardButton("D", callback_data="block_D"),
         InlineKeyboardButton("E", callback_data="block_E")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text="Выберите блок:",
        reply_markup=reply_markup
    )


async def show_all_blocks(query):
    """Show status of all blocks"""
    blocks = get_all_blocks()
    
    if not blocks:
        await query.edit_message_text(text="❌ Нет блоков")
        return
    
    message = "<b>📊 Все блоки:</b>\n\n"
    for block in blocks:
        message += (
            f"<b>Блок {block.block_name}</b> - {block.status}\n"
            f"SL: {block.stop_line} | TP: {block.tp_price}\n"
            f"PnL: {block.final_pnl}\n\n"
        )
    
    await query.edit_message_text(text=message, parse_mode='HTML')


async def show_my_blocks(query):
    """Show active blocks"""
    from database import SessionLocal, Block
    db = SessionLocal()
    blocks = db.query(Block).filter(Block.status == "active").all()
    db.close()
    
    if not blocks:
        await query.edit_message_text(text="✅ Нет активных блоков")
        return
    
    message = "<b>🟢 Активные блоки:</b>\n\n"
    for block in blocks:
        message += (
            f"<b>Блок {block.block_name}</b>\n"
            f"SL: {block.stop_line}\n"
            f"TP: {block.tp_price}\n"
            f"Создан: {block.created_at.strftime('%H:%M')}\n\n"
        )
    
    await query.edit_message_text(text=message, parse_mode='HTML')


async def show_history(query):
    """Show block history"""
    from database import get_block_history
    blocks = get_block_history(limit=5)
    
    if not blocks:
        await query.edit_message_text(text="📜 История пуста")
        return
    
    message = "<b>📜 Последние блоки:</b>\n\n"
    for block in blocks:
        message += (
            f"Блок {block.block_name} - {block.close_reason}\n"
            f"PnL: {block.final_pnl:.2f}\n"
            f"Закрыт: {block.closed_at.strftime('%H:%M')}\n\n"
        )
    
    await query.edit_message_text(text=message, parse_mode='HTML')


async def show_help(query):
    """Show help"""
    help_text = (
        "<b>🆘 Справка</b>\n\n"
        "<b>Команды:</b>\n"
        "/start - Главное меню\n"
        "/status A - Статус блока A\n"
        "/sl A 42000 - Установить Stop Line\n"
        "/tp A 45000 - Установить TP\n"
        "/close A - Закрыть блок\n\n"
        "<b>Как использовать:</b>\n"
        "1. Создайте новый блок (A-E)\n"
        "2. Откройте позиции на Binance\n"
        "3. Добавьте позиции в блок\n"
        "4. Установите Stop Line и TP\n"
        "5. Система будет мониторить блок"
    )
    
    await query.edit_message_text(text=help_text, parse_mode='HTML')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get block status"""
    if not context.args:
        await update.message.reply_text("Использование: /status A")
        return
    
    block_name = context.args[0].upper()
    status = await block_manager.get_block_status(block_name)
    
    if status:
        await update.message.reply_text(status, parse_mode='HTML')
    else:
        await update.message.reply_text(f"❌ Блок {block_name} не найден")


async def set_sl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set stop line"""
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /sl A 42000")
        return
    
    block_name = context.args[0].upper()
    try:
        sl = float(context.args[1])
        await block_manager.update_stop_line(block_name, sl)
        await update.message.reply_text(f"✅ Stop Line для блока {block_name} установлен: {sl}")
    except ValueError:
        await update.message.reply_text("❌ Некорректная цена")


async def set_tp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set take profit"""
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /tp A 45000")
        return
    
    block_name = context.args[0].upper()
    try:
        tp = float(context.args[1])
        from database import SessionLocal, Block
        db = SessionLocal()
        block = db.query(Block).filter(Block.block_name == block_name).first()
        if block:
            block.tp_price = tp
            db.commit()
        db.close()
        await update.message.reply_text(f"✅ TP для блока {block_name} установлен: {tp}")
    except ValueError:
        await update.message.reply_text("❌ Некорректное значение")


async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close block manually"""
    if not context.args:
        await update.message.reply_text("Использование: /close A")
        return
    
    block_name = context.args[0].upper()
    from database import close_block, get_block_positions
    from binance_api import close_position
    
    positions = get_block_positions(block_name)
    for position in positions:
        close_position(position.symbol, position.quantity)
    
    close_block(block_name, "manual", 0)
    await update.message.reply_text(f"✅ Блок {block_name} закрыт")


async def channel_send_message(message):
    """Send message to channel"""
    try:
        await bot_app.bot.send_message(TELEGRAM_CHANNEL_ID, message, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error sending to channel: {e}")


async def telegram_send_message(message):
    """Send message to user"""
    from config import TELEGRAM_CHAT_ID
    try:
        await bot_app.bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error sending message: {e}")


async def main():
    """Main function"""
    global bot_app, block_manager
    
    bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    block_manager = BlockManager(telegram_send_message, channel_send_message)
    
    # Commands
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("status", status_command))
    bot_app.add_handler(CommandHandler("sl", set_sl_command))
    bot_app.add_handler(CommandHandler("tp", set_tp_command))
    bot_app.add_handler(CommandHandler("close", close_command))
    
    # Buttons
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("Bot started!")
    await bot_app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())