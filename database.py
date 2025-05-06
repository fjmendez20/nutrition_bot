import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime
import logging
from typing import Optional

# Importamos los modelos consolidados desde models.py
from models import Base, User, WaterLog, PlanDownload, Payment, UserSettings

# Configuración básica de logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Obtener URL de la base de datos
DATABASE_URL = os.getenv('DATABASE_URL')

# Ajustar URL para SQLAlchemy (postgres:// → postgresql://)
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Configuración del motor de base de datos
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False  # Cambiar a True para debug
)

# Crear todas las tablas si no existen
if os.getenv('RESET_DB_ON_START', 'false').lower() == 'true':
    Base.metadata.drop_all(engine)  # ¡Cuidado! Esto borrará todas las tablas
    logger.warning("⚠️ Base de datos reiniciada - TODAS LAS TABLAS ELIMINADAS")

Base.metadata.create_all(engine)

# Configuración de la sesión
SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Session = scoped_session(SessionFactory)

def get_db_session():
    """Obtiene una nueva sesión de base de datos con manejo seguro"""
    return Session()

def user_exists(telegram_id: int) -> bool:
    """Verifica si un usuario ya está registrado"""
    db = get_db_session()
    try:
        return db.query(User).filter_by(telegram_id=telegram_id).first() is not None
    except Exception as e:
        logger.error(f"Error en user_exists: {str(e)}")
        raise
    finally:
        db.close()

def get_or_create_user(telegram_id: int, 
                     username: Optional[str] = None, 
                     first_name: Optional[str] = None, 
                     last_name: Optional[str] = None) -> User:
    """Obtiene un usuario existente o crea uno nuevo con configuración inicial"""
    db = get_db_session()
    try:
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        
        if not user:
            # Crear nuevo usuario
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                registered_at=datetime.utcnow(),
                language='es'  # Valor por defecto
            )
            db.add(user)
            
            # Crear configuración inicial
            settings = UserSettings(
                user_id=user.id,
                water_reminders_enabled=True,
                reminder_start_time='08:00',
                reminder_end_time='22:00'
            )
            db.add(settings)
            
            db.commit()
            logger.info(f"Nuevo usuario creado: {telegram_id}")
        else:
            # Actualizar datos si es necesario
            update_needed = False
            if username and user.username != username:
                user.username = username
                update_needed = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                update_needed = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                update_needed = True
                
            if update_needed:
                db.commit()
                logger.info(f"Usuario actualizado: {telegram_id}")
            else:
                logger.info(f"Usuario existente encontrado: {telegram_id}")
        
        return user
    except Exception as e:
        logger.error(f"Error en get_or_create_user: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def get_user_settings(telegram_id: int) -> Optional[UserSettings]:
    """Obtiene la configuración de un usuario"""
    db = get_db_session()
    try:
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            return db.query(UserSettings).filter_by(user_id=user.id).first()
        return None
    except Exception as e:
        logger.error(f"Error en get_user_settings: {str(e)}")
        raise
    finally:
        db.close()

def reset_user_water(telegram_id: int) -> bool:
    """Resetea el contador de agua para un usuario y registra el evento"""
    db = get_db_session()
    try:
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return False
            
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
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Error en reset_user_water: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

def log_water_consumption(telegram_id: int, amount: float) -> bool:
    """Registra el consumo de agua para un usuario"""
    db = get_db_session()
    try:
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return False
            
        # Registrar consumo
        log = WaterLog(
            user_id=user.id,
            amount=amount,
            timestamp=datetime.utcnow()
        )
        db.add(log)
        
        # Actualizar contador
        user.current_water += amount
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Error en log_water_consumption: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()
