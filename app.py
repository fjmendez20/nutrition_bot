from telegram.ext import ApplicationBuilder
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request
from waitress import serve
import asyncio

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
        
    async def initialize(self):
        """Inicializa el bot con la misma configuración que tu versión polling"""
        if self.application is None:
            self.application = (
                ApplicationBuilder()
                .token(Config.TELEGRAM_TOKEN)
                .arbitrary_callback_data(True)  # Mantenemos tu configuración exacta
                .build()
            )
            
            # Importamos y configuramos los handlers como en tu versión polling
            from handlers import setup_handlers
            setup_handlers(self.application)
            
            await self.application.initialize()
            await self.application.start()
            logger.info("Bot inicializado correctamente (igual que en polling)")

    async def setup_webhook(self):
        """Configura el webhook manteniendo tu lógica de botones"""
        await self.initialize()
            
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        await self.application.bot.set_webhook(
            url=webhook_url,
            secret_token=Config.WEBHOOK_SECRET,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]  # Esencial para botones
        )
        logger.info(f"Webhook configurado en: {webhook_url}")

    async def process_update(self, update_data):
        """Procesa updates igual que en polling"""
        try:
            if self.application is None:
                await self.initialize()
            
            update = Update.de_json(update_data, self.application.bot)
            await self.application.process_update(update)
            return True
            
        except Exception as e:
            logger.error(f"Error procesando update: {str(e)}", exc_info=True)
            logger.error(f"Datos del update recibido: {update_data}")
            return False

# Instancia global del bot (igual que en tu webhook original)
bot_manager = BotManager()

# Flask endpoints (igual que antes)
@app.route('/')
def home():
    return "¡Bot activo! Webhook configurado en /webhook"

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Endpoint para actualizaciones, compatible con tus botones"""
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.WEBHOOK_SECRET:
        logger.warning("Intento de acceso no autorizado al webhook")
        return "Unauthorized", 401
    
    try:
        update_data = request.get_json()
        logger.info(f"Update recibido: {update_data}")
        
        # Procesamiento directo (sin colas) manteniendo tu lógica
        success = await bot_manager.process_update(update_data)
        return "ok" if success else "error", 200
        
    except Exception as e:
        logger.error(f"Error en webhook: {str(e)}", exc_info=True)
        return "server error", 500

@app.route('/webhook_status', methods=['GET'])
async def webhook_status():
    """Verifica estado del webhook"""
    if bot_manager.application is None:
        return {"status": "Bot no inicializado"}, 503
    
    info = await bot_manager.application.bot.get_webhook_info()
    return {
        'url': info.url,
        'pending_updates': info.pending_update_count,
        'last_error': info.last_error_message
    }

def run_flask():
    """Inicia el servidor web"""
    logger.info(f"Iniciando servidor en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

async def startup():
    """Configuración inicial idéntica a tu lógica"""
    await bot_manager.setup_webhook()

if __name__ == '__main__':
    # Inicialización como en tu versión original
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(startup())
    
    # Iniciar Flask (igual que antes)
    run_flask()