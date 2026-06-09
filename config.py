import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "-100YOUR_CHANNEL_ID")

# Binance
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "YOUR_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "YOUR_SECRET_KEY")

# Database
DATABASE_URL = "sqlite:///trading_system.db"

# Timezone
TIMEZONE = "Asia/Almaty"

# Monitoring interval (seconds)
MONITOR_INTERVAL = 5

# Block configuration
BLOCKS = ["A", "B", "C", "D", "E"]

# Bot settings
DEBUG = True