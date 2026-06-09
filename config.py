import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", 0))
TELEGRAM_CHANNEL_ID = int(os.getenv("TELEGRAM_CHANNEL_ID", 0))

# Binance
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

# Database
DATABASE_URL = "sqlite:///trading_system.db"

# Timezone
TIMEZONE = "Asia/Almaty"

# Engine monitoring interval (seconds)
MONITOR_INTERVAL = 5

# Blocks
AVAILABLE_BLOCKS = ["A", "B", "C", "D", "E"]

# Debug
DEBUG = True

print("✅ Config loaded")
if DEBUG:
    print(f"  Bot Token: {TELEGRAM_BOT_TOKEN[:10]}...")
    print(f"  Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"  Channel ID: {TELEGRAM_CHANNEL_ID}")
    print(f"  API Key: {BINANCE_API_KEY[:10] if BINANCE_API_KEY else 'NOT SET'}...")