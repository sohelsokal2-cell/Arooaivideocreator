import asyncio
import logging
import uvicorn
from app.config import PORT, TELEGRAM_BOT_TOKEN
from app.bot import create_bot_app
from app.web_server import app as web_app

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def run_services():
    """Runs the FastAPI health-check server and Telegram Bot concurrently."""
    bot_app = None
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "your_telegram_bot_token_here":
        try:
            bot_app = create_bot_app()
            await bot_app.initialize()
            await bot_app.start()
            if bot_app.updater:
                await bot_app.updater.start_polling()
            logger.info("Telegram Bot started polling successfully!")
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot polling: {e}")
    else:
        logger.warning("No TELEGRAM_BOT_TOKEN provided. Running in Web-Only mode for Render healthchecks.")

    # Run Uvicorn server for Render
    config = uvicorn.Config(app=web_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

    if bot_app and bot_app.updater:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()

if __name__ == "__main__":
    asyncio.run(run_services())

