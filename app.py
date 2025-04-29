from telegram.ext import ApplicationBuilder, ContextTypes
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request
from threading import Thread
from waitress import serve
import asyncio

# Configuración de logging avanzada
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
PORT = int(os.environ.get('PORT', 10000))

# Variable global para el Application
telegram_app = None

async def post_init(application):
    """Configuración posterior a la inicialización"""
    webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=Config.WEBHOOK_SECRET,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )
    logger.info(f"Webhook configurado en: {webhook_url}")

@app.route('/')
def home():
    return "¡Bot activo! El webhook está configurado."

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Endpoint para actualizaciones de Telegram"""
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.WEBHOOK_SECRET:
        logger.warning("Intento de acceso no autorizado al webhook")
        return "Unauthorized", 401

    try:
        json_data = request.get_json()
        update = Update.de_json(json_data, telegram_app.bot)
        
        # Procesamiento directo (mejor para Render)
        await telegram_app.process_update(update)
        return "ok", 200
    except Exception as e:
        logger.error(f"Error procesando update: {e}", exc_info=True)
        return "server error", 500

def run_bot():
    """Inicia el bot de Telegram"""
    global telegram_app
    
    telegram_app = (
        ApplicationBuilder()
        .token(Config.TELEGRAM_TOKEN)
        .post_init(post_init)
        .arbitrary_callback_data(True)
        .build()
    )
    
    # Configura handlers
    from handlers import setup_handlers
    setup_handlers(telegram_app)
    
    # Inicia el event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    logger.info("Bot iniciado y listo para recibir actualizaciones")
    loop.run_forever()

def run_flask():
    """Inicia el servidor web"""
    logger.info(f"Iniciando servidor en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    # Inicia el bot en un hilo separado
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Inicia Flask en el hilo principal
    run_flask()