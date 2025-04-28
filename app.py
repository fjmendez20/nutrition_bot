from telegram.ext import ApplicationBuilder
from config import Config
import logging
import asyncio
import os
from threading import Thread
from flask import Flask, jsonify

# Configuración básica
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Mini servidor Flask para mantener activo el servicio
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot activo con webhook!"

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

def run_flask():
    app.run(host='0.0.0.0', port=8081)

async def run_bot():
    application = (
        ApplicationBuilder()
        .token(Config.TELEGRAM_TOKEN)
        .arbitrary_callback_data(True)
        .build()
    )
    
    from handlers import setup_handlers
    setup_handlers(application)
    
    webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=Config.WEBHOOK_SECRET
    )
    logger.info(f"Webhook configurado en: {webhook_url}")
    
    await application.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        secret_token=Config.WEBHOOK_SECRET
    )

def main():
    # Inicia Flask en segundo plano
    Thread(target=run_flask, daemon=True).start()
    
    # Configura el event loop correctamente
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.error(f"Error fatal: {e}")
    finally:
        loop.close()

if __name__ == '__main__':
    main()