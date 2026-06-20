import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Cargamos las variables de entorno desde el archivo .env
load_dotenv()

# URL de conexión corregida con tus datos reales por defecto si falla el .env
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:root11a@localhost:3306/agrotech_db")

# El engine es el encargado de administrar los sockets de conexión a MySQL
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verifica si la conexión sigue viva antes de usarla
    pool_recycle=3600    # Recicla conexiones para evitar errores de desconexión
)

# Cada petición de la API tendrá su propia sesión independiente en la BD
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Esta clase base la usarán nuestros modelos de Python para mapearse con las tablas de MySQL
Base = declarative_base()

# Dependencia profesional para inyectar la sesión de la BD en los routers
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  # Nos aseguramos de CERRAR la conexión al terminar la petición HTTP