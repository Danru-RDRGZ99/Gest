from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from typing import List, Annotated, Optional
from datetime import timedelta
from pydantic import BaseModel, EmailStr
import string
import secrets
from google.oauth2 import id_token
from google.auth.exceptions import GoogleAuthError
from starlette.middleware.sessions import SessionMiddleware
from captcha.image import ImageCaptcha
from io import BytesIO
import random
from starlette.config import Config

from db import get_db
import auth_service_usuarios as auth_service
import models_usuarios as models
import security_usuarios as security
import schemas_usuarios as schemas
import rbac_usuarios

config = Config(".env")

app = FastAPI(title="API de Servicio de Usuarios", description="Servicio dedicado para autenticación y gestión de perfiles.", version="1.0.0")

app.add_middleware(
    SessionMiddleware,
    secret_key=config("SESSION_SECRET_KEY", default="a-very-secret-key-please-change"),
    session_cookie="session_id",
    max_age=3600,
    same_site="lax",
    https_only=False,
)

def generate_random_password(length=16):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

class UsuarioAdminUpdate(BaseModel):
    nombre: Optional[str] = None
    user: Optional[str] = None
    correo: Optional[EmailStr] = None
    rol: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str
    captcha: str

class GoogleToken(BaseModel):
    id_token: str

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(security.get_current_user)]
AdminUser = Annotated[dict, Depends(security.get_current_admin_user)]

def user_to_dict(u: models.Usuario) -> dict:
    return {"id": u.id, "nombre": u.nombre, "correo": u.correo, "user": u.user, "rol": u.rol}

@app.on_event("startup")
def _startup():
    auth_service.init_db(create_dev_admin=True)

@app.get("/__health")
async def health():
    return {"status": "ok"}

@app.get("/usuarios/verify")
async def verify(user: dict = Depends(security.get_current_user)):
    return user

@app.get("/captcha", tags=["Auth"])
async def get_captcha(request: Request):
    image_captcha = ImageCaptcha()
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    request.session["captcha_text"] = captcha_text
    image_stream = image_captcha.generate(captcha_text)
    image_bytes = image_stream.getvalue()
    return Response(content=image_bytes, media_type="image/png")

@app.post("/token", tags=["Auth"])
async def login_for_access_token(request: Request, login_data: LoginRequest, db: DbSession):
    captcha_esperado = request.session.get("captcha_text")
    if "captcha_text" in request.session:
        del request.session["captcha_text"]
    if not captcha_esperado or login_data.captcha.upper() != captcha_esperado.upper():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El texto del CAPTCHA es incorrecto.")
    user_dict = auth_service.login(username_or_email=login_data.username, password=login_data.password)
    if not user_dict:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos", headers={"WWW-Authenticate": "Bearer"})
    expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {"sub": user_dict["user"], "rol": user_dict["rol"], "id": user_dict["id"]}
    access_token = security.create_access_token(data=token_data, expires_delta=expires)
    user_obj = db.get(models.Usuario, user_dict["id"])
    if not user_obj:
        raise HTTPException(status_code=404, detail="Usuario no encontrado post-login.")
    routes = rbac_usuarios.allowed_routes(user_dict["rol"])
    return {"access_token": access_token, "token_type": "bearer", "user": user_to_dict(user_obj), "allowed_routes": routes}

@app.post("/auth/google-token", tags=["Auth"])
async def login_with_google_token(token_data: GoogleToken, db: DbSession):
    try:
        google_client_id = config("GOOGLE_CLIENT_ID")
        if not google_client_id:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="GOOGLE_CLIENT_ID no configurado")
        id_info = id_token.verify_oauth2_token(token_data.id_token, request=None, audience=google_client_id)
        user_email = (id_info.get('email') or "").lower()
        user_name = id_info.get('name') or id_info.get('given_name') or (user_email.split('@')[0] if user_email else "")
        if not user_email:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No se pudo obtener el email del token de Google.")
        db_user = db.query(models.Usuario).filter(models.Usuario.correo == user_email).first()
        if not db_user:
            random_pass = generate_random_password()
            ok, result = auth_service.create_user(nombre=user_name, correo=user_email, user=user_email, password=random_pass, rol='estudiante')
            if not ok:
                if "El usuario ya existe" in str(result):
                    user_username = f"{user_email.split('@')[0]}_{secrets.token_hex(4)}"
                    ok, result = auth_service.create_user(nombre=user_name, correo=user_email, user=user_username, password=random_pass, rol='estudiante')
                if not ok:
                    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al crear usuario: {result}")
            db_user = db.get(models.Usuario, result["id"])
            if not db_user:
                raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, detail="Usuario creado pero no se pudo recuperar.")
        expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
        token_data_payload = {"sub": db_user.user, "rol": db_user.rol, "id": db_user.id}
        access_token = security.create_access_token(data=token_data_payload, expires_delta=expires)
        routes = rbac_usuarios.allowed_routes(db_user.rol)
        return {"access_token": access_token, "token_type": "bearer", "user": user_to_dict(db_user), "allowed_routes": routes}
    except GoogleAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token de Google inválido o expirado: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno del servidor: {e}")

@app.post("/register", response_model=schemas.Usuario, tags=["Auth"], status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UsuarioCreate, db: DbSession):
    ok, result = auth_service.create_user(**user.model_dump())
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(result))
    user_db = db.get(models.Usuario, result["id"])
    if not user_db:
        raise HTTPException(status_code=404, detail="Usuario creado pero no recuperado.")
    return user_db

@app.get("/usuarios", response_model=List[schemas.Usuario], tags=["Usuarios (Admin)"])
def get_all_users(user: AdminUser, db: DbSession, q: Optional[str] = "", rol: Optional[str] = ""):
    query = db.query(models.Usuario)
    if rol:
        query = query.filter(models.Usuario.rol == rol)
    if q:
        search = f"%{q.lower()}%"
        query = query.filter(
            (models.Usuario.nombre.ilike(search))
            | (models.Usuario.user.ilike(search))
            | (models.Usuario.correo.ilike(search))
        )
    return query.order_by(models.Usuario.nombre.asc()).all()

@app.put("/usuarios/{user_id}", response_model=schemas.Usuario, tags=["Usuarios (Admin)"])
def update_user_by_admin(user_id: int, user_update: UsuarioAdminUpdate, user: AdminUser, db: DbSession):
    user_to_update = db.get(models.Usuario, user_id)
    if not user_to_update:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user_id == user["id"] and user_update.rol and user_update.rol != "admin":
        raise HTTPException(status_code=403, detail="No puedes revocar tu propio rol.")
    update_data = user_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No se proporcionaron datos.")
    for k, v in update_data.items():
        setattr(user_to_update, k, v)
    try:
        db.commit()
        db.refresh(user_to_update)
        return user_to_update
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno.")

@app.delete("/usuarios/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Usuarios (Admin)"])
def delete_user(user_id: int, user: AdminUser, db: DbSession):
    if user_id == user["id"]:
        raise HTTPException(status_code=403, detail="No puedes eliminar tu propia cuenta.")
    user_to_delete = db.get(models.Usuario, user_id)
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    try:
        db.delete(user_to_delete)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        if "violates foreign key constraint" in str(e).lower():
            raise HTTPException(status_code=409, detail="No se puede eliminar: el usuario tiene datos asociados en otros servicios.")
        raise HTTPException(status_code=500, detail=f"Error interno al eliminar usuario: {e}")

@app.put("/usuarios/me/profile", response_model=schemas.Usuario, tags=["Usuarios"])
def update_my_profile(profile_data: schemas.ProfileUpdate, user: CurrentUser, db: DbSession):
    user_to_update = db.get(models.Usuario, user["id"])
    if not user_to_update:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    update_data = profile_data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No se proporcionaron datos.")
    for k, v in update_data.items():
        setattr(user_to_update, k, v)
    try:
        db.commit()
        db.refresh(user_to_update)
        return user_to_update
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno.")

@app.put("/usuarios/me/password", tags=["Usuarios"])
def change_my_password(pass_data: schemas.PasswordUpdate, user: CurrentUser, db: DbSession):
    user_in_db = db.get(models.Usuario, user["id"])
    if not user_in_db:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if not auth_service.verify_password(pass_data.old_password, user_in_db.password_hash):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta.")
    if len(pass_data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Contraseña debe tener >= 6 caracteres.")
    user_in_db.password_hash = auth_service.hash_password(pass_data.new_password)
    try:
        db.commit()
        return {"message": "Contraseña actualizada."}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno.")

@app.get("/__health")
def health():
    return {"ok": True}
