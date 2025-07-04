import os
from dotenv import load_dotenv

load_dotenv()

# Cookies for downloading from platforms
INST_COOKIES = """
# write up here insta cookies
"""

YTUB_COOKIES = """
# write here yt cookies
"""

# Required environment variables
API_ID = int(os.getenv("API_ID", "27704224"))
API_HASH = os.getenv("API_HASH", "c2e33826d757fe113bc154fcfabc987d")
BOT_TOKEN = os.getenv("BOT_TOKEN", "7540338860:AAGPblRh7yXqpVdLLb4Vndv4IioMd36GFgc")
MONGO_DB = os.getenv("MONGO_DB", "mongodb+srv://ZeroTwo:aloksingh@zerotwo.3q3ij.mongodb.net/?retryWrites=true&w=majority")

# Required IDs
OWNER_ID = list(map(int, os.getenv("OWNER_ID", "7970350353").split())) if os.getenv("OWNER_ID") else []
LOG_GROUP = int(os.getenv("LOG_GROUP", "-1002669902570")) if os.getenv("LOG_GROUP") else None
FORCE_SUB = int(os.getenv("FORCE_SUB", "-1002669902570")) if os.getenv("FORCE_SUB") else None

# Database name
DB_NAME = os.getenv("DB_NAME", "telegram_downloader")

# Optional configurations
STRING = os.getenv("STRING", None)
MASTER_KEY = os.getenv("MASTER_KEY", "0zZvUhB9NSi3SYVWB3a0WgG3HpGGtuYV")
IV_KEY = os.getenv("IV_KEY", "sNskkKYWqdpO")

# Platform cookies
YT_COOKIES = os.getenv("YT_COOKIES", YTUB_COOKIES)
INSTA_COOKIES = os.getenv("INSTA_COOKIES", INST_COOKIES)

# Limits
FREEMIUM_LIMIT = int(os.getenv("FREEMIUM_LIMIT", "1000000"))
PREMIUM_LIMIT = int(os.getenv("PREMIUM_LIMIT", "10000000"))

# Links
JOIN_LINK = os.getenv("JOIN_LINK", "https://t.me/Era_Bot_Support")
ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "https://t.me/Yae_X_Miko")
