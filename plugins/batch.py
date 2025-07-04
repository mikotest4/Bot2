# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

import os, re, time, asyncio, json, asyncio 
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import UserNotParticipant
from config import API_ID, API_HASH, LOG_GROUP, STRING, FORCE_SUB, FREEMIUM_LIMIT, PREMIUM_LIMIT
from utils.func import get_user_data, screenshot, thumbnail, get_video_metadata
from utils.func import get_user_data_key, process_text_with_rules, is_premium_user, E
from shared_client import app as X
from plugins.settings import rename_file
from plugins.start import subscribe as sub
from utils.custom_filters import login_in_progress
from utils.encrypt import dcs
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

Y = None if not STRING else __import__('shared_client').userbot
Z, P, UB, UC, emp = {}, {}, {}, {}, {}

ACTIVE_USERS = {}
ACTIVE_USERS_FILE = "active_users.json"
ongoing_downloads = {}

# fixed directory file_name problems 
def sanitize(filename):
    return re.sub(r'[<>:"/\\|?*\']', '_', filename).strip(" .")[:255]

def load_active_users():
    try:
        if os.path.exists(ACTIVE_USERS_FILE):
            with open(ACTIVE_USERS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception:
        return {}

async def save_active_users_to_file():
    try:
        with open(ACTIVE_USERS_FILE, 'w') as f:
            json.dump(ACTIVE_USERS, f)
    except Exception as e:
        logger.error(f"Error saving active users: {e}")

async def add_active_batch(user_id: int, batch_info: Dict[str, Any]):
    ACTIVE_USERS[str(user_id)] = batch_info
    await save_active_users_to_file()

def is_user_active(user_id: int) -> bool:
    return str(user_id) in ACTIVE_USERS

async def update_batch_progress(user_id: int, current: int, success: int):
    if str(user_id) in ACTIVE_USERS:
        ACTIVE_USERS[str(user_id)]["current"] = current
        ACTIVE_USERS[str(user_id)]["success"] = success
        await save_active_users_to_file()

async def request_batch_cancel(user_id: int):
    if str(user_id) in ACTIVE_USERS:
        ACTIVE_USERS[str(user_id)]["cancel_requested"] = True
        await save_active_users_to_file()
        return True
    return False

def should_cancel(user_id: int) -> bool:
    user_str = str(user_id)
    return user_str in ACTIVE_USERS and ACTIVE_USERS[user_str].get("cancel_requested", False)

async def remove_active_batch(user_id: int):
    if str(user_id) in ACTIVE_USERS:
        del ACTIVE_USERS[str(user_id)]
        await save_active_users_to_file()

def get_batch_info(user_id: int) -> Optional[Dict[str, Any]]:
    return ACTIVE_USERS.get(str(user_id))

ACTIVE_USERS = load_active_users()

async def upd_dlg(c):
    try:
        async for _ in c.get_dialogs(limit=100): pass
        return True
    except Exception as e:
        logger.error(f'Failed to update dialogs: {e}')
        return False

async def get_msg(c, u, i, d, lt):
    try:
        if lt == 'public':
            try:
                xm = await c.get_messages(i, d)
                emp[i] = getattr(xm, "empty", False)
                if emp[i]:
                    try: await u.join_chat(i)
                    except: pass
                    xm = await u.get_messages((await u.get_chat(f"@{i}")).id, d)
                return xm
            except Exception as e:
                logger.error(f'Error fetching public message: {e}')
                return None
        else:
            if u:
                try:
                    async for _ in u.get_dialogs(limit=50): pass
                    chat_id = i if str(i).startswith('-100') else f'-100{i}' if i.isdigit() else i
                    try:
                        peer = await u.resolve_peer(chat_id)
                        if hasattr(peer, 'channel_id'): resolved_id = f'-100{peer.channel_id}'
                        elif hasattr(peer, 'chat_id'): resolved_id = f'-{peer.chat_id}'
                        elif hasattr(peer, 'user_id'): resolved_id = peer.user_id
                        else: resolved_id = chat_id
                        return await u.get_messages(resolved_id, d)
                    except Exception:
                        try:
                            chat = await u.get_chat(chat_id)
                            return await u.get_messages(chat.id, d)
                        except Exception:
                            async for _ in u.get_dialogs(limit=200): pass
                            return await u.get_messages(chat_id, d)
                except Exception as e:
                    logger.error(f'Private channel error: {e}')
                    return None
            return None
    except Exception as e:
        logger.error(f'Error fetching message: {e}')
        return None

async def get_ubot(uid):
    bt = await get_user_data_key(uid, "bot_token", None)
    if not bt: return None
    if uid in UB: return UB.get(uid)
    try:
        bot = Client(f"user_{uid}", bot_token=bt, api_id=API_ID, api_hash=API_HASH)
        await bot.start()
        UB[uid] = bot
        return bot
    except Exception as e:
        logger.error(f"Error starting bot for user {uid}: {e}")
        return None

async def get_uclient(uid):
    ud = await get_user_data(uid)
    ubot = UB.get(uid)
    cl = UC.get(uid)
    if cl: return cl
    if not ud: return ubot if ubot else None
    xxx = ud.get('session_string')
    if xxx:
        try:
            ss = dcs(xxx)
            gg = Client(f'{uid}_client', api_id=API_ID, api_hash=API_HASH, device_model="v3saver", session_string=ss)
            await gg.start()
            await upd_dlg(gg)
            UC[uid] = gg
            return gg
        except Exception as e:
            logger.error(f'User client error: {e}')
            return ubot if ubot else Y
    return Y

async def prog(c, t, C, h, m, st):
    global P
    p = c / t * 100
    interval = 10 if t >= 100 * 1024 * 1024 else 20 if t >= 50 * 1024 * 1024 else 30 if t >= 10 * 1024 * 1024 else 50
    step = int(p // interval) * interval
    if m not in P or P[m] != step or p >= 100:
        P[m] = step
        c_mb = c / (1024 * 1024)
        t_mb = t / (1024 * 1024)
        bar = '🟢' * int(p / 10) + '🔴' * (10 - int(p / 10))
        speed = c / (time.time() - st) / (1024 * 1024) if time.time() > st else 0
        eta = time.strftime('%M:%S', time.gmtime((t - c) / (speed * 1024 * 1024))) if speed > 0 else '00:00'
        await C.edit_message_text(h, m, f"__**Pyro Handler...**__\n\n{bar}\n\n⚡**__Completed__**: {c_mb:.2f} MB / {t_mb:.2f} MB\n📊 **__Done__**: {p:.2f}%\n🚀 **__Speed__**: {speed:.2f} MB/s\n⏳ **__ETA__**: {eta}\n\n**__Powered by Team SPY__**")
        if p >= 100: P.pop(m, None)

async def send_direct(c, m, tcid, ft=None, rtmid=None):
    try:
        if m.video:
            await c.send_video(tcid, m.video.file_id, caption=ft, duration=m.video.duration, width=m.video.width, height=m.video.height, reply_to_message_id=rtmid)
        elif m.video_note:
            await c.send_video_note(tcid, m.video_note.file_id, duration=m.video_note.duration, length=m.video_note.length, reply_to_message_id=rtmid)
        elif m.animation:
            await c.send_animation(tcid, m.animation.file_id, duration=m.animation.duration, width=m.animation.width, height=m.animation.height, caption=ft, reply_to_message_id=rtmid)
        elif m.sticker:
            await c.send_sticker(tcid, m.sticker.file_id, reply_to_message_id=rtmid)
        elif m.sticker:
            await c.send_sticker(tcid, m.sticker.file_id, reply_to_message_id=rtmid)
        elif m.document:
            await c.send_document(tcid, m.document.file_id, caption=ft, reply_to_message_id=rtmid)
        elif m.audio:
            await c.send_audio(tcid, m.audio.file_id, caption=ft, duration=m.audio.duration, performer=m.audio.performer, title=m.audio.title, reply_to_message_id=rtmid)
        elif m.voice:
            await c.send_voice(tcid, m.voice.file_id, caption=ft, duration=m.voice.duration, reply_to_message_id=rtmid)
        elif m.photo:
            await c.send_photo(tcid, m.photo.file_id, caption=ft, reply_to_message_id=rtmid)
        elif m.text:
            await c.send_message(tcid, ft if ft else m.text, reply_to_message_id=rtmid)
    except Exception as e:
        logger.error(f"Error sending direct: {e}")

async def handle_file_download(c, m, tcid, uid, ft=None, rtmid=None):
    """Handle file download and upload with progress"""
    try:
        # Check if file should be downloaded and re-uploaded
        rename_tag = await get_user_data_key(uid, "rename_tag", None)
        
        if rename_tag or ft:
            # Download and re-upload with custom name/caption
            status_msg = await c.send_message(tcid, "📥 **Downloading file...**", reply_to_message_id=rtmid)
            
            # Download file
            start_time = time.time()
            
            # Get file info
            if m.document:
                file_name = m.document.file_name or "document"
                file_size = m.document.file_size
            elif m.video:
                file_name = f"video_{int(time.time())}.mp4"
                file_size = m.video.file_size
            elif m.audio:
                file_name = m.audio.file_name or f"audio_{int(time.time())}.mp3"
                file_size = m.audio.file_size
            elif m.photo:
                file_name = f"photo_{int(time.time())}.jpg"
                file_size = 0  # Photos don't have file_size
            else:
                file_name = f"file_{int(time.time())}"
                file_size = 0
            
            # Apply rename tag
            if rename_tag:
                file_extension = os.path.splitext(file_name)[1]
                file_name = f"{rename_tag}{file_extension}"
            
            # Sanitize filename
            file_name = sanitize(file_name)
            
            # Download file with progress
            try:
                downloaded_file = await c.download_media(
                    m,
                    file_name=file_name,
                    progress=prog,
                    progress_args=(c, tcid, status_msg.id, start_time)
                )
                
                if downloaded_file:
                    await status_msg.edit("📤 **Uploading file...**")
                    
                    # Upload file
                    if m.video:
                        # Get video metadata
                        duration, width, height = await get_video_metadata(downloaded_file)
                        thumb_path = await screenshot(downloaded_file, duration, uid)
                        
                        await c.send_video(
                            tcid, 
                            downloaded_file, 
                            caption=ft,
                            duration=duration,
                            width=width,
                            height=height,
                            thumb=thumb_path,
                            reply_to_message_id=rtmid,
                            progress=prog,
                            progress_args=(c, tcid, status_msg.id, time.time())
                        )
                        
                        # Clean up
                        if thumb_path and os.path.exists(thumb_path):
                            os.remove(thumb_path)
                            
                    elif m.document:
                        thumb_path = thumbnail(uid)
                        await c.send_document(
                            tcid, 
                            downloaded_file, 
                            caption=ft,
                            thumb=thumb_path,
                            reply_to_message_id=rtmid,
                            progress=prog,
                            progress_args=(c, tcid, status_msg.id, time.time())
                        )
                        
                    elif m.audio:
                        thumb_path = thumbnail(uid)
                        await c.send_audio(
                            tcid, 
                            downloaded_file, 
                            caption=ft,
                            thumb=thumb_path,
                            duration=m.audio.duration,
                            performer=m.audio.performer,
                            title=m.audio.title,
                            reply_to_message_id=rtmid,
                            progress=prog,
                            progress_args=(c, tcid, status_msg.id, time.time())
                        )
                        
                    elif m.photo:
                        await c.send_photo(
                            tcid, 
                            downloaded_file, 
                            caption=ft,
                            reply_to_message_id=rtmid
                        )
                    
                    # Clean up downloaded file
                    if os.path.exists(downloaded_file):
                        os.remove(downloaded_file)
                    
                    await status_msg.delete()
                
            except Exception as e:
                logger.error(f"Download/upload error: {e}")
                await status_msg.edit(f"❌ **Error:** {str(e)}")
                
        else:
            # Direct send without download
            await send_direct(c, m, tcid, ft, rtmid)
            
    except Exception as e:
        logger.error(f"File handling error: {e}")
        await send_direct(c, m, tcid, ft, rtmid)

@X.on_message(filters.command("batch") & filters.private & ~login_in_progress)
async def batch_handler(client, message):
    user_id = message.from_user.id
    
    # Check subscription
    subscription_status = await sub(client, message)
    if subscription_status == 1:
        return
    
    # Check if user already has an active batch
    if is_user_active(user_id):
        await message.reply("⏳ **You have an active task. Use /stop to cancel it.**")
        return
    
    # Check if user is premium or within limits
    is_premium = await is_premium_user(user_id)
    limit = PREMIUM_LIMIT if is_premium else FREEMIUM_LIMIT
    
    if not is_premium and FREEMIUM_LIMIT == 0:
        await message.reply("❌ **Batch extraction is only available for premium users.**\n\nUse /plan to see premium plans.")
        return
    
    # Ask for links
    ask_msg = await message.reply(
        f"📋 **Send me the links to extract (one per line)**\n\n"
        f"{'🔸 **Premium User**' if is_premium else '🔸 **Free User**'}\n"
        f"📊 **Batch Limit:** {limit} links\n\n"
        f"**Example:**\n"
        f"`https://t.me/channelname/123`\n"
        f"`https://t.me/c/1234567890/123`\n\n"
        f"Send /cancel to cancel this operation."
    )
    
    # Add to active users
    await add_active_batch(user_id, {
        "status": "waiting_for_links",
        "start_time": time.time(),
        "limit": limit,
        "current": 0,
        "success": 0,
        "cancel_requested": False,
        "ask_msg_id": ask_msg.id
    })

@X.on_message(filters.text & filters.private & ~filters.command(['start', 'batch', 'cancel', 'stop', 'login', 'logout', 'help', 'settings', 'plan', 'status', 'dl', 'adl', 'setbot', 'rembot', 'session', 'terms', 'stats', 'transfer', 'add', 'rem', 'set']) & ~login_in_progress)
async def handle_batch_links(client, message):
    user_id = message.from_user.id
    
    # Check if user has active batch waiting for links
    if not is_user_active(user_id):
        return
    
    batch_info = get_batch_info(user_id)
    if not batch_info or batch_info.get("status") != "waiting_for_links":
        return
    
    try:
        # Parse links
        text = message.text.strip()
        links = [link.strip() for link in text.split('\n') if link.strip()]
        
        if not links:
            await message.reply("❌ **No valid links found. Please send links one per line.**")
            return
        
        # Check limit
        limit = batch_info.get("limit", FREEMIUM_LIMIT)
        if len(links) > limit:
            await message.reply(f"❌ **Too many links! Maximum allowed: {limit}**\n\nSend fewer links or upgrade to premium.")
            return
        
        # Validate links
        valid_links = []
        for link in links:
            if "t.me" in link:
                valid_links.append(link)
        
        if not valid_links:
            await message.reply("❌ **No valid Telegram links found.**\n\nPlease send valid t.me links.")
            return
        
        # Update batch info
        batch_info["status"] = "processing"
        batch_info["links"] = valid_links
        batch_info["total"] = len(valid_links)
        await add_active_batch(user_id, batch_info)
        
        # Start processing
        status_msg = await message.reply(
            f"🚀 **Starting batch extraction...**\n\n"
            f"📊 **Total Links:** {len(valid_links)}\n"
            f"⏳ **Status:** Processing...\n\n"
            f"Use /stop to cancel."
        )
        
        # Process links
        await process_batch_links(client, message, user_id, valid_links, status_msg)
        
    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        await message.reply(f"❌ **Error:** {str(e)}")
        await remove_active_batch(user_id)

async def process_batch_links(client, message, user_id, links, status_msg):
    """Process batch links with cancellation support"""
    try:
        total = len(links)
        success = 0
        failed = 0
        
        for i, link in enumerate(links):
            # Check for cancellation
            if should_cancel(user_id) or not is_user_active(user_id):
                await status_msg.edit(
                    f"🛑 **Batch cancelled by user**\n\n"
                    f"📊 **Progress:** {i}/{total}\n"
                    f"✅ **Success:** {success}\n"
                    f"❌ **Failed:** {failed}"
                )
                break
            
            try:
                # Update progress
                await update_batch_progress(user_id, i + 1, success)
                await status_msg.edit(
                    f"🔄 **Processing batch...**\n\n"
                    f"📊 **Progress:** {i + 1}/{total}\n"
                    f"✅ **Success:** {success}\n"
                    f"❌ **Failed:** {failed}\n\n"
                    f"🔗 **Current:** {link[:50]}...\n\n"
                    f"Use /stop to cancel."
                )
                
                # Process single link
                result = await process_single_link(client, message, user_id, link)
                if result:
                    success += 1
                else:
                    failed += 1
                
                # Small delay between links
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing link {link}: {e}")
                failed += 1
                continue
        
        # Final status
        if is_user_active(user_id) and not should_cancel(user_id):
            await status_msg.edit(
                f"✅ **Batch completed!**\n\n"
                f"📊 **Total:** {total}\n"
                f"✅ **Success:** {success}\n"
                f"❌ **Failed:** {failed}\n\n"
                f"**Powered by Team SPY**"
            )
        
    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        await status_msg.edit(f"❌ **Batch failed:** {str(e)}")
    finally:
        await remove_active_batch(user_id)

async def process_single_link(client, message, user_id, link):
    """Process a single link and return success status"""
    try:
        # Parse link
        chat_id, msg_id, link_type = E(link)
        if not chat_id or not msg_id:
            return False
        
        # Get appropriate client
        user_client = await get_uclient(user_id)
        if not user_client:
            return False
        
        # Get message
        msg = await get_msg(client, user_client, chat_id, msg_id, link_type)
        if not msg:
            return False
        
        # Get target chat
        target_chat = await get_user_data_key(user_id, "chat_id", message.chat.id)
        
        # Get custom caption
        custom_caption = await get_user_data_key(user_id, "caption", None)
        
        # Process caption
        if custom_caption:
            final_caption = custom_caption
        elif msg.caption:
            final_caption = await process_text_with_rules(user_id, msg.caption)
        else:
            final_caption = None
        
        # Check if file needs special handling
        if msg.document or msg.video or msg.audio:
            await handle_file_download(client, msg, target_chat, user_id, final_caption)
        else:
            await send_direct(client, msg, target_chat, final_caption)
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing single link {link}: {e}")
        return False

@X.on_message(filters.command(['cancel', 'stop']) & filters.private)
async def handle_batch_cancel(client, message):
    user_id = message.from_user.id
    
    if is_user_active(user_id):
        # Force stop the batch immediately
        await remove_active_batch(user_id)
        
        # Clear any ongoing downloads
        if user_id in ongoing_downloads:
            ongoing_downloads.pop(user_id, None)
        
        await message.reply("✅ **Batch stopped successfully!**")
    else:
        await message.reply("❌ **No active batch found to stop.**")

@X.on_message(filters.command("single") & filters.private & ~login_in_progress)
async def single_handler(client, message):
    user_id = message.from_user.id
    
    # Check subscription
    subscription_status = await sub(client, message)
    if subscription_status == 1:
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply(
            "**Usage:** `/single <telegram_link>`\n\n"
            "**Example:** `/single https://t.me/channelname/123`"
        )
        return
    
    link = args[1].strip()
    
    if "t.me" not in link:
        await message.reply("❌ **Please provide a valid Telegram link.**")
        return
    
    status_msg = await message.reply("🔄 **Processing link...**")
    
    try:
        result = await process_single_link(client, message, user_id, link)
        if result:
            await status_msg.edit("✅ **Link processed successfully!**")
        else:
            await status_msg.edit("❌ **Failed to process link.**")
    except Exception as e:
        logger.error(f"Single link processing error: {e}")
        await status_msg.edit(f"❌ **Error:** {str(e)}")

# Initialize active users on module load
ACTIVE_USERS = load_active_users()

# Plugin runner function (if needed by main.py)
async def run_batch_plugin():
    """Plugin runner function"""
    logger.info("Batch plugin loaded and ready")
