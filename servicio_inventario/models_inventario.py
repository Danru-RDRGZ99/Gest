from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Text,
    CheckConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Definimos una nueva Base para este servicio
class Base(DeclarativeBase):
    pass

# ============================
# MODELO "LEÍDO" (Read-only)
# (Copiado para que la relación de 'Prestamo' funcione)
# ============================

class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    user: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    rol: Mapped[str] = mapped_column(String(20))
    
    # La relación inversa (necesaria para `Prestamo.usuario`)
    prestamos: Mapped[List["Prestamo"]] = relationship(back_populates="usuario")

# ============================
# MODELOS "PROPIOS" (Owned)
# (Este servicio escribe en estas tablas)
# ============================

class Plantel(Base):
    __tablename__ = "planteles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    direccion: Mapped[str] = mapped_column(String(200))

    laboratorios: Mapped[List["Laboratorio"]] = relationship(
        back_populates="plantel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

class Laboratorio(Base):
    __tablename__ = "laboratorios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    ubicacion: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    capacidad: Mapped[int] = mapped_column(Integer, default=0)
    plantel_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("planteles.id", ondelete="SET NULL"), nullable=True, index=True
    )

    plantel: Mapped[Optional[Plantel]] = relationship(back_populates="laboratorios")
    recursos: Mapped[List["Recurso"]] = relationship(
        back_populates="laboratorio",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

class Recurso(Base):
    __tablename__ = "recursos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    laboratorio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("laboratorios.id", ondelete="RESTRICT"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(80))
    estado: Mapped[str] = mapped_column(String(40))
    specs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    laboratorio: Mapped[Laboratorio] = relationship(back_populates="recursos")
    prestamos: Mapped[List["Prestamo"]] = relationship(
        back_populates="recurso",
    )

class Prestamo(Base):
    __tablename__ = "prestamos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recurso_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recursos.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    solicitante: Mapped[str] = mapped_column(String(120), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(String(40), nullable=False, default="pendiente", index=True)
    comentario: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("cantidad >= 1", name="ck_prestamos_cantidad_pos"),
    )

    recurso: Mapped[Recurso] = relationship(back_populates="prestamos", lazy="joined")
    usuario: Mapped[Usuario] = relationship(back_populates="prestamos", lazy="joined")