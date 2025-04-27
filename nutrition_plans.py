import random
import os
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from database import get_db_session, User, PlanDownload
from keyboards import nutrition_plans_keyboard, main_menu_keyboard
from datetime import datetime

# Mapeo de tipos de plan a carpetas (ajusta estos nombres según tu estructura real)
PLAN_FOLDERS = {
    'weight_loss': 'weight_loss',
    'weight_gain': 'weight_gain',
    'maintenance': 'maintenance',
    'sports': 'sports',
    'metabolic': 'metabolic',
    'aesthetic': 'aesthetic'
}

async def handle_nutrition_plan_selection(update: Update, context: CallbackContext):
    """Muestra el menú de selección de planes nutricionales"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📚 Selecciona el tipo de plan nutricional que deseas:\n\n"
        "Cada plan está diseñado por expertos en nutrición para ayudarte a alcanzar tus metas.",
        reply_markup=nutrition_plans_keyboard()
    )

async def get_random_plan_file(plan_type):
    """Obtiene un archivo PDF aleatorio de la carpeta correspondiente"""
    folder_name = PLAN_FOLDERS.get(plan_type)
    if not folder_name:
        print(f"⚠️ Tipo de plan no reconocido: {plan_type}")
        return None
    
    folder_path = Path('static') / folder_name
    
    if not folder_path.exists():
        print(f"⚠️ Carpeta no encontrada: {folder_path.absolute()}")
        return None
    
    pdf_files = list(folder_path.glob('*.[pP][dD][fF]'))  # Busca PDFs insensible a mayúsculas
    
    if not pdf_files:
        print(f"⚠️ No se encontraron PDFs en: {folder_path}")
        return None
    
    return random.choice(pdf_files)

async def send_random_plan(update: Update, context: CallbackContext):
    """Envía un plan nutricional aleatorio según la categoría seleccionada"""
    query = update.callback_query
    await query.answer()
    
    plan_type = query.data.split('_')[1]
    user_id = query.from_user.id
    
    print(f"🔍 Buscando plan de tipo: {plan_type} para usuario: {user_id}")
    
    db = get_db_session()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    
    if not user:
        await query.edit_message_text("Usuario no encontrado.")
        return
    
    # Verificar límite de descargas para usuarios no premium
    if not user.is_premium:
        downloads_today = db.query(PlanDownload).filter(
            PlanDownload.user_id == user.id,
            PlanDownload.downloaded_at >= datetime.utcnow().date()
        ).count()
        
        if downloads_today >= 3:
            await query.edit_message_text(
                "⚠️ Has alcanzado tu límite de descargas gratuitas por hoy (3).\n\n"
                "Conviértete en usuario premium para descargar planes ilimitados.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌟 Hazte Premium", callback_data='premium')],
                    [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
                ])
            )
            return
    
    try:
        # Obtener archivo aleatorio
        plan_file = await get_random_plan_file(plan_type)
        
        if not plan_file:
            print(f"⚠️ No se encontró archivo PDF para {plan_type}")
            await query.edit_message_text(
                "⚠️ No hay planes disponibles en esta categoría en este momento.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
                ])
            )
            return
        
        print(f"📄 Archivo seleccionado: {plan_file}")
        
        # Registrar descarga
        db.add(PlanDownload(
            user_id=user.id,
            plan_type=plan_type,
            downloaded_at=datetime.utcnow()
        ))
        db.commit()
        
        # Enviar documento
        with open(plan_file, 'rb') as file:
            await context.bot.send_document(
                chat_id=user_id,
                document=file,
                filename=plan_file.name,
                caption=f"📄 Aquí está tu plan de {plan_type.replace('_', ' ')}."
            )
        
        # Mensajes de retorno al menú
        mensajes_retorno = [  
            f"¡Listo, {user.first_name}! 📂\n\n"  
            "Tu plan nutricional ya está en tus manos. ¿Qué tal si lo revisamos juntos más tarde?\n\n"  
            "Por ahora, ¿en qué más puedo ayudarte?",  
            f"¡Perfecto, {user.first_name}! 💡\n\n"  
            "Ahora que tienes tu plan, recuerda:\n"  
            "• Pequeños pasos son grandes logros 🚶‍♂️💨\n"  
            "• Puedes ajustarlo según cómo te sientas\n\n"  
            "¿Quieres gestionar algo más hoy?",  
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
        print(f"❌ Error al procesar el plan: {str(e)}")
        await query.edit_message_text(
            "⚠️ Error al generar tu plan. Inténtalo más tarde.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
            ])
        )