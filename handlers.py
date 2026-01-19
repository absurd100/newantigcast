import re
import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import app, OWNER_ID, regex_db, DEFAULT_LOCAL_EXPIRY
from utils import is_admin, get_config, update_config
from worker import auto_delete_reply

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

@app.on_message(filters.command(["setlocal", "setglobal", "setwaktu", "status", "setbio", "antigcast"]) & filters.group)
async def admin_handlers(client, message):
    if not message.from_user: return
    cid, cmd = message.chat.id, message.command[0].lower()
    from main import delete_queue
    
    if cmd == "antigcast":
        me = await client.get_me()
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("👀 lihat detail bot", url=f"t.me/{me.username}?start=help")]])
        res = await message.reply("🛡 **Grup ini memiliki sistem Antispam**", reply_markup=keyboard)
        return asyncio.create_task(auto_delete_reply(delete_queue, [message, res], 5))

    if not await is_admin(client, cid, message.from_user.id): return
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
    
    if res: asyncio.create_task(auto_delete_reply(delete_queue, [message, res], 10))
