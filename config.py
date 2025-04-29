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
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///nutrition_bot.db')
    
    # Configuración de pagos (Stripe, PayPal, etc.)
    STRIPE_API_KEY = os.getenv('STRIPE_API_KEY', '')
    PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID', '')
    
    # Google Drive (para los PDFs)
    GOOGLE_DRIVE_FOLDER_IDS = {
        'weight_loss': '18cYQJs4vGg1MxFSIMCsjL3mA-oRT-enR',
        'weight_gain': '1IGzHUejlRecVUPoumJG1yzcI5lwtul7q',
        'maintenance': '19qBf8nY5uEjq9pvPaXlCe4VwobdfZVo4',
        'sports': '1YXE-1d88E-AhBEPMcaGKft1jL81paLLD',
        'metabolic': '1xx3HONuEvSj4R7OsJMj8V3r5f-KET74B',
        'aesthetic': '1kpk9XN7n5vThzJ2ALchYIvRciE3WzwMu'
    }