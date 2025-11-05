# security_inventario.py
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import os, httpx

# Lee las URLs internas desde entorno (sin puertos)
USUARIOS_URL = os.getenv("USUARIOS_URL", "http://servicio-usuarios.railway.internal")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Lee clave JWT desde entorno; si falta, error explícito
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY no configurada en variables de entorno")
ALGORITHM = "HS256"

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Token faltante")
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return {"user": payload.get("sub"), "rol": payload.get("rol"), "id": payload.get("id")}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

async def get_current_admin_user(user: dict = Depends(get_current_user)) -> dict:
    if user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol admin")
    return user

# Si usas verificación remota del token:
async def verificar_token(authorization: str):
    async with httpx.AsyncClient(base_url=USUARIOS_URL, timeout=5.0) as client:
        r = await client.get("/usuarios/verify", headers={"Authorization": authorization})
        r.raise_for_status()
        return r.json()
