import time, asyncio, datetime, hashlib, re, os, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import filters, idle
from pyrogram.raw import functions
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import *
from utils import get_config, is_admin, update_config, auto_delete_reply

# --- HEALTH CHECK ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Bot Antispam is Online")

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

# --- HANDLERS (OWNER) ---
@app.on_message(filters.command(["addregex", "delregex", "infobot"]) & filters.user(OWNER_ID))
async def owner_management(client, message):
    cmd = message.command[0].lower()
    if cmd == "addregex":
        if len(message.command) < 2: return await message.reply("Format: `/addregex pola`")
        pattern = " ".join(message.command[1:])
        try:
            re.compile(pattern)
            await regex_db.update_one({"pattern": pattern}, {"$set": {"pattern": pattern}}, upsert=True)
            await message.reply(f"✅ Regex `{pattern}` berhasil disimpan.")
        except: await message.reply("❌ Pattern Regex tidak valid!")
    elif cmd == "delregex":
        pattern = " ".join(message.command[1:])
        await regex_db.delete_one({"pattern": pattern})
        await message.reply(f"🗑 Regex `{pattern}` dihapus.")
    elif cmd == "infobot":
        res = [doc["pattern"] async for doc in regex_db.find({})]
        text_regex = "📋 **Daftar Blacklist Regex:**\n`" + "`\n`".join(res) + "`" if res else "📋 **Daftar Regex:** Kosong."
        await message.reply(text_regex)

# --- START PRIVATE ---
@app.on_message(filters.command("start") & filters.private)
async def start_private(client, message):
    me = await client.get_me()
    add_url = f"t.me/{me.username}?startgroup=true&admin=delete_messages"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("➕ Aktifkan Proteksi di Grup", url=add_url)]])
    await message.reply(f"👋 **Selamat Datang di Sistem Keamanan Bot Antispam**\n\n"
        "Saya adalah bot spesialis mitigasi spam massal lintas grup secara *real-time*.\n\n"
        "📖 **TUTORIAL PENGGUNAAN:**\n"
        "1. Klik tombol di bawah untuk menambahkan saya ke grup Anda.\n"
        "2. Pastikan saya diberikan hak akses sebagai **Administrator** dengan izin **Hapus Pesan (Delete Messages)**.\n"
        "3. Setelah aktif, saya akan memantau setiap pesan masuk secara otomatis.\n\n"
        "📋 **DAFTAR PERINTAH ADMIN GRUP:**\n"
        "• `/status` - Memeriksa konfigurasi keamanan grup saat ini.\n"
        "• `/setlocal [on/off]` - Mengaktifkan filter duplikasi konten dalam grup.\n"
        "• `/setglobal [on/off]` - Mengaktifkan filter berdasarkan database blacklist pusat.\n"
        "• `/setbio [on/off]` - Menghapus pesan jika bio profil member ada link/username.\n"
        "• `/setwaktu [menit]` - Mengatur rentang waktu deteksi pengulangan pesan.\n"
        "• `/antigcast` - Verifikasi status proteksi grup.\n\n"
        "🛡 *Pengelolaan spam di grup Anda adalah fokus utama kami.*", reply_markup=keyboard)

# --- ADMIN GROUP HANDLERS ---
@app.on_message(filters.command(["setlocal", "setglobal", "setwaktu", "status", "setbio", "antigcast"]) & filters.group)
async def admin_handlers(client, message):
    if not message.from_user: return
    cid, cmd = message.chat.id, message.command[0].lower()
    if cmd == "antigcast":
        me = await client.get_me()
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("👀 lihat detail bot", url=f"t.me/{me.username}?start=help")]])
        res = await message.reply("🛡 **Grup ini memiliki sistem Antispam**", reply_markup=keyboard)
        return asyncio.create_task(auto_delete_reply([message, res], 5))
    if not await is_admin(cid, message.from_user.id): return
    cfg = await get_config(cid)
    res = None
    if cmd == "status":
        text = (f"🖥 **DASHBOARD KEAMANAN GRUP**\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                f"📡 **Proteksi Lokal:** `{'AKTIF' if cfg.get('local', True) else 'OFF'}`\n"
                f"📡 **Proteksi Global:** `{'AKTIF' if cfg.get('global', True) else 'OFF'}`\n"
                f"📡 **Proteksi Bio Link:** `{'AKTIF' if cfg.get('bio_check', False) else 'OFF'}`\n"
                f"⏱ **Jendela Deteksi:** `{cfg.get('expiry', DEFAULT_LOCAL_EXPIRY)//60} Menit`\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯")
        res = await message.reply(text)
    elif cmd == "setwaktu":
        if len(message.command) > 1 and message.command[1].isdigit():
            m = int(message.command[1]); await update_config(cid, "expiry", m * 60)
            res = await message.reply(f"✅ Window lokal diatur ke: `{m} menit`.")
    elif cmd in ["setlocal", "setglobal", "setbio"]:
        if len(message.command) > 1:
            mode = message.command[1].lower() == "on"
            key = "bio_check" if cmd == "setbio" else ("local" if "local" in cmd else "global")
            await update_config(cid, key, mode)
            res = await message.reply(f"✅ `{key.upper()}` sekarang: `{'ON' if mode else 'OFF'}`.")
    if res: asyncio.create_task(auto_delete_reply([message, res], 10))

# --- CORE LOGIC (FILTER) ---
@app.on_message(filters.group & ~filters.service, group=2)
async def main_core_filter(client, message):
    if not message.from_user or await is_admin(message.chat.id, message.from_user.id): return
    cid, uid, mid = message.chat.id, message.from_user.id, message.id
    cfg = await get_config(cid)
    if cfg.get("bio_check", False):
        try:
            peer = await client.resolve_peer(uid)
            full = await client.invoke(functions.users.GetFullUser(id=peer))
            u_bio = full.full_user.about or ""
            if u_bio and re.search(LINK_PATTERN, u_bio, re.IGNORECASE):
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
            for loc_cid, loc_mid in locs:
                if (await get_config(loc_cid)).get("global", True): await delete_queue.put((loc_cid, [loc_mid]))
            return
        else: await messages_db.update_one({"_id": g_key}, {"$set": {"time": now_ts, "createdAt": now_dt, "locations": [[cid, mid]]}})
    else: await messages_db.insert_one({"_id": g_key, "time": now_ts, "createdAt": now_dt, "locations": [[cid, mid]]})
    await messages_db.update_one({"_id": l_key}, {"$set": {"time": now_ts, "msg_id": mid, "createdAt": now_dt}}, upsert=True)

# --- BOOTSTRAP ---
async def start_bot():
    await messages_db.create_index("createdAt", expireAfterSeconds=21600)
    threading.Thread(target=run_health_check, daemon=True).start()
    asyncio.create_task(delete_worker())
    await app.start()
    print("🚀 Bot Antispam is RUNNING!"); await idle(); await app.stop()

if __name__ == "__main__":
    asyncio.run(start_bot())
