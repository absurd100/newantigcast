import time, asyncio, datetime, hashlib, re, os, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import filters, idle
from pyrogram.raw import functions
from config import app, regex_db, messages_db, GLOBAL_EXPIRY, DEFAULT_LOCAL_EXPIRY, LINK_PATTERN, delete_queue, OWNER_ID
from utils import get_config, is_admin, update_config, auto_delete_reply
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Online")

def run_health_check():
    try:
        port = int(os.environ.get("PORT", 8000))
        HTTPServer(('0.0.0.0', port), HealthCheckHandler).serve_forever()
    except: pass

# --- WORKER ---
async def delete_worker():
    while True:
        chat_id, message_ids = await delete_queue.get()
        try: await app.delete_messages(chat_id, message_ids)
        except: pass
        finally: delete_queue.task_done()

# --- HANDLERS (Command) ---
@app.on_message(filters.command(["addregex", "delregex", "infobot"]) & filters.user(OWNER_ID))
async def owner_cmd(client, message):
    cmd = message.command[0].lower()
    if cmd == "addregex":
        pattern = " ".join(message.command[1:])
        try:
            re.compile(pattern)
            await regex_db.update_one({"pattern": pattern}, {"$set": {"pattern": pattern}}, upsert=True)
            await message.reply(f"✅ Regex `{pattern}` disimpan.")
        except: await message.reply("❌ Pattern tidak valid!")
    elif cmd == "infobot":
        res = [doc["pattern"] async for doc in regex_db.find({})]
        await message.reply("📋 Blacklist:\n`" + "`\n`".join(res) + "`" if res else "Kosong.")

@app.on_message(filters.command("start") & filters.private)
async def start_private(client, message):
    me = await client.get_me()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("➕ Aktifkan Proteksi", url=f"t.me/{me.username}?startgroup=true")]])
    await message.reply("👋 **Bot Antispam Aktif**\nTambahkan saya ke grup dan jadikan admin.", reply_markup=keyboard)

@app.on_message(filters.command(["setlocal", "setglobal", "setwaktu", "status", "setbio", "antigcast"]) & filters.group)
async def admin_cmd(client, message):
    if not message.from_user: return
    cid, cmd = message.chat.id, message.command[0].lower()
    if not await is_admin(cid, message.from_user.id): return
    cfg = await get_config(cid)
    res = None
    if cmd == "status":
        res = await message.reply(f"🖥 **STATUS**\nLokal: {cfg.get('local')}\nGlobal: {cfg.get('global')}\nBio: {cfg.get('bio_check')}")
    elif cmd == "antigcast":
        res = await message.reply("🛡 **Proteksi Aktif**")
    if res: asyncio.create_task(auto_delete_reply([message, res], 10))

# --- CORE FILTER ---
@app.on_message(filters.group & ~filters.service, group=2)
async def core_filter(client, message):
    if not message.from_user or await is_admin(message.chat.id, message.from_user.id): return
    cid, uid, mid = message.chat.id, message.from_user.id, message.id
    cfg = await get_config(cid)
    
    if cfg.get("bio_check"):
        try:
            peer = await client.resolve_peer(uid)
            full = await client.invoke(functions.users.GetFullUser(id=peer))
            if full.full_user.about and re.search(LINK_PATTERN, full.full_user.about, re.IGNORECASE):
                return await delete_queue.put((cid, [mid]))
        except: pass

    if not (message.text or message.caption) or (message.text or "").startswith("/"): return
    content = (message.text or message.caption).strip()
    
    async for reg in regex_db.find({}):
        if re.search(reg["pattern"], content, re.IGNORECASE):
            return await delete_queue.put((cid, [mid]))

    now_ts, now_dt = time.time(), datetime.datetime.now(datetime.UTC)
    content_hash = hashlib.md5(content.encode()).hexdigest()
    
    l_key = f"loc_{cid}_{uid}_{content_hash}"
    exist_l = await messages_db.find_one({"_id": l_key})
    if cfg.get("local", True) and exist_l:
        if (now_ts - exist_l["time"]) < cfg.get("expiry", DEFAULT_LOCAL_EXPIRY):
            return await delete_queue.put((cid, [exist_l["msg_id"], mid]))

    g_key = f"glob_{uid}_{content_hash}"
    exist_g = await messages_db.find_one({"_id": g_key})
    if exist_g:
        if (now_ts - exist_g["time"]) < GLOBAL_EXPIRY:
            locs = exist_g.get("locations", [])
            if [cid, mid] not in locs: locs.append([cid, mid])
            await messages_db.update_one({"_id": g_key}, {"$set": {"locations": locs, "createdAt": now_dt}})
            for l_cid, l_mid in locs:
                if (await get_config(l_cid)).get("global", True): await delete_queue.put((l_cid, [l_mid]))
            return
    
    await messages_db.update_one({"_id": g_key}, {"$set": {"time": now_ts, "createdAt": now_dt, "locations": [[cid, mid]]}}, upsert=True)
    await messages_db.update_one({"_id": l_key}, {"$set": {"time": now_ts, "msg_id": mid, "createdAt": now_dt}}, upsert=True)

# --- START ---
async def start():
    await messages_db.create_index("createdAt", expireAfterSeconds=21600)
    threading.Thread(target=run_health_check, daemon=True).start()
    asyncio.create_task(delete_worker())
    await app.start()
    print("🚀 Bot Running!"); await idle(); await app.stop()

if __name__ == "__main__":
    asyncio.run(start())
