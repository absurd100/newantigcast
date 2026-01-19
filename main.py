import time
import asyncio
import datetime
import hashlib
import re
from pyrogram import filters, idle
from pyrogram.raw import functions

from config import app, regex_db, messages_db, GLOBAL_EXPIRY, DEFAULT_LOCAL_EXPIRY, LINK_PATTERN
from health import start_health_server
from worker import delete_worker, setup_db, auto_delete_reply
from utils import get_config, is_admin
import handlers # Mengaktifkan semua command

delete_queue = asyncio.Queue()

@app.on_message(filters.group & ~filters.service, group=2)
async def main_core_filter(client, message):
    if not message.from_user: return
    cid, uid, mid = message.chat.id, message.from_user.id, message.id
    
    if await is_admin(client, cid, uid): return
    cfg = await get_config(cid)
    
    # 1. BIO LINK DETECTOR
    if cfg.get("bio_check", False):
        try:
            peer = await client.resolve_peer(uid)
            full_user_raw = await client.invoke(functions.users.GetFullUser(id=peer))
            u_bio = full_user_raw.full_user.about or ""
            if u_bio and re.search(LINK_PATTERN, u_bio, re.IGNORECASE):
                await delete_queue.put((cid, [mid]))
                return
        except: pass

    if not (message.text or message.caption): return
    content = (message.text or message.caption).strip()
    if content.startswith("/"): return

    # 2. REGEX BLACKLIST
    async for reg in regex_db.find({}):
        if re.search(reg["pattern"], content, re.IGNORECASE):
            await delete_queue.put((cid, [mid]))
            return

    now_ts = time.time()
    now_dt = datetime.datetime.now(datetime.UTC)
    content_hash = hashlib.md5(content.encode()).hexdigest()
    
    # 3. ANTI DUPLIKASI LOKAL
    local_key = f"loc_{cid}_{uid}_{content_hash}"
    existing_local = await messages_db.find_one({"_id": local_key})
    if cfg.get("local", True) and existing_local:
        if (now_ts - existing_local["time"]) < cfg.get("expiry", DEFAULT_LOCAL_EXPIRY):
            await delete_queue.put((cid, [existing_local["msg_id"], mid]))
            return

    # 4. ANTI DUPLIKASI GLOBAL
    global_key = f"glob_{uid}_{content_hash}"
    existing_global = await messages_db.find_one({"_id": global_key})
    if existing_global:
        if (now_ts - existing_global["time"]) < GLOBAL_EXPIRY:
            locs = existing_global.get("locations", [])
            if [cid, mid] not in locs: locs.append([cid, mid])
            await messages_db.update_one({"_id": global_key}, {"$set": {"locations": locs, "createdAt": now_dt}})
            for loc_cid, loc_mid in locs:
                target_cfg = await get_config(loc_cid)
                if target_cfg.get("global", True):
                    await delete_queue.put((loc_cid, [loc_mid]))
            return
        else:
            await messages_db.update_one({"_id": global_key}, {"$set": {"time": now_ts, "createdAt": now_dt, "locations": [[cid, mid]]}})
    else:
        await messages_db.insert_one({"_id": global_key, "time": now_ts, "createdAt": now_dt, "locations": [[cid, mid]]})

    await messages_db.update_one({"_id": local_key}, {"$set": {"time": now_ts, "msg_id": mid, "createdAt": now_dt}}, upsert=True)

async def start_bot():
    await setup_db()
    start_health_server()
    asyncio.create_task(delete_worker(app, delete_queue))
    await app.start()
    print("🚀 Bot Antispam is RUNNING!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(start_bot())
