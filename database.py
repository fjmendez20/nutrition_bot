import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime
import logging
from typing import Optional

# Configuración básica de logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Obtener URL de la base de datos
DATABASE_URL = os.getenv('DATABASE_URL')

# Ajustar URL para SQLAlchemy (postgres:// → postgresql://)
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    weight = Column(Float)
    water_goal = Column(Float)  # en ml
    current_water = Column(Float, default=0)  # en ml
    is_premium = Column(Boolean, default=False)
    premium_expiry = Column(DateTime)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_water_reminder = Column(DateTime)

class WaterLog(Base):
    __tablename__ = 'water_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float)  # en ml
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_daily_reset = Column(Boolean, default=False)
    
class PlanDownload(Base):
    __tablename__ = 'plan_downloads'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    plan_type = Column(String)
    downloaded_at = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float)
    currency = Column(String, default='USD')
    payment_method = Column(String)
    transaction_id = Column(String)
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

# Configuración del motor de base de datos
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300
)

# Crear todas las tablas si no existen
if os.getenv('RESET_DB_ON_START', 'false').lower() == 'true':
    Base.metadata.drop_all(engine)  # ¡Borrará todas las tablas!
    print("⚠️ Base de datos reiniciada")

Base.metadata.create_all(engine)

# Configuración de la sesión
SessionFactory = sessionmaker(bind=engine)
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
    """Obtiene un usuario existente o crea uno nuevo"""
    db = get_db_session()
    try:
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                registered_at=datetime.utcnow()
            )
            db.add(user)
            db.commit()
            logger.info(f"Nuevo usuario creado: {telegram_id}")
        else:
            logger.info(f"Usuario existente encontrado: {telegram_id}")
        
        return user
    except Exception as e:
        logger.error(f"Error en get_or_create_user: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()