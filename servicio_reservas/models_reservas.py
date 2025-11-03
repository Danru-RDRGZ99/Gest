from __future__ import annotations
from datetime import datetime, time, date
from typing import List, Optional
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Text,
    Time, Date, Boolean, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Definimos una nueva Base para este servicio
class Base(DeclarativeBase):
    pass

# ============================
# MODELOS "LEÍDOS" (Read-only)
# (Copiados para que las relaciones de 'Reserva' funcionen)
# ============================

class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    user: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    rol: Mapped[str] = mapped_column(String(20))
    
    # La relación inversa (necesaria para `Reserva.usuario`)
    reservas: Mapped[List["Reserva"]] = relationship(back_populates="usuario")

class Plantel(Base):
    __tablename__ = "planteles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    direccion: Mapped[str] = mapped_column(String(200))
    laboratorios: Mapped[List["Laboratorio"]] = relationship(back_populates="plantel")

class Laboratorio(Base):
    __tablename__ = "laboratorios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    ubicacion: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    capacidad: Mapped[int] = mapped_column(Integer, default=0)
    plantel_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("planteles.id"), nullable=True, index=True)

    plantel: Mapped[Optional[Plantel]] = relationship(back_populates="laboratorios")
    
    # Relaciones inversas (necesarias)
    reservas: Mapped[List["Reserva"]] = relationship(back_populates="laboratorio")
    reglas_horario: Mapped[List["ReglaHorario"]] = relationship(back_populates="laboratorio")
    excepciones_horario: Mapped[List["ExcepcionHorario"]] = relationship(back_populates="laboratorio")

# ============================
# MODELOS "PROPIOS" (Owned)
# (Este servicio escribe en estas tablas)
# ============================

class Reserva(Base):
    __tablename__ = "reservas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    laboratorio_id: Mapped[int] = mapped_column(Integer, ForeignKey("laboratorios.id", ondelete="RESTRICT"), index=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(40), default="activa")
    google_event_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Relaciones (Funcionan gracias a los modelos de arriba)
    usuario: Mapped[Usuario] = relationship(back_populates="reservas")
    laboratorio: Mapped[Laboratorio] = relationship(back_populates="reservas")

class ReglaHorario(Base):
    __tablename__ = "reglas_horario"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    laboratorio_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("laboratorios.id", ondelete="CASCADE"), nullable=True, index=True)
    dia_semana: Mapped[int] = mapped_column(Integer, index=True)
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    es_habilitado: Mapped[bool] = mapped_column(Boolean, default=True)
    tipo_intervalo: Mapped[Optional[str]] = mapped_column(String(50), default='disponible')
    laboratorio: Mapped[Optional["Laboratorio"]] = relationship(back_populates="reglas_horario")

class ExcepcionHorario(Base):
    __tablename__ = "excepciones_horario"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    laboratorio_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("laboratorios.id", ondelete="CASCADE"), nullable=True, index=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    hora_inicio: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    hora_fin: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    es_habilitado: Mapped[bool] = mapped_column(Boolean, default=False)
    descripcion: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    laboratorio: Mapped[Optional["Laboratorio"]] = relationship(back_populates="excepciones_horario")