from telegram.ext import ApplicationBuilder
from config import Config
import logging
import asyncio
import os
from threading import Thread
from flask import Flask

# Configura Flask para mantener activo el servicio
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot activo con webhook!"

def run_flask():
    app.run(host='0.0.0.0', port=8081)

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    try:
        # Inicia Flask en segundo plano
        Thread(target=run_flask, daemon=True).start()

        # Construye la aplicación
        application = (
            ApplicationBuilder()
            .token(Config.TELEGRAM_TOKEN)
            .arbitrary_callback_data(True)
            .build()
        )
        
        # Registra handlers
        from handlers import setup_handlers
        setup_handlers(application)
        
        # Configura webhook
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        await application.bot.set_webhook(
            url=webhook_url,
            secret_token=Config.WEBHOOK_SECRET
        )
        logger.info(f"Webhook configurado: {webhook_url}")

        # Inicia el webhook
        await application.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", 8080)),
            webhook_url=webhook_url,
            secret_token=Config.WEBHOOK_SECRET
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot detenido")
    except Exception as e:
        logger.error(f"Error fatal: {e}")