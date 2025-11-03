from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime, time, date

# --- Schemas para Modelos "Leídos" ---

class Plantel(BaseModel):
    id: int
    nombre: str
    direccion: str
    model_config = ConfigDict(from_attributes=True)

class Laboratorio(BaseModel):
    id: int
    nombre: str
    ubicacion: Optional[str] = ""
    capacidad: Optional[int] = 0
    plantel: Optional[Plantel] = None
    model_config = ConfigDict(from_attributes=True)

class UsuarioSimple(BaseModel):
    id: int
    nombre: str
    user: str
    correo: str
    rol: str
    model_config = ConfigDict(from_attributes=True)

# --- Schemas para Modelos "Propios" ---

class ReservaBase(BaseModel):
    usuario_id: int
    laboratorio_id: int
    inicio: datetime
    fin: datetime

class ReservaCreate(ReservaBase): pass

class Reserva(ReservaBase):
    id: int
    estado: str
    google_event_id: Optional[str] = None
    usuario: UsuarioSimple # Incluye el objeto de usuario anidado
    model_config = ConfigDict(from_attributes=True)

# --- Schemas de Horarios ---

class ReglaHorarioBase(BaseModel):
    laboratorio_id: Optional[int] = None
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    es_habilitado: bool = True
    tipo_intervalo: Optional[str] = 'disponible'

class ReglaHorarioCreate(ReglaHorarioBase): pass

class ReglaHorarioUpdate(BaseModel):
    # (Copia los campos opcionales de pydantic_models.py)
    pass

class ReglaHorario(ReglaHorarioBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ExcepcionHorarioBase(BaseModel):
    laboratorio_id: Optional[int] = None
    fecha: date
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    es_habilitado: bool = False
    descripcion: Optional[str] = None

class ExcepcionHorarioCreate(ExcepcionHorarioBase): pass

class ExcepcionHorarioUpdate(BaseModel):
    # (Copia los campos opcionales de pydantic_models.py)
    pass

class ExcepcionHorario(ExcepcionHorarioBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class SlotHorario(BaseModel):
    inicio: datetime
    fin: datetime
    tipo: str