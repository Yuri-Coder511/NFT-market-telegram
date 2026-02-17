# config.py
import os

# Telegram Bot Tokens
BOT_MAIN_TOKEN = "YOUR_MAIN_BOT_TOKEN"  # Основной бот маркета
BOT_RECEIVER_TOKEN = "YOUR_RECEIVER_BOT_TOKEN"  # Бот для приема NFT

# Webhook settings
WEBHOOK_URL = "https://your-domain.com"  # Ваш домен
WEBHOOK_PATH = "/webhook"
WEBHOOK_RECEIVER_PATH = "/webhook_receiver"

# Database
DATABASE_URL = "sqlite:///nft_market.db"

# Admin IDs
ADMIN_IDS = [123456789]  # ID администраторов

# Upload settings
UPLOAD_FOLDER = "uploads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'json'}

# Stars rate (сколько рублей за 1 звезду)
STARS_TO_RUB = 10  # 1 звезда = 10 рублей (пример)