from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict

class Usuario(BaseModel):
    id: int
    nombre: str
    correo: EmailStr
    user: str
    rol: str
    model_config = ConfigDict(from_attributes=True)

class UsuarioCreate(BaseModel):
    nombre: str
    correo: EmailStr
    user: str
    password: str
    rol: str

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
    user: Usuario

class TokenWithRoutes(Token):
    allowed_routes: List[str]
