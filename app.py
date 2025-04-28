from telegram.ext import ApplicationBuilder
from config import Config
import logging
import asyncio
import os

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def setup_webhook(application):
    """Configura el webhook en Telegram"""
    webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
    secret_token = Config.WEBHOOK_SECRET  # Añade esto a tu config.py
    
    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=secret_token,
        drop_pending_updates=True
    )
    logger.info(f"Webhook configurado en: {webhook_url}")

async def main():
    try:
        # Construye la aplicación
        application = (
            ApplicationBuilder()
            .token(Config.TELEGRAM_TOKEN)
            .arbitrary_callback_data(True)
            .updater(None)  # Importante: desactiva el polling
            .build()
        )
        
        # Registra los handlers
        from handlers import setup_handlers
        setup_handlers(application)
        
        # Configura el webhook
        await setup_webhook(application)
        
        # Inicia el servidor webhook
        await application.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", 8080)),  # Render usa el puerto 8080
            secret_token=Config.WEBHOOK_SECRET,
            webhook_url=f"https://{Config.RENDER_DOMAIN}/webhook"
        )
        
    except Exception as e:
        logger.error(f"Error crítico: {e}")
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.error(f"Error fatal: {e}")