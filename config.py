import os
import dns.resolver
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client

load_dotenv()

# Pengaturan DNS
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8', '8.8.4.4', '1.1.1.1']

# Konfigurasi ENV
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))

# Database Setup
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["antispam"]
config_db = db["status"]
messages_db = db["seen_messages"]
regex_db = db["regex_list"]

# Inisialisasi App
app = Client("antispam_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# Variabel Global
GLOBAL_EXPIRY = 15  
DEFAULT_LOCAL_EXPIRY = 3600 
LINK_PATTERN = r"(https?://\S+|t\.me/\S+|www\.\S+|[\w-]+\.(com|net|org|io|biz|xyz|me|link|info)|@\w+)"
