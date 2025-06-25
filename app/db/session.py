from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Crear el motor de SQLAlchemy
# pool_pre_ping habilita una comprobación de conexión antes de usarla del pool
engine = create_engine(str(settings.DATABASE_URI), pool_pre_ping=True)

# Crear una fábrica de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Función de dependencia para obtener una sesión de DB en las rutas
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
