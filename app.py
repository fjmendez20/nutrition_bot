from telegram.ext import ApplicationBuilder
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request, jsonify
from waitress import serve
import asyncio
from telegram.request import HTTPXRequest
import threading

# Configuración inicial
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
PORT = int(os.environ.get('PORT', 10000))

class BotManager:
    def __init__(self):
        self.application = None
        self.loop = asyncio.new_event_loop()
        self.request = HTTPXRequest(
            connection_pool_size=20,
            read_timeout=20.0,
            write_timeout=20.0,
            connect_timeout=20.0,
            pool_timeout=30.0
        )
    
    def run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    async def _initialize(self):
        self.application = (
            ApplicationBuilder()
            .token(Config.TELEGRAM_TOKEN)
            .arbitrary_callback_data(True)
            .request(self.request)
            .build()
        )
        
        from handlers import setup_handlers
        setup_handlers(self.application)
        
        await self.application.initialize()
        await self.application.start()

    def initialize(self):
        self.run_async(self._initialize())

    async def _setup_webhook(self):
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        await self.application.bot.set_webhook(
            url=webhook_url,
            secret_token=Config.WEBHOOK_SECRET,
            allowed_updates=["message", "callback_query"]
        )

    def setup_webhook(self):
        self.run_async(self._setup_webhook())

    async def _process_update(self, update_data):
        update = Update.de_json(update_data, self.application.bot)
        await self.application.process_update(update)
        return True

    def process_update(self, update_data):
        try:
            return self.run_async(self._process_update(update_data))
        except Exception as e:
            logger.error(f"Error procesando update: {e}")
            return False

# Inicialización
bot_manager = BotManager()
bot_manager.initialize()
bot_manager.setup_webhook()

# Endpoints Flask (síncronos)
@app.post('/webhook')
def webhook():
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.WEBHOOK_SECRET:
        return "Unauthorized", 401
    
    update_data = request.get_json()
    success = bot_manager.process_update(update_data)
    return ("ok", 200) if success else ("error", 500)

def run():
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    run()