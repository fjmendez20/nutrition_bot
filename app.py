from telegram.ext import ApplicationBuilder, ContextTypes
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request, jsonify
from threading import Thread
from waitress import serve
import asyncio

# Configuración avanzada de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
PORT = int(os.environ.get('PORT', 10000))

class BotManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialize()
        return cls._instance
    
    def initialize(self):
        """Inicialización segura del bot"""
        self.application = (
            ApplicationBuilder()
            .token(Config.TELEGRAM_TOKEN)
            .arbitrary_callback_data(True)
            .build()
        )
        
        # Configura handlers
        from handlers import setup_handlers
        setup_handlers(self.application)
        
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    async def setup_webhook(self):
        """Configura el webhook de manera robusta"""
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        try:
            await self.application.bot.set_webhook(
                url=webhook_url,
                secret_token=Config.WEBHOOK_SECRET,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
            logger.info(f"Webhook configurado correctamente en {webhook_url}")
            return True
        except Exception as e:
            logger.error(f"Error configurando webhook: {str(e)}")
            return False

    async def process_update(self, update_data):
        """Procesa una actualización de manera segura"""
        try:
            update = Update.de_json(update_data, self.application.bot)
            await self.application.process_update(update)
            return True
        except Exception as e:
            logger.error(f"Error procesando update: {str(e)}")
            return False

# Inicialización del bot
bot_manager = BotManager()

@app.route('/')
def home():
    return "¡Bot activo! Webhook configurado en /webhook"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint para actualizaciones de Telegram"""
    # Verificación de seguridad
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.WEBHOOK_SECRET:
        logger.warning("Intento de acceso no autorizado al webhook")
        return "Unauthorized", 401
    
    try:
        # Procesamiento en el event loop del bot
        success = bot_manager.loop.run_until_complete(
            bot_manager.process_update(request.get_json())
        )
        
        if not success:
            raise RuntimeError("Falló el procesamiento del update")
            
        return "ok", 200
    except Exception as e:
        logger.error(f"Error en webhook: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    """Endpoint para configurar el webhook manualmente"""
    try:
        success = bot_manager.loop.run_until_complete(
            bot_manager.setup_webhook()
        )
        return jsonify({"success": success}), 200 if success else 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_flask():
    """Inicia el servidor web"""
    logger.info(f"Iniciando servidor en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

def run_bot():
    """Mantiene vivo el event loop del bot"""
    logger.info("Bot iniciado y listo para recibir actualizaciones")
    bot_manager.loop.run_forever()

if __name__ == '__main__':
    # Configura el webhook al iniciar
    bot_manager.loop.run_until_complete(bot_manager.setup_webhook())
    
    # Inicia el bot en un hilo separado
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Inicia Flask en el hilo principal
    run_flask()