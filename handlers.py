import re, asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import app, OWNER_ID, regex_db, DEFAULT_LOCAL_EXPIRY, delete_queue
from utils import is_admin, get_config, update_config, auto_delete_reply

@app.on_message(filters.command("start") & filters.private)
async def start_private(client, message):
    me = await client.get_me()
    add_url = f"t.me/{me.username}?startgroup=true&admin=delete_messages"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("➕ Aktifkan Proteksi di Grup", url=add_url)]])
    await message.reply(f"👋 **Selamat Datang di Sistem Keamanan Bot Antispam**\n\n🛡 *Pengelolaan spam di grup Anda adalah fokus utama kami.*", reply_markup=keyboard)

@app.on_message(filters.command(["status", "antigcast"]) & filters.group)
async def group_cmd(client, message):
    cid, cmd = message.chat.id, message.command[0].lower()
    if cmd == "antigcast":
        res = await message.reply("🛡 **Grup ini memiliki sistem Antispam**")
        return asyncio.create_task(auto_delete_reply([message, res], 5))
    
    if not await is_admin(cid, message.from_user.id): return
    cfg = await get_config(cid)
    if cmd == "status":
        text = f"📡 **Proteksi Lokal:** `{'AKTIF' if cfg.get('local', True) else 'OFF'}`"
        res = await message.reply(text)
        asyncio.create_task(auto_delete_reply([message, res], 10))
