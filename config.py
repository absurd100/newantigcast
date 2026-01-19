import os, asyncio, dns.resolver
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client

load_dotenv()
resolver = dns.resolver.Resolver()
resolver.nameservers = ['8.8.8.8', '8.8.4.4']
dns.resolver.default_resolver = resolver

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
MONGO_URL = os.environ.get("MONGO_URL", "").strip()
OWNER_ID = int(os.environ.get("OWNER_ID", 0))

mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["antispam"]
config_db = db["status"]
messages_db = db["seen_messages"]
regex_db = db["regex_list"]

app = Client("antispam_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
delete_queue = asyncio.Queue()

GLOBAL_EXPIRY = 15  
DEFAULT_LOCAL_EXPIRY = 3600 
LINK_PATTERN = r"(https?://\S+|t\.me/\S+|www\.\S+|[\w-]+\.(com|net|org|io|biz|xyz|me|link|info)|@\w+)"
