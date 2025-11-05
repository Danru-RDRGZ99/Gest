# servicio_usuarios/models_usuarios.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String

class Base(DeclarativeBase):
    pass

class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    user: Mapped[str]   = mapped_column(String(80),  unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    rol: Mapped[str]    = mapped_column(String(20))

    def __repr__(self) -> str:
        return f"Usuario(id={self.id}, user={self.user}, rol={self.rol})"
