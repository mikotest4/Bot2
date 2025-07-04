# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

from telethon import TelegramClient
from config import API_ID, API_HASH, BOT_TOKEN, STRING
from pyrogram import Client
import sys
import logging

logger = logging.getLogger(__name__)

client = None
app = None
userbot = None

async def start_client():
    """Start all clients with proper error handling"""
    global client, app, userbot
    
    clients = []
    
    try:
        # Start Telethon client
        client = TelegramClient("telethonbot", API_ID, API_HASH)
        if not client.is_connected():
            await client.start(bot_token=BOT_TOKEN)
            logger.info("✓ Telethon client started")
        clients.append(client)
        
        # Start Pyrogram app
        app = Client("pyrogrambot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
        await app.start()
        logger.info("✓ Pyrogram app started")
        clients.append(app)
        
        # Start userbot if STRING is provided
        if STRING:
            try:
                userbot = Client("4gbbot", api_id=API_ID, api_hash=API_HASH, session_string=STRING)
                await userbot.start()
                logger.info("✓ Userbot started")
                clients.append(userbot)
            except Exception as e:
                logger.error(f"Failed to start userbot: {e}")
                logger.error("Check your premium string session, it may be invalid or expired")
                # Don't exit, continue without userbot
        
        return clients
        
    except Exception as e:
        logger.error(f"Error starting clients: {e}")
        # Clean up any started clients
        for c in clients:
            try:
                if hasattr(c, 'stop'):
                    await c.stop()
                elif hasattr(c, 'disconnect'):
                    await c.disconnect()
            except:
                pass
        raise
