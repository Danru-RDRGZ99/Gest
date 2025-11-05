# security_inventario.py (Inventario)
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from starlette.config import Config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
config = Config(".env")

JWT_SECRET_KEY = config("JWT_SECRET_KEY")
ALGORITHM = "HS256"

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Token faltante")
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        # payload: {"sub": user, "rol": "...", "id": ...}
        return {
            "user": payload.get("sub"),
            "rol": payload.get("rol"),
            "id": payload.get("id"),
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

async def get_current_admin_user(user: dict = Depends(get_current_user)) -> dict:
    if user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol admin")
    return user
