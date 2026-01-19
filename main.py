import time, asyncio, datetime, hashlib, re, os, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import filters, idle
from pyrogram.raw import functions
from config import app, regex_db, messages_db, GLOBAL_EXPIRY, DEFAULT_LOCAL_EXPIRY, LINK_PATTERN, delete_queue
from utils import get_config, is_admin

# --- PENTING: MENGHUBUNGKAN HANDLERS ---
import handlers 

# --- WORKER ---
async def delete_worker():
    while True:
        chat_id, message_ids = await delete_queue.get()
        try: await app.delete_messages(chat_id, message_ids)
        except: pass
        finally: delete_queue.task_done()

# --- CORE LOGIC (FILTER SPAM) ---
@app.on_message(filters.group & ~filters.service, group=2)
async def core_filter(client, message):
    if not message.from_user or await is_admin(message.chat.id, message.from_user.id): return
    cid, uid, mid = message.chat.id, message.from_user.id, message.id
    cfg = await get_config(cid)
    
    # (Masukkan logika filter spam Anda di sini...)
    # Kode filter spam tetap di main.py agar cepat diproses
    print(f"Memeriksa pesan dari {uid}")

async def start():
    await messages_db.create_index("createdAt", expireAfterSeconds=21600)
    asyncio.create_task(delete_worker())
    await app.start()
    print("🚀 Bot Modular is RUNNING!")
    await idle()

if __name__ == "__main__":
    asyncio.run(start())
