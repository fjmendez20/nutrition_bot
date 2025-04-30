from telegram.ext import ApplicationBuilder
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request, jsonify
import asyncio
from telegram.request import HTTPXRequest
import threading
import time

# Configuración básica
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
            connection_pool_size=20,
            read_timeout=30.0,
            write_timeout=30.0,
            connect_timeout=30.0,
            pool_timeout=60.0
        )
        self._start_background_loop()

    def _start_background_loop(self):
        threading.Thread(
            target=self._run_event_loop,
            daemon=True,
            name='BotManagerLoop'
        ).start()

    def _run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _initialize(self):
        self.application = (
            ApplicationBuilder()
            .token(Config.TELEGRAM_TOKEN)
            .arbitrary_callback_data(False)
            .request(self.request)
            .build()
        )
        
        from handlers import setup_handlers
        setup_handlers(self.application)
        
        await self.application.initialize()
        await self.application.start()
        logger.info("Bot inicializado correctamente")

    def initialize(self):
        future = asyncio.run_coroutine_threadsafe(
            self._initialize(),
            self.loop
        )
        future.result()  # Espera a que termine

    async def _setup_webhook(self):
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        await self.application.bot.delete_webhook()
        await self.application.bot.set_webhook(
            url=webhook_url,
            secret_token=Config.WEBHOOK_SECRET,
            allowed_updates=["message", "callback_query"],
            max_connections=20
        )
        logger.info(f"Webhook configurado en: {webhook_url}")

    def setup_webhook(self):
        future = asyncio.run_coroutine_threadsafe(
            self._setup_webhook(),
            self.loop
        )
        future.result()

    async def _process_update(self, update_data):
        update = Update.de_json(update_data, self.application.bot)
        await self.application.process_update(update)
        return True

    def process_update(self, update_data):
        future = asyncio.run_coroutine_threadsafe(
            self._process_update(update_data),
            self.loop
        )
        return future.result()

# Inicialización del bot
bot_manager = BotManager()
bot_manager.initialize()
bot_manager.setup_webhook()

# Endpoints Flask
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

@app.get('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

# Inicio del servidor
def run_server():
    from waitress import serve
    logger.info(f"Iniciando servidor en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT, threads=4)

if __name__ == '__main__':
    run_server()