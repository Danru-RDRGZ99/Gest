import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from starlette.config import Config
from sqlalchemy.orm import Session

# Importar desde los nuevos archivos locales
from db import SessionLocal, get_db
import models_inventario as models

# --- Cargar Configuración ---
# (Asegúrate que apunte al .env correcto para este servicio)
config = Config(".env.usuarios")

# --- Constantes de Seguridad ---
# (Debe estar en tu .env.usuarios)
SECRET_KEY = config("JWT_SECRET_KEY", default="un-secreto-muy-fuerte-por-defecto") 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(config("ACCESS_TOKEN_EXPIRE_MINUTES", default=60))

# Define el "scheme" de OAuth2
# "token" es el endpoint que el cliente usará para obtener el token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Dependencia de la sesión de DB
DbSession = Annotated[Session, Depends(get_db)]

# --- Funciones de Token ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, credentials_exception: HTTPException) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        rol: str = payload.get("rol")
        
        if username is None or user_id is None or rol is None:
            raise credentials_exception
        
        # Devuelve el "payload" (los datos) del token
        return {"sub": username, "id": user_id, "rol": rol}
    
    except JWTError:
        raise credentials_exception

# --- Dependencias de Seguridad (para los endpoints) ---

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = verify_token(token, credentials_exception)
    
    # Verificamos que el usuario del token todavía existe en la BD
    user = db.get(models.Usuario, payload["id"])
    
    if user is None:
        raise credentials_exception
        
    # Devolvemos el "payload" que contiene el ID y el ROL
    return payload

async def get_current_admin_user(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if current_user.get("rol") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación no permitida. Requiere rol de administrador."
        )
    return current_user