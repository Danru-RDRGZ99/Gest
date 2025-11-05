# db.py (Inventario)
from starlette.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

config = Config(".env")
DATABASE_URL = config("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    pool_size=5,         # puedes subir a 8-10 si tu Postgres lo permite
    max_overflow=5,      # controla picos, evita colas largas
    pool_pre_ping=True,  # evita conexiones muertas
    pool_recycle=300,    # recicla antes de que el proxy cierre
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
