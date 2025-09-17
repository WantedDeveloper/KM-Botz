import asyncio, base64, random
from pyrogram import enums
from pyrogram.types import *
from pyrogram.file_id import FileId
from struct import pack
from plugins.config import *
from plugins.database import db
from plugins.clone_instance import get_client
from plugins.script import script

def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0

    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0

            r += bytes([i])

    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref

async def auto_post_clone(bot_id: int, db, target_channel: int):
    try:
        bot_id = int(bot_id)
        clone = await db.get_clone_by_id(bot_id)
        if not clone or not clone.get("auto_post", False):
            return

        owner_id = clone.get("user_id")
        if not await db.is_premium(owner_id):
            return

        clone_client = get_client(bot_id)
        if not clone_client:
            return

        FIX_IMAGE = "https://i.ibb.co/gFv0Nm8M/IMG-20250904-163513-052.jpg"

        while True:
            try:
                fresh = await db.get_clone_by_id(bot_id)
                if not fresh or not fresh.get("auto_post", False):
                    return

                owner_id = fresh.get("user_id")
                if not await db.is_premium(owner_id):
                    return

                item = await db.pop_random_unposted_media(bot_id)
                if not item:
                    print(f"⌛ No new media for {bot_id}, sleeping 60s...")
                    await asyncio.sleep(60)
                    continue

                file_id = item.get("file_id")
                if not file_id:
                    await db.mark_media_posted(item["_id"], bot_id)
                    continue

                await db.mark_media_posted(item["_id"], bot_id)

                unpack, _ = unpack_new_file_id(file_id)
                string = f"file_{unpack}"
                outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
                bot_username = (await clone_client.get_me()).username
                share_link = f"https://t.me/{bot_username}?start=AUTO-{outstr}"

                header = fresh.get("header")
                footer = fresh.get("footer")
                selected_caption = random.choice(script.CAPTION_LIST) if script.CAPTION_LIST else "Here is your file"

                text = ""

                if header:
                    text += f"<blockquote>{header}</blockquote>\n\n"

                text += f"{selected_caption}\n\n<blockquote>🔗 Here is your link:\n{share_link}</blockquote>"

                if footer:
                    text += f"\n\n<blockquote>{footer}</blockquote>"

                await clone_client.send_photo(
                    chat_id=target_channel,
                    photo=FIX_IMAGE,
                    caption=text,
                    parse_mode=enums.ParseMode.HTML
                )

                await db.mark_media_posted(item["_id"], bot_id)

                sleep_time = int(fresh.get("interval_sec", 3600))
                await asyncio.sleep(sleep_time)
            except Exception as e:
                if 'item' in locals() and item:
                    await db.unmark_media_posted(bot_id, item["file_id"])

                print(f"⚠️ Clone Auto-post error for {bot_id}: {e}")
                try:
                    await clone_client.send_message(
                        LOG_CHANNEL,
                        f"⚠️ Clone Auto Post Error:\n\n<code>{e}</code>\n\nKindly check this message to get assistance."
                    )
                except:
                    pass
                await asyncio.sleep(30)
    except Exception as e:
        await client.send_message(
            LOG_CHANNEL,
            f"❌ Clone AutoPost crashed for {bot_id}:\n\n<code>{e}</code>\n\nKindly check this message for assistance."
        )
        print(f"❌ Clone AutoPost crashed for {bot_id}: {e}")
