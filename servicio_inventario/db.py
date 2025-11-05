# db.py del servicio INVENTARIO
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")  # tu cadena (Postgres/…)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # detecta conexiones muertas y las recicla
    pool_size=10,            # sube el pool base (antes 5)
    max_overflow=20,         # permite ráfagas
    pool_timeout=10,         # no bloquees 30s; falla antes si no hay conn
    pool_recycle=600,        # recicla para evitar timeouts del proveedor
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  # ¡IMPORTANTE! asegura retorno de la conexión a la pool
