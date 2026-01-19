from pyrogram.enums import ChatMemberStatus
from config import config_db, DEFAULT_LOCAL_EXPIRY

async def get_config(chat_id):
    cfg = await config_db.find_one({"chat_id": chat_id})
    if not cfg:
        return {"local": True, "global": True, "expiry": DEFAULT_LOCAL_EXPIRY, "bio_check": False}
    return cfg

async def update_config(chat_id, key, value):
    await config_db.update_one({"chat_id": chat_id}, {"$set": {key: value}}, upsert=True)

async def is_admin(client, chat_id, user_id):
    if not user_id: return False
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except: return False
