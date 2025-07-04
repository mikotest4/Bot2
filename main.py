# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

import asyncio
import importlib
import os
import sys
import signal
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables for clients
clients = []
running = True

def signal_handler(signum, frame):
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False

async def check_dependencies():
    """Check if all required dependencies are installed"""
    required_modules = [
        'yt_dlp',
        'pyrogram', 
        'telethon',
        'motor',
        'pymongo',
        'aiohttp',
        'cryptography',
        'PIL',
        'cv2'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
            logger.info(f"✓ {module} - OK")
        except ImportError:
            missing_modules.append(module)
            logger.error(f"✗ {module} - MISSING")
    
    if missing_modules:
        logger.error(f"Missing required modules: {', '.join(missing_modules)}")
        logger.error("Please install missing dependencies with: pip install -r requirements.txt")
        return False
    
    return True

async def start_clients():
    """Start all clients with proper error handling"""
    try:
        from shared_client import start_client
        logger.info("Starting Telegram clients...")
        client_instances = await start_client()
        clients.extend(client_instances)
        logger.info("All clients started successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to start clients: {e}")
        return False

async def load_plugins():
    """Load plugins with error handling"""
    try:
        plugin_dir = Path("plugins")
        if not plugin_dir.exists():
            logger.warning("Plugins directory not found")
            return True
            
        plugins = [f.stem for f in plugin_dir.glob("*.py") if f.name != "__init__.py"]
        
        for plugin in plugins:
            try:
                module = importlib.import_module(f"plugins.{plugin}")
                logger.info(f"✓ Loaded plugin: {plugin}")
                
                # Run plugin if it has a run function
                if hasattr(module, f"run_{plugin}_plugin"):
                    await getattr(module, f"run_{plugin}_plugin")()
                    
            except Exception as e:
                logger.error(f"✗ Failed to load plugin {plugin}: {e}")
                continue
        
        return True
    except Exception as e:
        logger.error(f"Error loading plugins: {e}")
        return False

async def shutdown_clients():
    """Gracefully shutdown all clients"""
    logger.info("Shutting down clients...")
    
    for client in clients:
        try:
            if hasattr(client, 'stop'):
                await client.stop()
            elif hasattr(client, 'disconnect'):
                await client.disconnect()
        except Exception as e:
            logger.error(f"Error stopping client: {e}")
    
    # Cancel all remaining tasks
    tasks = [task for task in asyncio.all_tasks() if not task.done()]
    if tasks:
        logger.info(f"Cancelling {len(tasks)} remaining tasks...")
        for task in tasks:
            task.cancel()
        
        # Wait for tasks to complete cancellation
        await asyncio.gather(*tasks, return_exceptions=True)

async def main():
    """Main function with proper error handling and cleanup"""
    global running
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Check dependencies first
        logger.info("Checking dependencies...")
        if not await check_dependencies():
            logger.error("Dependency check failed. Exiting.")
            return 1
        
        # Start clients
        logger.info("Starting clients...")
        if not await start_clients():
            logger.error("Failed to start clients. Exiting.")
            return 1
        
        # Load plugins
        logger.info("Loading plugins...")
        if not await load_plugins():
            logger.warning("Some plugins failed to load, but continuing...")
        
        logger.info("🚀 Bot is running! Press Ctrl+C to stop.")
        
        # Keep the bot running
        while running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    finally:
        # Cleanup
        await shutdown_clients()
        logger.info("Shutdown complete")
    
    return 0

if __name__ == "__main__":
    try:
        # Run the main function
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
