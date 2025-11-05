# security_reservas.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import os, httpx

# Host interno en Railway (sin puertos)
USUARIOS_URL = os.getenv("USUARIOS_URL", "http://servicio-usuarios.railway.internal")

# Clave compartida por TODOS los servicios (configúrala en Railway)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY no configurada en variables de entorno")

ALGORITHM = "HS256"

# Solo afecta al “Authorize” del Swagger, no a la validación real
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# --- Decodificador de JWT (sin tocar la BD) ---
def _decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        uid = payload.get("id")
        rol = payload.get("rol")
        if not (sub and uid and rol):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"user": sub, "id": uid, "rol": rol}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- (Opción A) Confiar en el JWT localmente ---
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    return _decode_token(token)

# --- (Opción B) Verificar contra servicio de Usuarios (si lo prefieres) ---
async def get_current_user_verified(token: str = Depends(oauth2_scheme)) -> dict:
    # Llama a /usuarios/verify del servicio de usuarios
    async with httpx.AsyncClient(base_url=USUARIOS_URL, timeout=5.0) as client:
        r = await client.get("/usuarios/verify", headers={"Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Token inválido")
        return r.json()

# Usa esta dependencia donde necesites rol admin
async def get_current_admin_user(user: dict = Depends(get_current_user)) -> dict:
    if user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol admin")
    return user
