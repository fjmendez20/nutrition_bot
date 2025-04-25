from telegram import Update
from telegram.ext import CallbackContext
from database import get_db_session, User, Payment
from keyboards import premium_options_keyboard
from datetime import datetime, timedelta
import stripe
from config import Config

stripe.api_key = Config.STRIPE_API_KEY

def handle_premium_payment(update: Update, context: CallbackContext):
    """Muestra las opciones de pago para premium"""
    query = update.callback_query
    query.answer()
    
    query.edit_message_text(
        "🌟 ¡Conviértete en usuario Premium! 🌟\n\n"
        "Beneficios:\n"
        "✅ Descargas ilimitadas de planes nutricionales\n"
        "✅ Acceso a contenido exclusivo\n"
        "✅ Soporte prioritario\n\n"
        "Precio: $9.99 USD/mes\n\n"
        "Selecciona tu método de pago:",
        reply_markup=premium_options_keyboard()
    )

def create_stripe_payment_link(user_id: int):
    """Crea un enlace de pago con Stripe"""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'NutriBot Premium',
                    },
                    'unit_amount': 999,  # $9.99 USD
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f'https://t.me/nutribot?start=payment_success_{user_id}',
            cancel_url='https://t.me/nutribot?start=payment_cancel',
            metadata={'user_id': user_id}
        )
        return session.url
    except Exception as e:
        print(f"Error al crear sesión de Stripe: {e}")
        return None

def handle_payment_method(update: Update, context: CallbackContext):
    """Maneja la selección del método de pago"""
    query = update.callback_query
    query.answer()
    payment_method = query.data.split('_')[1]
    user_id = query.from_user.id
    
    if payment_method == 'credit_card':
        payment_url = create_stripe_payment_link(user_id)
        if payment_url:
            query.edit_message_text(
                "💳 Pago con tarjeta de crédito\n\n"
                "Haz clic en el siguiente enlace para completar tu pago seguro con Stripe:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Pagar con Stripe", url=payment_url)],
                    [InlineKeyboardButton("🔙 Atrás", callback_data='premium')]
                ])
            )
        else:
            query.edit_message_text(
                "⚠️ Error al procesar el pago. Por favor, inténtalo de nuevo más tarde.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]])
            )
    
    elif payment_method == 'paypal':
        # Implementar lógica de PayPal similar
        pass
    
    elif payment_method == 'crypto':
        # Implementar lógica de criptomonedas
        pass

def process_payment_success(user_id: int):
    """Actualiza el estado del usuario a premium después de un pago exitoso"""
    db = get_db_session()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    
    if user:
        user.is_premium = True
        user.premium_expiry = datetime.utcnow() + timedelta(days=30)  # 1 mes
        db.commit()
        
        # Registrar el pago
        db.add(Payment(
            user_id=user.id,
            amount=9.99,
            payment_method='stripe',
            status='completed',
            completed_at=datetime.utcnow()
        ))
        db.commit()
        
        return True
    return False