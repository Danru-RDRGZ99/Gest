from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime

# --- Schema para Modelo "Leído" ---
class UsuarioSimple(BaseModel):
    id: int
    nombre: str
    user: str
    correo: str
    rol: str
    model_config = ConfigDict(from_attributes=True)

# --- Schemas para Modelos "Propios" ---

class PlantelBase(BaseModel):
    nombre: str
    direccion: str
class PlantelCreate(PlantelBase): pass
class Plantel(PlantelBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class LaboratorioBase(BaseModel):
    nombre: str
    ubicacion: Optional[str] = ""
    capacidad: Optional[int] = 0
    plantel_id: int
class LaboratorioCreate(LaboratorioBase): pass
class Laboratorio(LaboratorioBase):
    id: int
    plantel: Optional[Plantel] = None
    model_config = ConfigDict(from_attributes=True)

class RecursoBase(BaseModel):
    laboratorio_id: int
    tipo: str
    estado: str
    specs: Optional[str] = ""
class RecursoCreate(RecursoBase): pass
class Recurso(RecursoBase):
    id: int
    laboratorio: Optional[Laboratorio] = None
    model_config = ConfigDict(from_attributes=True)

class PrestamoBase(BaseModel):
    recurso_id: int
    usuario_id: int
    cantidad: int = 1
    inicio: datetime
    fin: datetime
    comentario: Optional[str] = None
class PrestamoCreate(PrestamoBase): pass
class Prestamo(PrestamoBase):
    id: int
    estado: str
    created_at: datetime
    solicitante: str
    recurso: Recurso       # Objeto anidado
    usuario: UsuarioSimple # Objeto anidado
    model_config = ConfigDict(from_attributes=True)