import random
from telegram import Update
from telegram.ext import CallbackContext
from database import get_db_session, User, PlanDownload
from config import Config
from keyboards import nutrition_plans_keyboard
import requests
from io import BytesIO

def handle_nutrition_plan_selection(update: Update, context: CallbackContext):
    """Muestra el menú de selección de planes nutricionales"""
    query = update.callback_query
    query.answer()
    
    query.edit_message_text(
        "📚 Selecciona el tipo de plan nutricional que deseas:\n\n"
        "Cada plan está diseñado por expertos en nutrición para ayudarte a alcanzar tus metas.",
        reply_markup=nutrition_plans_keyboard()
    )

def send_random_plan(update: Update, context: CallbackContext):
    """Envía un plan nutricional aleatorio según la categoría seleccionada"""
    query = update.callback_query
    query.answer()
    
    plan_type = query.data.split('_')[1]
    user_id = query.from_user.id
    
    db = get_db_session()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    
    # Verificar límite de descargas para usuarios no premium
    if not user.is_premium:
        downloads_today = db.query(PlanDownload).filter(
            PlanDownload.user_id == user.id,
            PlanDownload.downloaded_at >= datetime.utcnow().date()
        ).count()
        
        if downloads_today >= 3:
            query.edit_message_text(
                "⚠️ Has alcanzado tu límite de descargas gratuitas por hoy (3).\n\n"
                "Conviértete en usuario premium para descargar planes ilimitados y acceder a beneficios exclusivos.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌟 Hazte Premium", callback_data='premium')],
                    [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
                ])
            )
            return
    
    # Obtener un PDF aleatorio de la carpeta de Google Drive
    folder_id = Config.GOOGLE_DRIVE_FOLDER_IDS.get(plan_type)
    if not folder_id:
        query.edit_message_text(
            "⚠️ Lo sentimos, no hay planes disponibles en esta categoría en este momento.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]])
        )
        return
    
    # Simular obtención de un PDF aleatorio de Drive
    # En una implementación real, usarías la API de Google Drive
    try:
        # Aquí iría la lógica para obtener un archivo aleatorio de la carpeta de Drive
        # Por ahora simulamos con un PDF de ejemplo
        pdf_url = "https://example.com/sample_plan.pdf"  # URL simulada
        response = requests.get(pdf_url)
        pdf_file = BytesIO(response.content)
        
        # Registrar la descarga
        db.add(PlanDownload(
            user_id=user.id,
            plan_type=plan_type
        ))
        db.commit()
        
        # Enviar el PDF
        context.bot.send_document(
            chat_id=user_id,
            document=pdf_file,
            filename=f"plan_nutricional_{plan_type}.pdf",
            caption=f"📄 Aquí está tu plan de {plan_type.replace('_', ' ')}.\n\n"
                    f"Recuerda que puedes descargar hasta 3 planes por día. "
                    f"¡Hazte premium para acceder a descargas ilimitadas!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌟 Hazte Premium", callback_data='premium')],
                [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
            ])
        )
    except Exception as e:
        print(f"Error al enviar el plan: {e}")
        query.edit_message_text(
            "⚠️ Ocurrió un error al generar tu plan. Por favor, inténtalo de nuevo más tarde.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]])
        )