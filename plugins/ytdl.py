# ---------------------------------------------------
# File Name: ytdl.py (Complete Fixed Version)
# Description: A Pyrogram bot for downloading yt and other sites videos from Telegram channels or groups 
#              and uploading them back to Telegram.
# Author: Gagan
# GitHub: https://github.com/devgaganin/
# Telegram: https://t.me/team_spy_pro
# YouTube: https://youtube.com/@dev_gagan
# Created: 2025-01-11
# Last Modified: 2025-01-11
# Version: 2.0.5
# License: MIT License
# ---------------------------------------------------

import asyncio
import os
import tempfile
import time
import random
import string
import requests
import logging
import math
from pathlib import Path

# Import with error handling
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    yt_dlp = None
    YT_DLP_AVAILABLE = False
    logging.error("yt-dlp not installed. Video downloading will be disabled.")

try:
    from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    logging.error("mutagen not installed. Audio metadata editing will be disabled.")

try:
    from shared_client import client, app
    from telethon import events
    from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeAudio
    CLIENTS_AVAILABLE = True
except ImportError as e:
    CLIENTS_AVAILABLE = False
    logging.error(f"Client import error: {e}")

try:
    from devgagantools import fast_upload
    FAST_UPLOAD_AVAILABLE = True
except ImportError:
    FAST_UPLOAD_AVAILABLE = False
    logging.warning("devgagantools not available, using standard upload")

from config import YT_COOKIES, INSTA_COOKIES
from utils.func import get_video_metadata, screenshot
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import aiofiles

logger = logging.getLogger(__name__)
thread_pool = ThreadPoolExecutor(max_workers=2)
ongoing_downloads = {}

def get_random_string(length=7):
    """Generate random string for filenames"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def check_requirements():
    """Check if all required modules are available"""
    if not YT_DLP_AVAILABLE:
        return False, "yt-dlp not installed"
    if not CLIENTS_AVAILABLE:
        return False, "Telegram clients not available"
    return True, "All requirements satisfied"

def d_thumbnail(thumbnail_url, save_path):
    """Download thumbnail synchronously"""
    try:
        response = requests.get(thumbnail_url, stream=True, timeout=30)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return save_path
    except Exception as e:
        logger.error(f"Failed to download thumbnail: {e}")
        return None

async def download_thumbnail_async(url, path):
    """Download thumbnail asynchronously"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as response:
                if response.status == 200:
                    async with aiofiles.open(path, 'wb') as f:
                        await f.write(await response.read())
                    return True
    except Exception as e:
        logger.error(f"Failed to download thumbnail: {e}")
    return False

async def extract_info_async(ydl_opts, url):
    """Extract video/audio info in thread pool"""
    def sync_extract():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
        except Exception as e:
            logger.error(f"yt-dlp extraction failed: {e}")
            raise
    
    return await asyncio.get_event_loop().run_in_executor(thread_pool, sync_extract)

async def edit_audio_metadata(file_path, title, info_dict):
    """Edit audio metadata if mutagen is available"""
    if not MUTAGEN_AVAILABLE:
        logger.warning("Mutagen not available, skipping metadata editing")
        return
    
    try:
        def sync_edit():
            audio_file = MP3(file_path, ID3=ID3)
            try:
                audio_file.add_tags()
            except:
                pass
            
            audio_file.tags["TIT2"] = TIT2(encoding=3, text=title)
            audio_file.tags["TPE1"] = TPE1(encoding=3, text="Team SPY")
            audio_file.tags["COMM"] = COMM(encoding=3, lang="eng", desc="Comment", text="Processed by Team SPY")
            
            # Add thumbnail if available
            thumbnail_url = info_dict.get('thumbnail')
            if thumbnail_url:
                thumbnail_path = os.path.join(tempfile.gettempdir(), f"thumb_{get_random_string()}.jpg")
                if d_thumbnail(thumbnail_url, thumbnail_path):
                    try:
                        with open(thumbnail_path, 'rb') as img:
                            audio_file.tags["APIC"] = APIC(
                                encoding=3,
                                mime='image/jpeg',
                                type=3,
                                desc='Cover',
                                data=img.read()
                            )
                    except Exception as e:
                        logger.error(f"Failed to add thumbnail to metadata: {e}")
                    finally:
                        if os.path.exists(thumbnail_path):
                            os.remove(thumbnail_path)
            
            audio_file.save()
        
        await asyncio.get_event_loop().run_in_executor(thread_pool, sync_edit)
        
    except Exception as e:
        logger.error(f"Metadata editing failed: {e}")

async def progress_callback(current, total, message):
    """Progress callback for uploads"""
    try:
        if total > 0:
            percent = (current / total) * 100
            if percent % 10 == 0:  # Update every 10%
                await message.edit(f"**📤 Uploading: {percent:.1f}%**")
    except Exception as e:
        logger.error(f"Progress callback error: {e}")

async def upload_file_with_progress(client, file_path, chat_id, caption, progress_message):
    """Upload file with progress tracking"""
    try:
        if FAST_UPLOAD_AVAILABLE:
            uploaded = await fast_upload(
                client, 
                file_path, 
                reply=progress_message,
                name=None,
                progress_bar_function=lambda done, total: progress_callback(done, total, progress_message)
            )
            await client.send_file(chat_id, uploaded, caption=caption)
        else:
            # Standard upload
            await client.send_file(chat_id, file_path, caption=caption)
            
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise

async def process_audio(client, event, url, cookies_env_var=None):
    """Process audio download with comprehensive error handling"""
    requirements_ok, error_msg = check_requirements()
    if not requirements_ok:
        await event.reply(f"❌ **{error_msg}**")
        return

    temp_cookie_path = None
    download_path = None
    progress_message = None
    
    try:
        # Handle cookies
        cookies = None
        if cookies_env_var == "YT_COOKIES":
            cookies = YT_COOKIES
        elif cookies_env_var == "INSTA_COOKIES":
            cookies = INSTA_COOKIES
        
        if cookies and cookies.strip() and cookies != "# write here yt cookies" and cookies != "# write up here insta cookies":
            with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_cookie_file:
                temp_cookie_file.write(cookies)
                temp_cookie_path = temp_cookie_file.name

        # Set up download
        random_filename = f"@team_spy_pro_{event.sender_id}_{get_random_string()}"
        download_path = f"{random_filename}.mp3"

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f"{random_filename}.%(ext)s",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }],
            'quiet': True,
            'noplaylist': True,
            'no_warnings': True,
        }
        
        if temp_cookie_path:
            ydl_opts['cookiefile'] = temp_cookie_path

        progress_message = await event.reply("**🎵 Starting audio extraction...**")

        # Extract audio
        try:
            info_dict = await extract_info_async(ydl_opts, url)
            title = info_dict.get('title', 'Extracted Audio')
        except Exception as e:
            await progress_message.edit(f"❌ **Extraction failed:** {str(e)}")
            return

        # Check if file was created
        if not os.path.exists(download_path):
            await progress_message.edit("❌ **Audio file not found after extraction**")
            return

        await progress_message.edit("**📝 Processing metadata...**")

        # Edit metadata
        try:
            await edit_audio_metadata(download_path, title, info_dict)
        except Exception as e:
            logger.warning(f"Metadata editing failed: {e}")

        # Upload file
        await progress_message.edit("**📤 Uploading audio...**")
        
        try:
            file_size = os.path.getsize(download_path)
            duration = info_dict.get('duration', 0)
            
            caption = f"**🎵 {title}**\n\n**📊 Size:** {file_size / (1024*1024):.1f} MB\n**⏱️ Duration:** {duration//60}:{duration%60:02d}\n\n**Powered by Team SPY**"
            
            await upload_file_with_progress(client, download_path, event.chat_id, caption, progress_message)
            await progress_message.delete()
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            await progress_message.edit(f"❌ **Upload failed:** {str(e)}")

    except Exception as e:
        logger.error(f"Audio processing error: {e}")
        if progress_message:
            await progress_message.edit(f"❌ **Error:** {str(e)}")
        else:
            await event.reply(f"❌ **Error processing audio:** {str(e)}")
    
    finally:
        # Cleanup
        if download_path and os.path.exists(download_path):
            try:
                os.remove(download_path)
            except:
                pass
        if temp_cookie_path and os.path.exists(temp_cookie_path):
            try:
                os.remove(temp_cookie_path)
            except:
                pass

async def process_video(client, event, url, cookies_env_var=None):
    """Process video download with comprehensive error handling"""
    requirements_ok, error_msg = check_requirements()
    if not requirements_ok:
        await event.reply(f"❌ **{error_msg}**")
        return

    temp_cookie_path = None
    download_path = None
    progress_message = None
    
    try:
        # Handle cookies
        cookies = None
        if cookies_env_var == "YT_COOKIES":
            cookies = YT_COOKIES
        elif cookies_env_var == "INSTA_COOKIES":
            cookies = INSTA_COOKIES
        
        if cookies and cookies.strip() and cookies != "# write here yt cookies" and cookies != "# write up here insta cookies":
            with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_cookie_file:
                temp_cookie_file.write(cookies)
                temp_cookie_path = temp_cookie_file.name

        # Set up download
        random_filename = f"@team_spy_pro_{event.sender_id}_{get_random_string()}"
        download_path = f"{random_filename}.mp4"

        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': f"{random_filename}.%(ext)s",
            'quiet': True,
            'noplaylist': True,
            'no_warnings': True,
        }
        
        if temp_cookie_path:
            ydl_opts['cookiefile'] = temp_cookie_path

        progress_message = await event.reply("**🎬 Starting video extraction...**")

        # Extract video
        try:
            info_dict = await extract_info_async(ydl_opts, url)
            title = info_dict.get('title', 'Extracted Video')
        except Exception as e:
            await progress_message.edit(f"❌ **Extraction failed:** {str(e)}")
            return

        # Find the actual downloaded file
        possible_extensions = ['mp4', 'mkv', 'webm', 'avi']
        actual_file = None
        for ext in possible_extensions:
            test_path = f"{random_filename}.{ext}"
            if os.path.exists(test_path):
                actual_file = test_path
                break

        if not actual_file:
            await progress_message.edit("❌ **Video file not found after extraction**")
            return

        download_path = actual_file

        # Upload file
        await progress_message.edit("**📤 Uploading video...**")
        
        try:
            file_size = os.path.getsize(download_path)
            duration = info_dict.get('duration', 0)
            width = info_dict.get('width', 0)
            height = info_dict.get('height', 0)
            
            caption = f"**🎬 {title}**\n\n**📊 Size:** {file_size / (1024*1024):.1f} MB\n**⏱️ Duration:** {duration//60}:{duration%60:02d}\n**📐 Resolution:** {width}x{height}\n\n**Powered by Team SPY**"
            
            await upload_file_with_progress(client, download_path, event.chat_id, caption, progress_message)
            await progress_message.delete()
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            await progress_message.edit(f"❌ **Upload failed:** {str(e)}")

    except Exception as e:
        logger.error(f"Video processing error: {e}")
        if progress_message:
            await progress_message.edit(f"❌ **Error:** {str(e)}")
        else:
            await event.reply(f"❌ **Error processing video:** {str(e)}")
    
    finally:
        # Cleanup
        if download_path and os.path.exists(download_path):
            try:
                os.remove(download_path)
            except:
                pass
        if temp_cookie_path and os.path.exists(temp_cookie_path):
            try:
                os.remove(temp_cookie_path)
            except:
                pass

# Event handlers with error checking
if CLIENTS_AVAILABLE and client and app:
    @client.on(events.NewMessage(pattern=r"/adl"))
    async def audio_download_handler(event):
        """Handle audio download command"""
        user_id = event.sender_id
        
        if user_id in ongoing_downloads:
            await event.reply("⏳ **You already have an ongoing download. Please wait!**")
            return

        args = event.message.text.split()
        if len(args) < 2:
            await event.reply("**Usage:** `/adl <video-link>`\n\n**Example:** `/adl https://youtube.com/watch?v=example`")
            return

        requirements_ok, error_msg = check_requirements()
        if not requirements_ok:
            await event.reply(f"❌ **{error_msg}**\n\nPlease install: `pip install yt-dlp`")
            return

        url = args[1]
        ongoing_downloads[user_id] = True

        try:
            if "instagram.com" in url:
                await process_audio(client, event, url, "INSTA_COOKIES")
            elif "youtube.com" in url or "youtu.be" in url:
                await process_audio(client, event, url, "YT_COOKIES")
            else:
                await process_audio(client, event, url)
        except Exception as e:
            logger.error(f"Audio download error: {e}")
            await event.reply(f"❌ **Error:** {str(e)}")
        finally:
            ongoing_downloads.pop(user_id, None)

    @client.on(events.NewMessage(pattern=r"/dl"))
    async def video_download_handler(event):
        """Handle video download command"""
        user_id = event.sender_id
        
        if user_id in ongoing_downloads:
            await event.reply("⏳ **You already have an ongoing download. Please wait!**")
            return

        args = event.message.text.split()
        if len(args) < 2:
            await event.reply("**Usage:** `/dl <video-link>`\n\n**Example:** `/dl https://youtube.com/watch?v=example`")
            return

        requirements_ok, error_msg = check_requirements()
        if not requirements_ok:
            await event.reply(f"❌ **{error_msg}**\n\nPlease install: `pip install yt-dlp`")
            return

        url = args[1]
        ongoing_downloads[user_id] = True

        try:
            if "instagram.com" in url:
                await process_video(client, event, url, "INSTA_COOKIES")
            elif "youtube.com" in url or "youtu.be" in url:
                await process_video(client, event, url, "YT_COOKIES")
            else:
                await process_video(client, event, url)
        except Exception as e:
            logger.error(f"Video download error: {e}")
            await event.reply(f"❌ **Error:** {str(e)}")
        finally:
            ongoing_downloads.pop(user_id, None)

    @client.on(events.NewMessage(pattern=r"/cancel"))
    async def cancel_download_handler(event):
        """Handle download cancellation"""
        user_id = event.sender_id
        
        if user_id in ongoing_downloads:
            ongoing_downloads.pop(user_id, None)
            await event.reply("✅ **Download cancelled successfully!**")
        else:
            await event.reply("❌ **No ongoing download to cancel.**")

else:
    logger.error("Clients not available, ytdl handlers not registered")

# Module initialization
if __name__ == "__main__":
    logger.info("ytdl.py module loaded")
    requirements_ok, error_msg = check_requirements()
    if requirements_ok:
        logger.info("✅ All requirements satisfied for ytdl module")
    else:
        logger.error(f"❌ {error_msg}")
