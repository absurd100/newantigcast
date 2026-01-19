import asyncio
from config import messages_db

async def delete_worker(app, delete_queue):
    while True:
        chat_id, message_ids = await delete_queue.get()
        try:
            await app.delete_messages(chat_id, message_ids)
            await asyncio.sleep(0.1)
        except: pass
        finally:
            delete_queue.task_done()

async def auto_delete_reply(delete_queue, messages, delay=5):
    await asyncio.sleep(delay)
    for msg in messages:
        try: await delete_queue.put((msg.chat.id, [msg.id]))
        except: pass

async def setup_db():
    await messages_db.create_index("createdAt", expireAfterSeconds=21600)
    print("✅ Database & TTL Index 6 Hours Active.")
