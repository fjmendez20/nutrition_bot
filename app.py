from telegram.ext import ApplicationBuilder
from config import Config
import logging
import asyncio
import os
import signal

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotRunner:
    def __init__(self):
        self.application = None
        self.loop = asyncio.new_event_loop()

    async def setup(self):
        """Configuración inicial del bot"""
        self.application = (
            ApplicationBuilder()
            .token(Config.TELEGRAM_TOKEN)
            .arbitrary_callback_data(True)
            .build()
        )
        
        from handlers import setup_handlers
        setup_handlers(self.application)

    async def configure_webhook(self):
        """Configura el webhook en Telegram"""
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        await self.application.bot.set_webhook(
            url=webhook_url,
            secret_token=Config.WEBHOOK_SECRET,
            drop_pending_updates=True
        )
        logger.info(f"Webhook configurado en: {webhook_url}")

    def handle_shutdown(self, signum, frame):
        """Maneja la señal de apagado"""
        logger.info("Recibida señal de apagado, deteniendo el bot...")
        self.loop.create_task(self.shutdown())

    async def shutdown(self):
        """Apagado limpio"""
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
        self.loop.stop()

    def run(self):
        """Punto de entrada principal"""
        try:
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.setup())
            self.loop.run_until_complete(self.configure_webhook())
            
            # Configura señales para apagado limpio
            signal.signal(signal.SIGINT, self.handle_shutdown)
            signal.signal(signal.SIGTERM, self.handle_shutdown)
            
            # Inicia el webhook
            self.loop.run_until_complete(
                self.application.run_webhook(
                    listen="0.0.0.0",
                    port=int(os.getenv("PORT", 8080)),
                    secret_token=Config.WEBHOOK_SECRET,
                    webhook_url=f"https://{Config.RENDER_DOMAIN}/webhook"
                )
            )
            
            # Mantiene el bot corriendo
            self.loop.run_forever()
            
        except Exception as e:
            logger.error(f"Error fatal: {e}")
        finally:
            self.loop.close()

if __name__ == '__main__':
    bot = BotRunner()
    bot.run()