from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💧 Recordatorios de agua", callback_data='water_reminder')],
        [InlineKeyboardButton("🍎 Plan de nutrición", callback_data='nutrition_plans')],
        [InlineKeyboardButton("🌟 Premium", callback_data='premium')]
    ]
    return InlineKeyboardMarkup(keyboard)

def water_reminder_keyboard():
    keyboard = [
        [InlineKeyboardButton("💧 Registrar agua", callback_data='water_progress')],
        [InlineKeyboardButton("❌ Cancelar recordatorios", callback_data='cancel_water_reminders')],
        [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def water_amount_keyboard():
    keyboard = [
        [InlineKeyboardButton("250 ml", callback_data='water_amount_250')],
        [InlineKeyboardButton("500 ml", callback_data='water_amount_500')],
        [InlineKeyboardButton("750 ml", callback_data='water_amount_750')],
        [InlineKeyboardButton("🔙 Atrás", callback_data='water_reminder')]
    ]
    return InlineKeyboardMarkup(keyboard)

def water_progress_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ 250ml", callback_data='water_amount_250'),
         InlineKeyboardButton("➕ 500ml", callback_data='water_amount_500')],
        [InlineKeyboardButton("➕ 750ml", callback_data='water_amount_750')],
        [InlineKeyboardButton("⚖ Cambiar peso", callback_data='water_change_weight')],
        [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def nutrition_plans_keyboard():
    keyboard = [
        [InlineKeyboardButton("📉 Pérdida de peso", callback_data='plan_weight_loss')],
        [InlineKeyboardButton("📈 Aumento de peso/masa muscular", callback_data='plan_weight_gain')],
        [InlineKeyboardButton("⚖ Mantenimiento de peso", callback_data='plan_maintenance')],
        [InlineKeyboardButton("🏃 Mejora del rendimiento deportivo", callback_data='plan_sports')],
        [InlineKeyboardButton("❤ Salud metabólica", callback_data='plan_metabolic')],
        [InlineKeyboardButton("💪 Dietas para fines estéticos", callback_data='plan_aesthetic')],
        [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def premium_options_keyboard():
    keyboard = [
        [InlineKeyboardButton("💳 Tarjeta de crédito", callback_data='payment_credit_card')],
        [InlineKeyboardButton("📱 PayPal", callback_data='payment_paypal')],
        [InlineKeyboardButton("₿ Criptomonedas", callback_data='payment_crypto')],
        [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)