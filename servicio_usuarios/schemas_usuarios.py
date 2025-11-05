# servicio_usuarios/schemas_usuarios.py  (referencia)
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional

class UsuarioBase(BaseModel):
    nombre: str
    correo: EmailStr
    user: str
    rol: str

class UsuarioCreate(UsuarioBase):
    password: str

class Usuario(BaseModel):
    id: int
    nombre: str
    correo: EmailStr
    user: str
    rol: str
    model_config = ConfigDict(from_attributes=True)

class ProfileUpdate(BaseModel):
    nombre: Optional[str] = None
    user: Optional[str] = None
    correo: Optional[EmailStr] = None

class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str

class Token(BaseModel):
    access_token: str
    token_type: str
