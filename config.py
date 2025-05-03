import os
from dotenv import load_dotenv

load_dotenv()  # Carga las variables del archivo .env

class Config:
    # Token de tu bot de Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET') # Ej: "A1B2-C3D4-E5F6"
    RENDER_DOMAIN = os.getenv('RENDER_DOMAIN')  # Tu dominio en Render
    # URL para el webhook (debes configurar esto en tu servidor)
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://nutrition-bot-y646.onrender.com/')
    
    # Configuración de la base de datos
    DATABASE_URL = os.getenv('DATABASE_URL', 'DATABASE_URL')
    
    # Configuración de pagos (Stripe, PayPal, etc.)
    STRIPE_API_KEY = os.getenv('STRIPE_API_KEY', '')
    PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID', '')
    
    # Mega (para los PDFs)    
    MEGA_EMAIL = os.getenv('MEGA_EMAIL', 'MEGA_EMAIL')
    MEGA_PASSWORD = os.getenv('MEGA_PASSWORD', 'MEGA_PASSWORD')