from telegram.ext import ApplicationBuilder, Application
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request, jsonify
import asyncio

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
PORT = int(os.environ.get('PORT', 8081))

# Inicialización del bot
application: Application = (
    ApplicationBuilder()
    .token(Config.TELEGRAM_TOKEN)
    .arbitrary_callback_data(True)
    .build()
)

# Handlers
from handlers import setup_handlers
setup_handlers(application)

@app.route('/')
def home():
    return "¡Bot activo! Ver /webhook_info para estado del webhook"

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Endpoint para actualizaciones de Telegram"""
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.WEBHOOK_SECRET:
        logger.warning("Intento de acceso no autorizado al webhook")
        return "Unauthorized", 401
        
    try:
        update = Update.de_json(await request.get_json(), application.bot)
        await application.process_update(update)
        return "ok", 200
    except Exception as e:
        logger.error(f"Error procesando update: {e}")
        return "server error", 500

@app.route('/webhook_info', methods=['GET'])
async def webhook_info():
    """Obtiene información del webhook actual"""
    try:
        info = await application.bot.get_webhook_info()
        return jsonify({
            "url": info.url,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message,
            "status": "active" if info.url else "inactive"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

async def setup():
    """Configuración inicial"""
    webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=Config.WEBHOOK_SECRET,
        drop_pending_updates=True
    )
    logger.info(f"Webhook configurado en: {webhook_url}")

def run_app():
    """Inicia la aplicación"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup())
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    run_app()