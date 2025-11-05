# security_usuarios.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from db import get_db
import models_usuarios as models

# === Config desde variables de entorno (Railway) ===
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    # Evita levantar el servicio si falta la clave
    raise RuntimeError("Falta JWT_SECRET_KEY en variables de entorno")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Para el botón "Authorize" del Swagger (no valida por sí mismo)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# Tipo para inyectar la sesión
DbSession = Annotated[Session, Depends(get_db)]

# === Tokens ===
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str, credentials_exception: HTTPException) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        uid = payload.get("id")
        rol = payload.get("rol")
        if not (sub and uid and rol):
            raise credentials_exception
        # Normalizamos a {"user","id","rol"} para que coincida con Inventario/Reservas
        return {"user": sub, "id": uid, "rol": rol}
    except JWTError:
        raise credentials_exception

# === Dependencias ===
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    current = verify_token(token, credentials_exception)

    # (Usuarios SÍ puede tocar su BD) confirma que el usuario aún existe
    if not db.get(models.Usuario, current["id"]):
        raise credentials_exception

    return current

async def get_current_admin_user(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if current_user.get("rol") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operación no permitida. Requiere rol de administrador.")
    return current_user
