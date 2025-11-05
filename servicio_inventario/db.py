import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Usa Railway Postgres si está seteado; si no, cae a SQLite local.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./inventario.db")

# Para SQLite en modo thread-safe
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.getenv("POOL_SIZE", "10")),
    max_overflow=int(os.getenv("MAX_OVERFLOW", "20")),
    pool_timeout=int(os.getenv("POOL_TIMEOUT", "10")),
    pool_recycle=int(os.getenv("POOL_RECYCLE", "600")),
    connect_args=connect_args,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
