from telegram.ext import ApplicationBuilder
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request, jsonify
import asyncio
from telegram.request import HTTPXRequest
import httpx
import threading

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
PORT = int(os.environ.get('PORT', 10000))

class BotManager:
    def __init__(self):
        self.application = None
        self.loop = asyncio.new_event_loop()
        self.request = HTTPXRequest(
            connection_pool_size=30,
            read_timeout=30.0,
            write_timeout=30.0,
            connect_timeout=30.0,
            pool_timeout=60.0,
            http_version="1.1"
        )
    
    async def _initialize(self):
        self.application = (
            ApplicationBuilder()
            .token(Config.TELEGRAM_TOKEN)
            .request(self.request)
            .post_init(self.post_init)
            .build()
        )
        
        from handlers import setup_handlers
        setup_handlers(self.application)
        
        await self.application.initialize()
        await self.application.start()
        logger.info("Bot inicializado correctamente")

    def initialize(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._initialize())

    async def post_init(self, application):
        logger.info("Handlers registrados:")
        for handler in application.handlers[0]:
            logger.info(f"- {type(handler).__name__}: {getattr(handler, 'pattern', 'N/A')}")

    async def _setup_webhook(self):
        await self.initialize()
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        
        await self.application.bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)
        
        await self.application.bot.set_webhook(
            url=webhook_url,
            secret_token=Config.WEBHOOK_SECRET,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            max_connections=30
        )
        logger.info(f"Webhook configurado: {webhook_url}")

    def setup_webhook(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._setup_webhook())

    async def _process_update(self, update_data):
        try:
            update = Update.de_json(update_data, self.application.bot)
            if update.callback_query:
                logger.info(f"Procesando callback: {update.callback_query.data}")
            await self.application.process_update(update)
            return True
        except Exception as e:
            logger.error(f"Error procesando update: {str(e)}", exc_info=True)
            return False

    def process_update(self, update_data):
        asyncio.set_event_loop(self.loop)
        return self.loop.run_until_complete(self._process_update(update_data))

bot_manager = BotManager()
bot_manager.initialize()  # Inicialización temprana

@app.route('/')
def home():
    return "¡Bot activo! Webhook configurado en /webhook"

@app.post('/webhook')
def webhook():
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.WEBHOOK_SECRET:
        return "Unauthorized", 401
    
    try:
        update_data = request.get_json()
        logger.info(f"Update recibido (type: {update_data.get('update_id')})")
        success = bot_manager.process_update(update_data)
        return "ok" if success else "error", 200
    except Exception as e:
        logger.error(f"Error en webhook: {str(e)}", exc_info=True)
        return "server error", 500

@app.get('/webhook_status')
def webhook_status():
    if bot_manager.application is None:
        return jsonify({"status": "Bot no inicializado"}), 503
    
    info = asyncio.run_coroutine_threadsafe(
        bot_manager.application.bot.get_webhook_info(),
        bot_manager.loop
    ).result()
    
    return jsonify({
        'url': info.url,
        'pending_updates': info.pending_update_count,
        'last_error': info.last_error_message,
        'last_error_date': str(info.last_error_date)
    })

def run_flask():
    from waitress import serve
    logger.info(f"Iniciando servidor en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    bot_manager.setup_webhook()
    run_flask()