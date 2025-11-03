from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional

# --- Base Schemas ---

class UsuarioBase(BaseModel):
    nombre: str
    correo: EmailStr
    user: str
    rol: str

# --- Create Schemas ---

class UsuarioCreate(UsuarioBase):
    password: str

# --- Read Schemas ---

class Usuario(UsuarioBase): # El schema principal de lectura de Usuario
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Auth Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Usuario # Incluye los detalles completos del usuario en el login

# --- Update Schemas (usados en los endpoints) ---

class ProfileUpdate(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[EmailStr] = None
    user: Optional[str] = None

class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str

# --- TODOS LOS DEMÁS SCHEMAS (Plantel, Laboratorio, Recurso, Reserva, etc.) HAN SIDO ELIMINADOS ---