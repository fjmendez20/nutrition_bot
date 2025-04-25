from telegram.ext import ApplicationBuilder  # Cambia esto
from config import Config
from threading import Thread
import logging
import asyncio

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    try:
        application = (
        ApplicationBuilder()
        .token(Config.TELEGRAM_TOKEN)
        .arbitrary_callback_data(True)  # Opcional pero recomendado
        .build()
    )
        
        from handlers import setup_handlers
        setup_handlers(application)
        
        logger.info("Starting bot in polling mode...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info("Bot is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        if 'application' in locals():
            await application.updater.stop()
            await application.stop()
            await application.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        
    #if Config.WEBHOOK_URL:
    #    await application.run_webhook(
    #        listen='0.0.0.0',
    #        port=8443,
    #        url_path=Config.TELEGRAM_TOKEN,
    #        webhook_url=f"{Config.WEBHOOK_URL}/{Config.TELEGRAM_TOKEN}",
    #        cert='cert.pem'  # Necesario para HTTPS
    #    )
    #    logger.info("Bot running in webhook mode")
    #else:
    #    await application.run_polling()
    #    logger.info("Bot running in polling mode")

