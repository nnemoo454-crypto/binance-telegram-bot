import logging
from datetime import datetime
import pytz
import asyncio
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
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from database import (
    create_block,
    get_active_blocks,
    get_block_history,
    get_statistics,
    add_order_record,
    SessionLocal,
    TradingBlock as TradingBlockModel,
    OrderRecord
)
import uuid

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
NEW_BLOCK, INPUT_PAIR, INPUT_TIME, INPUT_ENTRY, INPUT_SL, INPUT_TP, INPUT_VOLUME, INPUT_ORDERS = range(8)
SET_STOPLINE = 10

# Timezone
TZ = pytz.timezone('Asia/Almaty')


class BotState:
    """Store conversation state"""
    def __init__(self):
        self.user_data = {}


bot_state = BotState()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    keyboard = [
        [InlineKeyboardButton("➕ Новый блок", callback_data="new_block")],
        [InlineKeyboardButton("📊 Статус", callback_data="status")],
        [InlineKeyboardButton("📈 История", callback_data="history")],
        [InlineKeyboardButton("💹 Статистика", callback_data="stats")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 <b>Binance Trading Bot</b>\n\n"
        "Это бот для управления вашей торговой стратегией на Binance.\n\n"
        "Доступные команды:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


async def new_block_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start new block creation"""
    await update.callback_query.answer()
    user_id = update.effective_user.id
    bot_state.user_data[user_id] = {}
    
    await update.callback_query.edit_message_text(
        text="📝 Введите торговую пару (например: BTCUSDT)"
    )
    return INPUT_PAIR


async def input_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get pair input"""
    user_id = update.effective_user.id
    pair = update.message.text.upper()
    bot_state.user_data[user_id]['pair'] = pair
    
    await update.message.reply_text(
        f"✅ Пара: {pair}\n\n"
        "Введите время создания блока (UTC+5, формат: HH:MM)"
    )
    return INPUT_TIME


async def input_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get time input"""
    user_id = update.effective_user.id
    time_str = update.message.text
    bot_state.user_data[user_id]['time'] = time_str
    
    await update.message.reply_text(
        f"✅ Время: {time_str}\n\n"
        "Введите цену входа (первого ордера)"
    )
    return INPUT_ENTRY


async def input_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get entry price"""
    user_id = update.effective_user.id
    try:
        entry = float(update.message.text)
        bot_state.user_data[user_id]['entry_price'] = entry
        
        await update.message.reply_text(
            f"✅ Цена входа: {entry}\n\n"
            "Введите стоп-линию (цена отмены всех ордеров)"
        )
        return INPUT_SL
    except ValueError:
        await update.message.reply_text("❌ Некорректное значение. Введите число.")
        return INPUT_ENTRY


async def input_sl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get stop line"""
    user_id = update.effective_user.id
    try:
        sl = float(update.message.text)
        bot_state.user_data[user_id]['stop_line'] = sl
        
        await update.message.reply_text(
            f"✅ Стоп-линия: {sl}\n\n"
            "Введите тейк-профит (одинаковый для всех ордеров)"
        )
        return INPUT_TP
    except ValueError:
        await update.message.reply_text("❌ Некорректное значение. Введите число.")
        return INPUT_SL


async def input_tp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get take profit"""
    user_id = update.effective_user.id
    try:
        tp = float(update.message.text)
        bot_state.user_data[user_id]['tp'] = tp
        
        await update.message.reply_text(
            f"✅ Тейк-профит: {tp}\n\n"
            "Введите объёмы для всех 8 ордеров (через запятую, например: 0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1)"
        )
        return INPUT_VOLUME
    except ValueError:
        await update.message.reply_text("❌ Некорректное значение. Введите число.")
        return INPUT_TP


async def input_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get volumes"""
    user_id = update.effective_user.id
    try:
        volumes = [float(v.strip()) for v in update.message.text.split(',')]
        if len(volumes) != 8:
            await update.message.reply_text("❌ Нужно ровно 8 объёмов!")
            return INPUT_VOLUME
        
        bot_state.user_data[user_id]['volumes'] = volumes
        
        await update.message.reply_text(
            f"✅ Объёмы: {volumes}\n\n"
            "Введите ID 8 ордеров с Binance (через запятую)"
        )
        return INPUT_ORDERS
    except ValueError:
        await update.message.reply_text("❌ Некорректный формат. Используйте запятую.")
        return INPUT_VOLUME


async def input_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get order IDs and save block"""
    user_id = update.effective_user.id
    try:
        order_ids = [int(o.strip()) for o in update.message.text.split(',')]
        if len(order_ids) != 8:
            await update.message.reply_text("❌ Нужно ровно 8 ID ордеров!")
            return INPUT_ORDERS
        
        # Create block
        data = bot_state.user_data[user_id]
        block_id = str(uuid.uuid4())[:8]
        
        db_block = create_block(
            block_id=block_id,
            pair=data['pair'],
            entry_price=data['entry_price'],
            stop_line=data['stop_line'],
            tp=data['tp'],
            volume=sum(data['volumes'])
        )
        
        # Add order records
        for order_id in order_ids:
            add_order_record(block_id, order_id, data['pair'], data['entry_price'], 0)
        
        # Send confirmation
        message = (
            f"✅ <b>Блок создан успешно!</b>\n"
            f"📊 ID: {block_id}\n"
            f"💱 Пара: {data['pair']}\n"
            f"📍 Цена входа: {data['entry_price']}\n"
            f"🛑 Стоп-линия: {data['stop_line']}\n"
            f"🎯 ТП: {data['tp']}\n"
            f"📦 Общий объём: {sum(data['volumes'])}\n"
            f"⏰ {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await update.message.reply_text(message, parse_mode='HTML')
        
        # Clear state
        del bot_state.user_data[user_id]
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Некорректный формат ID ордеров.")
        return INPUT_ORDERS


async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active blocks status"""
    await update.callback_query.answer()
    
    db = SessionLocal()
    blocks = db.query(TradingBlockModel).filter(TradingBlockModel.status == "active").all()
    db.close()
    
    if not blocks:
        await update.callback_query.edit_message_text(text="❌ Нет активных блоков")
        return
    
    message = "📊 <b>Активные блоки:</b>\n\n"
    for block in blocks:
        message += (
            f"🔹 <b>{block.block_id}</b>\n"
            f"   Пара: {block.pair}\n"
            f"   Вход: {block.entry_price}\n"
            f"   СЛ: {block.stop_line}\n"
            f"   ТП: {block.tp}\n"
            f"   Объём: {block.volume}\n"
            f"   Создан: {block.created_at.strftime('%H:%M:%S')}\n\n"
        )
    
    await update.callback_query.edit_message_text(text=message, parse_mode='HTML')


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show closed blocks"""
    await update.callback_query.answer()
    
    blocks = get_block_history(limit=10)
    
    if not blocks:
        await update.callback_query.edit_message_text(text="❌ История пуста")
        return
    
    message = "📈 <b>История блоков:</b>\n\n"
    for block in blocks:
        message += (
            f"🔹 <b>{block.block_id}</b>\n"
            f"   Пара: {block.pair}\n"
            f"   Статус: {block.status}\n"
            f"   PnL: {block.pnl:.2f}\n"
            f"   Причина: {block.reason}\n\n"
        )
    
    await update.callback_query.edit_message_text(text=message, parse_mode='HTML')


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show statistics"""
    await update.callback_query.answer()
    
    stats = get_statistics()
    
    message = (
        f"💹 <b>Статистика:</b>\n\n"
        f"📊 Всего блоков: {stats['total_blocks']}\n"
        f"✅ Закрытых: {stats['closed_blocks']}\n"
        f"💰 Общая PnL: {stats['total_pnl']:.2f}\n"
        f"📈 Процент успеха: {stats['win_rate']:.1f}%"
    )
    
    await update.callback_query.edit_message_text(text=message, parse_mode='HTML')


async def set_stopline_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set stop line command"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Используйте: /set_stopline <block_id> <цена>"
        )
        return
    
    block_id = context.args[0]
    try:
        new_sl = float(context.args[1])
        db = SessionLocal()
        block = db.query(TradingBlockModel).filter(TradingBlockModel.block_id == block_id).first()
        if block:
            block.stop_line = new_sl
            db.commit()
            await update.message.reply_text(
                f"✏️ <b>Стоп-линия изменена</b>\n"
                f"📊 ID блока: {block_id}\n"
                f"📍 Новая стоп-линия: {new_sl}",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(f"❌ Блок {block_id} не найден")
        db.close()
    except ValueError:
        await update.message.reply_text("❌ Некорректная цена")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help"""
    help_text = (
        "<b>Доступные команды:</b>\n\n"
        "/start - Главное меню\n"
        "/new_block - Создать новый блок\n"
        "/status - Статус активных блоков\n"
        "/history - История закрытых блоков\n"
        "/stats - Статистика\n"
        "/set_stopline &lt;block_id&gt; &lt;цена&gt; - Изменить стоп-линию\n"
        "/help - Эта справка"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    
    if query.data == "new_block":
        await new_block_start(update, context)
    elif query.data == "status":
        await show_status(update, context)
    elif query.data == "history":
        await show_history(update, context)
    elif query.data == "stats":
        await show_stats(update, context)


def main():
    """Main bot function"""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("set_stopline", set_stopline_cmd))
    
    # Button callbacks
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Conversation handler for new block
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_block_start, pattern="new_block")],
        states={
            INPUT_PAIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_pair)],
            INPUT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_time)],
            INPUT_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_entry)],
            INPUT_SL: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_sl)],
            INPUT_TP: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_tp)],
            INPUT_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_volume)],
            INPUT_ORDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_orders)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    app.add_handler(conv_handler)
    
    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()