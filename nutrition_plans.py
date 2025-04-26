import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from database import get_db_session, User, PlanDownload
from config import Config
from keyboards import nutrition_plans_keyboard, main_menu_keyboard
import requests
from io import BytesIO
from datetime import datetime

async def handle_nutrition_plan_selection(update: Update, context: CallbackContext):
    """Muestra el menú de selección de planes nutricionales"""
    query = update.callback_query
    await query.answer()  # Añadido await
    
    await query.edit_message_text(  # Añadido await
        "📚 Selecciona el tipo de plan nutricional que deseas:\n\n"
        "Cada plan está diseñado por expertos en nutrición para ayudarte a alcanzar tus metas.",
        reply_markup=nutrition_plans_keyboard()
    )

async def send_random_plan(update: Update, context: CallbackContext):
    """Envía un plan nutricional aleatorio según la categoría seleccionada"""
    query = update.callback_query
    await query.answer()  # Añadido await
    
    plan_type = query.data.split('_')[1]
    user_id = query.from_user.id
    
    db = get_db_session()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    
    if not user:
        await query.edit_message_text("Usuario no encontrado.")
        return
    
    # Verificar límite de descargas
    if not user.is_premium:
        downloads_today = db.query(PlanDownload).filter(
            PlanDownload.user_id == user.id,
            PlanDownload.downloaded_at >= datetime.utcnow().date()
        ).count()
        
        if downloads_today >= 3:
            await query.edit_message_text(  # Añadido await
                "⚠️ Has alcanzado tu límite de descargas gratuitas por hoy (3).\n\n"
                "Conviértete en usuario premium para descargar planes ilimitados.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌟 Hazte Premium", callback_data='premium')],
                    [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
                ])
            )
            return
    
    # Obtener PDF (simulado)
    try:
        pdf_url = "https://example.com/sample_plan.pdf"
        response = requests.get(pdf_url)
        pdf_file = BytesIO(response.content)
        
        # Registrar descarga
        db.add(PlanDownload(user_id=user.id, plan_type=plan_type))
        db.commit()
        
        # Enviar documento (no necesita await porque usa context.bot)
        await context.bot.send_document(
            chat_id=user_id,
            document=pdf_file,
            filename=f"plan_nutricional_{plan_type}.pdf",
            caption=f"📄 Aquí está tu plan de {plan_type.replace('_', ' ')}."
        )
        
        # Después de enviar el PDF:  
        mensajes_retorno = [  
            f"¡Listo, {user.first_name}! 📂\n\n"  
            "Tu plan nutricional ya está en tus manos. ¿Qué tal si lo revisamos juntos más tarde?\n\n"  
            "Por ahora, ¿en qué más puedo ayudarte?",  
            f"¡Perfecto, {user.first_name}! 💡\n\n"  
            "Ahora que tienes tu plan, recuerda:\n"  
            "• Pequeños pasos son grandes logros 🚶‍♂️💨\n"  
            "• Puedes ajustarlo según cómo te sientas\n\n"  
            "¿Quieres gestionar algo más hoy?" ,  
            f"¡Genial, {user.first_name}! 🌟\n\n"  
            "Espero que este plan te sea útil. Si tienes dudas o quieres compartir tu progreso, ¡aquí estoy!\n\n"  
            "¿Qué hacemos ahora?"   
        ]  

        await context.bot.send_message(  
            chat_id=user_id,  
            text=random.choice(mensajes_retorno),  
            reply_markup=main_menu_keyboard(),  
            parse_mode="HTML"  
        ) 
        
    except Exception as e:
        print(f"Error: {e}")
        await query.edit_message_text(
            "⚠️ Error al generar tu plan. Inténtalo más tarde.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
            ])
        )