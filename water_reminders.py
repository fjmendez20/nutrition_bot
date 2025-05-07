from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from database import get_db_session, User, WaterLog, UserSettings
from keyboards import water_amount_keyboard, water_progress_keyboard, water_reminder_keyboard, weight_input_keyboard
from datetime import datetime, timedelta
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def reset_daily_water(context: CallbackContext):
    """Reinicia el contador de agua para todos los usuarios a medianoche"""
    db = get_db_session()
    try:
        users = db.query(User).filter(User.water_goal.isnot(None)).all()
        
        if not users:
            logger.info("No hay usuarios para reiniciar")
            return
            
        for user in users:
            try:
                # Verificar si el usuario tiene recordatorios activados
                settings = db.query(UserSettings).filter_by(user_id=user.id).first()
                if settings and not settings.water_reminders_enabled:
                    continue
                
                # Registrar el reset
                log = WaterLog(
                    user_id=user.id,
                    amount=user.current_water,
                    is_daily_reset=True,
                    timestamp=datetime.utcnow()
                )
                db.add(log)
                
                # Resetear contador
                user.current_water = 0
                user.last_water_reminder = None
                
                # Reiniciar recordatorios si están habilitados
                if settings and settings.water_reminders_enabled:
                    await restart_water_reminders(context, user.telegram_id)
                    
            except Exception as e:
                logger.error(f"Error reiniciando usuario {user.telegram_id}: {e}")
                continue
                
        db.commit()
        logger.info(f"Reinicio diario completado para {len(users)} usuarios")
        
    except Exception as e:
        logger.error(f"Error crítico en reset_daily_water: {e}")
        if db: db.rollback()
    finally:
        if db: db.close()

async def handle_register_weight(update: Update, context: CallbackContext):
    """Manejador para el botón de registro de peso"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['awaiting_weight'] = True
    await query.edit_message_text(
        "⚖️ *Registro de Peso* ⚖️\n\n"
        "Por favor ingresa tu peso actual en kilogramos (ejemplo: 68.5):\n\n"
        "⚠️ Solo el número, sin unidades o texto adicional.",
        reply_markup=weight_input_keyboard(),
        parse_mode='Markdown'
    )


                
async def check_user_registered(update: Update, context: CallbackContext) -> bool:
    """Verifica si el usuario está registrado y activo"""
    user = update.effective_user
    db = None
    try:
        db = get_db_session()
        user_record = db.query(User).filter_by(telegram_id=user.id).first()
        
        if not user_record:
            logger.warning(f"Usuario no registrado intentando acceder: {user.id}")
            await update.callback_query.answer(
                "⚠️ Debes registrarte primero con /start",
                show_alert=True
            )
            return False
        return True
    except Exception as e:
        logger.error(f"Error verificando registro: {e}")
        await update.callback_query.answer(
            "🔴 Error verificando tu registro. Intenta más tarde.",
            show_alert=True
        )
        return False
    finally:
        if db:
            db.close()


async def handle_weight_input(update: Update, context: CallbackContext):
    """Maneja la entrada del peso del usuario con validación mejorada"""
    if 'awaiting_weight' not in context.user_data:
        return  # No hacer nada si no estamos esperando un peso
    
    user_id = update.message.from_user.id
    db = None
    try:
        weight_str = update.message.text.replace(',', '.').strip()
        if not weight_str.replace('.', '').isdigit():
            raise ValueError("Formato inválido")
            
        weight = float(weight_str)
        if not (30 <= weight <= 300):
            raise ValueError("Peso fuera de rango")
            
        db = get_db_session()
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        if user:
            user.weight = weight
            user.water_goal = weight * 35
            user.current_water = 0
            db.commit()
            
            # Limpiar estado
            del context.user_data['awaiting_weight']
            
            await update.message.reply_text(
                f"✅ Peso actualizado: {weight} kg\n"
                f"💧 Nueva meta diaria: {user.water_goal:.0f} ml",
                reply_markup=water_progress_keyboard()
            )
            
            await restart_water_reminders(context, user_id)
            
    except ValueError:
        await update.message.reply_text(
            "⚠️ Formato inválido. Ingresa solo el número (ej: 68.5)",
            reply_markup=weight_input_keyboard()
        )
    except Exception as e:
        logger.error(f"Error registrando peso: {e}")
        await update.message.reply_text(
            "🔴 Error al registrar peso. Intenta más tarde.",
            reply_markup=weight_input_keyboard()
        )
    finally:
        if db:
            db.close()
            
async def restart_water_reminders(context: CallbackContext, user_id: int):
    """Reinicia los recordatorios considerando la configuración del usuario"""
    db = get_db_session()
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user or not user.water_goal:
            return
            
        settings = db.query(UserSettings).filter_by(user_id=user.id).first()
        
        # Cancelar jobs existentes
        for job in context.job_queue.get_jobs_by_name(f"water_reminder_{user_id}"):
            job.schedule_removal()
        
        # Programar nuevos recordatorios si están habilitados
        if not settings or settings.water_reminders_enabled:
            interval = settings.reminder_interval if settings else 60  # Default: 60 minutos
            
            context.job_queue.run_repeating(
                callback=send_water_reminder,
                interval=timedelta(minutes=interval),
                first=timedelta(seconds=3600),  # Primera notificación en 10 segundos
                chat_id=user_id,
                data={'user_id': user_id},
                name=f"water_reminder_{user_id}"
            )
            logger.info(f"Recordatorios programados para usuario {user_id} cada {interval} minutos")
    except Exception as e:
        logger.error(f"Error reiniciando recordatorios: {e}")
    finally:
        if db: db.close()


def calculate_water_goal(weight_kg: float) -> float:
    """Calcula la meta diaria de agua en ml (35ml por kg de peso)"""
    return weight_kg * 35

async def handle_water_reminder(update: Update, context: CallbackContext):
    """Manejador principal para recordatorios de agua"""
    query = update.callback_query
    await query.answer()
    
    if not await check_user_registered(update, context):
        return
        
    db = None
    try:
        db = get_db_session()
        user = db.query(User).filter_by(telegram_id=query.from_user.id).first()
        
        if not user or not user.weight:
            await handle_register_weight(update, context)
            return
    
        await show_water_progress(query, user)
    except Exception as e:
        logger.error(f"Error en handle_water_reminder: {e}")
        await query.edit_message_text(
            "⚠️ Error al procesar tu solicitud. Intenta nuevamente.",
            reply_markup=water_reminder_keyboard()
        )
    finally:
        if db:
            db.close()

async def handle_water_progress(update: Update, context: CallbackContext):
    """Muestra el progreso actual de hidratación"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_session()
    user = db.query(User).filter_by(telegram_id=query.from_user.id).first()
    
    if not user:
        await query.edit_message_text("❌ No se encontraron tus datos. Por favor, reinicia el bot.")
        return
    
    await show_water_progress(query, user)

async def show_water_progress(query, user: User):
    """Muestra el progreso con gráfica mejorada"""
    try:
        progress = min((user.current_water / user.water_goal) * 100, 100)
        progress_bar = "🟩" * int(progress / 10) + "⬜" * (10 - int(progress / 10))
        
        message = (
            "💧 *Progreso de Hidratación* 💧\n\n"
            f"🚰 Consumido hoy: `{user.current_water:.0f} ml`\n"
            f"🎯 Meta diaria: `{user.water_goal:.0f} ml`\n"
            f"📊 Progreso: `{progress:.1f}%`\n\n"
            f"{progress_bar}\n\n"
            f"⏱ Próximo recordatorio en 1 hora"
        )
        
        await query.edit_message_text(
            text=message,
            reply_markup=water_progress_keyboard(),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error mostrando progreso: {e}")
        await query.edit_message_text(
            "⚠️ Error mostrando progreso",
            reply_markup=water_progress_keyboard()
        )
    

async def handle_water_amount(update: Update, context: CallbackContext):
    """Registra el consumo de agua con validación mejorada"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_session()
    try:
        user = db.query(User).filter_by(telegram_id=query.from_user.id).first()
        if not user:
            await query.edit_message_text("❌ Usuario no encontrado")
            return
            
        if user.current_water >= user.water_goal:
            await query.edit_message_text(
                "🎉 ¡Ya alcanzaste tu meta diaria!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Menú principal", callback_data='main_menu')]
                ])
            )
            return
            
        amount = float(query.data.split('_')[-1])
        new_amount = min(user.current_water + amount, user.water_goal)
        added_amount = new_amount - user.current_water
        user.current_water = new_amount
        
        # Registrar el consumo
        log = WaterLog(
            user_id=user.id,
            amount=added_amount,
            timestamp=datetime.utcnow()
        )
        db.add(log)
        db.commit()
        
        if user.current_water >= user.water_goal:
            await query.edit_message_text(
                "🎉 ¡Meta alcanzada! ¡Buen trabajo!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Menú principal", callback_data='main_menu')]
                ])
            )
            # Cancelar recordatorios hasta mañana
            for job in context.job_queue.get_jobs_by_name(f"water_reminder_{user.telegram_id}"):
                job.schedule_removal()
        else:
            await show_water_progress(query, user)
            
    except Exception as e:
        logger.error(f"Error registrando agua: {e}")
        await query.edit_message_text(
            "⚠️ Error al registrar. Intenta nuevamente.",
            reply_markup=water_progress_keyboard()
        )
    finally:
        if db: db.close()

async def start_water_reminders(context: CallbackContext, user_id: int):
    """Configura los recordatorios periódicos con manejo robusto de errores"""
    try:
        if not hasattr(context, 'job_queue') or not context.job_queue:
            logger.error("JobQueue no disponible")
            raise RuntimeError("JobQueue no configurado")
        
        # Cancelar jobs existentes para este usuario
        current_jobs = context.job_queue.get_jobs_by_name(f"water_reminder_{user_id}")
        for job in current_jobs:
            job.schedule_removal()
        
        # Programar recordatorios horarios
        context.job_queue.run_repeating(
            callback=send_water_reminder,
            interval=3600,  # 1 hora
            first=3600,       # Primera ejecución en 10 segundos
            chat_id=user_id,
            data={'user_id': user_id},
            name=f"water_reminder_{user_id}"
        )
        
        # Programar reinicio diario a las 00:00 (si no existe ya)
        if not any(job.name == "daily_reset" for job in context.job_queue.jobs()):
            context.job_queue.run_daily(
                callback=reset_daily_water,
                time=datetime.strptime("09:00", "%H:%M").time(),
                name="daily_reset"
            )
        
        logger.info(f"Recordatorios configurados para usuario {user_id}")
        
    except Exception as e:
        logger.error(f"Error crítico al configurar recordatorios: {e}")
        raise

async def send_water_reminder(context: CallbackContext):
    """Envía recordatorios considerando la configuración del usuario"""
    job = context.job
    user_id = job.data['user_id']
    db = get_db_session()
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user or not user.water_goal:
            return
            
        settings = db.query(UserSettings).filter_by(user_id=user.id).first()
        
        # Verificar si los recordatorios están habilitados
        if settings and not settings.water_reminders_enabled:
            return
            
        # Verificar horario permitido
        now = datetime.now().time()
        if settings:
            start = datetime.strptime(settings.reminder_start_time, "%H:%M").time()
            end = datetime.strptime(settings.reminder_end_time, "%H:%M").time()
            if not (start <= now <= end):
                return
                
        # Verificar si ya alcanzó la meta
        if user.current_water >= user.water_goal:
            return
            
        await context.bot.send_message(
            chat_id=user_id,
            text="💧 ⏰ **Recordatorio de Hidratación** ⏰ 💧\n\n"
                 "Es hora de tomar agua para mantenerte hidratado/a!\n\n"
                 f"Progreso actual: {user.current_water:.0f}/{user.water_goal:.0f} ml",
            reply_markup=water_reminder_keyboard(),
            parse_mode='Markdown'
        )
        user.last_water_reminder = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"Error enviando recordatorio a {user_id}: {e}")
    finally:
        if db: db.close()
        
async def cancel_water_reminders(update: Update, context: CallbackContext):
    """Cancela recordatorios y actualiza la configuración"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_session()
    try:
        user = db.query(User).filter_by(telegram_id=query.from_user.id).first()
        if not user:
            await query.edit_message_text("❌ Usuario no encontrado")
            return
            
        settings = db.query(UserSettings).filter_by(user_id=user.id).first()
        if settings:
            settings.water_reminders_enabled = False
            db.commit()
            
        # Cancelar jobs
        jobs_removed = 0
        for job in context.job_queue.get_jobs_by_name(f"water_reminder_{user.telegram_id}"):
            job.schedule_removal()
            jobs_removed += 1
            
        message = "🔕 Recordatorios desactivados" if jobs_removed > 0 else "ℹ️ No tenías recordatorios activos"
        await query.edit_message_text(
            text=message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💧 Ver progreso", callback_data='water_progress')],
                [InlineKeyboardButton("🏠 Menú principal", callback_data='main_menu')]
            ])
        )
    except Exception as e:
        logger.error(f"Error cancelando recordatorios: {e}")
        await query.edit_message_text("⚠️ Error al desactivar recordatorios")
    finally:
        if db: db.close()
