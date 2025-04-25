import os
from dotenv import load_dotenv

load_dotenv()  # Carga las variables del archivo .env

class Config:
    # Token de tu bot de Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    
    # URL para el webhook (debes configurar esto en tu servidor)
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://tudominio.com/webhook')
    
    # Configuración de la base de datos
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///nutrition_bot.db')
    
    # Configuración de pagos (Stripe, PayPal, etc.)
    STRIPE_API_KEY = os.getenv('STRIPE_API_KEY', '')
    PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID', '')
    
    # Google Drive (para los PDFs)
    GOOGLE_DRIVE_FOLDER_IDS = {
        'weight_loss': 'ID_CARPETA_DRIVE',
        'weight_gain': 'ID_CARPETA_DRIVE',
        'maintenance': 'ID_CARPETA_DRIVE',
        'sports': 'ID_CARPETA_DRIVE',
        'metabolic': 'ID_CARPETA_DRIVE',
        'aesthetic': 'ID_CARPETA_DRIVE'
    }