from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    """Teclado principal del bot"""
    keyboard = [
        [InlineKeyboardButton("💧 Recordatorios de Agua", callback_data='water_reminder')],
        [InlineKeyboardButton("🍎 Plan Nutricional", callback_data='nutrition_plans')],
        [InlineKeyboardButton("🌟 Premium", callback_data='premium')]
    ]
    return InlineKeyboardMarkup(keyboard)

def water_reminder_keyboard():
    """Teclado para gestión de recordatorios de agua"""
    keyboard = [
        [InlineKeyboardButton("💧 Registrar Consumo", callback_data='water_progress')],
        [InlineKeyboardButton("⚖ Registrar Peso", callback_data='register_weight')],  # Cambiado a register_weight
        [InlineKeyboardButton("🔕 Cancelar Recordatorios", callback_data='cancel_water_reminders')],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def water_amount_keyboard():
    """Teclado para seleccionar cantidad de agua consumida"""
    keyboard = [
        [
            InlineKeyboardButton("250 ml", callback_data='water_amount_250'),
            InlineKeyboardButton("500 ml", callback_data='water_amount_500')
        ],
        [
            InlineKeyboardButton("750 ml", callback_data='water_amount_750'),
            InlineKeyboardButton("1 L", callback_data='water_amount_1000')
        ],
        [InlineKeyboardButton("🔙 Atrás", callback_data='water_reminder')]
    ]
    return InlineKeyboardMarkup(keyboard)

def water_progress_keyboard():
    """Teclado para mostrar progreso de hidratación"""
    keyboard = [
        [
            InlineKeyboardButton("➕ 250ml", callback_data='water_amount_250'),
            InlineKeyboardButton("➕ 500ml", callback_data='water_amount_500')
        ],
        [
            InlineKeyboardButton("➕ 750ml", callback_data='water_amount_750'),
            InlineKeyboardButton("➕ 1L", callback_data='water_amount_1000')
        ],
        [InlineKeyboardButton("⚖ Actualizar Peso", callback_data='register_weight')],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def nutrition_plans_keyboard():
    """Teclado para selección de planes nutricionales"""
    keyboard = [
        [InlineKeyboardButton("📉 Pérdida de Peso", callback_data='plan_weight_loss')],
        [InlineKeyboardButton("📈 Aumento Muscular", callback_data='plan_weight_gain')],
        [InlineKeyboardButton("⚖ Mantenimiento", callback_data='plan_maintenance')],
        [InlineKeyboardButton("🏃 Rendimiento Deportivo", callback_data='plan_sports')],
        [InlineKeyboardButton("❤ Salud Metabólica", callback_data='plan_metabolic')],
        [InlineKeyboardButton("💪 Objetivos Estéticos", callback_data='plan_aesthetic')],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def premium_options_keyboard():
    """Teclado para opciones premium"""
    keyboard = [
        [InlineKeyboardButton("💳 Tarjeta de Crédito", callback_data='payment_credit_card')],
        [InlineKeyboardButton("📱 PayPal", callback_data='payment_paypal')],
        [InlineKeyboardButton("₿ Criptomonedas", callback_data='payment_crypto')],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def weight_input_keyboard():
    """Teclado para cancelar entrada de peso"""
    keyboard = [
        [InlineKeyboardButton("❌ Cancelar", callback_data='water_reminder')]
    ]
    return InlineKeyboardMarkup(keyboard)