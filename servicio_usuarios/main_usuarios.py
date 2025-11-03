# --- Standard FastAPI and SQLAlchemy Imports ---
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from typing import List, Annotated, Optional
from datetime import timedelta
import traceback

# --- Security and Authentication Imports ---
from pydantic import BaseModel, EmailStr
import string
import secrets

# --- Google Auth Imports (para /auth/google-token) ---
from google.oauth2 import id_token
from google.auth.exceptions import GoogleAuthError

# --- CAPTCHA Imports ---
from starlette.middleware.sessions import SessionMiddleware
from captcha.image import ImageCaptcha
from io import BytesIO
import random

# --- Configuración y Otros ---
from starlette.config import Config
from starlette.responses import JSONResponse

# --- Project-specific Core Imports ---
# (Importamos desde los nuevos archivos locales)
from db import SessionLocal, get_db # Asumiendo que get_db está en db.py
import auth_service_usuarios as auth_service
import models_usuarios as models
import security_usuarios as security
import schemas_usuarios as schemas
import rbac_usuarios # --- AÑADIDO PARA LOS PERMISOS ---

# --- Cargar Configuración ---
# (Asegúrate que apunte al .env correcto para este servicio)
config = Config(".env")

# --- Database Initialization ---
# (Crea el admin 'dev' si es necesario)
auth_service.init_db(create_dev_admin=True)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="API de Servicio de Usuarios",
    description="Servicio dedicado para autenticación y gestión de perfiles.",
    version="1.0.0"
)

# --- Middleware (para CAPTCHA) ---
app.add_middleware(
    SessionMiddleware,
    secret_key=config("SESSION_SECRET_KEY", default="a-very-secret-key-please-change"),
    session_cookie="session_id",
    max_age=3600,
    same_site="lax",
    https_only=False
)

# --- Helper for Random Password (usado en Google Login) ---
def generate_random_password(length=16):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))
# --- End Helper ---

# --- Schemas (copiados de tu main.py original ) ---
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

# --- Database Dependency ---
DbSession = Annotated[Session, Depends(get_db)]

# --- Security Dependencies ---
CurrentUser = Annotated[dict, Depends(security.get_current_user)]
AdminUser = Annotated[dict, Depends(security.get_current_admin_user)]
# --- End Security Dependencies ---

# ==============================================================================
# --- AUTHENTICATION ENDPOINTS (Copiados de main.py ) ---
# ==============================================================================

@app.get("/captcha", tags=["Auth"])
async def get_captcha(request: Request):
    image_captcha = ImageCaptcha()
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    request.session["captcha_text"] = captcha_text
    image_stream = image_captcha.generate(captcha_text)
    image_bytes = image_stream.getvalue()
    return Response(content=image_bytes, media_type="image/png")

@app.post("/token", response_model=schemas.Token, tags=["Auth"])
async def login_for_access_token(request: Request, login_data: LoginRequest, db: DbSession):
    captcha_esperado = request.session.get("captcha_text")
    if "captcha_text" in request.session: del request.session["captcha_text"]
    if not captcha_esperado or login_data.captcha.upper() != captcha_esperado.upper():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El texto del CAPTCHA es incorrecto.")
    
    user_dict = auth_service.login(username_or_email=login_data.username, password=login_data.password)
    if not user_dict:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos", headers={"WWW-Authenticate": "Bearer"})
    
    expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {"sub": user_dict["user"], "rol": user_dict["rol"], "id": user_dict["id"]}
    access_token = security.create_access_token(data=token_data, expires_delta=expires)
    
    user_obj = db.get(models.Usuario, user_dict["id"])
    if not user_obj: raise HTTPException(status_code=404, detail="Usuario no encontrado post-login.")
    
    # --- AÑADIDO PARA RBAC ---
    user_role = user_dict["rol"]
    user_routes = rbac_usuarios.allowed_routes(user_role)
    
    return {"access_token": access_token, "token_type": "bearer", "user": user_obj, "allowed_routes": user_routes}

@app.post("/auth/google-token", response_model=schemas.Token, tags=["Auth"])
async def login_with_google_token(token_data: GoogleToken, db: DbSession):
    try:
        google_client_id = config("GOOGLE_CLIENT_ID")
        if not google_client_id: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="GOOGLE_CLIENT_ID no configurado en .env")
        
        id_info = id_token.verify_oauth2_token(token_data.id_token, request=None, audience=google_client_id)
        user_email = id_info.get('email').lower()
        user_name = id_info.get('name') or id_info.get('given_name') or user_email.split('@')[0]
        
        if not user_email: raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No se pudo obtener el email del token de Google.")
        
        db_user = db.query(models.Usuario).filter(models.Usuario.correo == user_email).first()
        
        if not db_user:
            random_pass = generate_random_password()
            ok, result = auth_service.create_user(nombre=user_name, correo=user_email, user=user_email, password=random_pass, rol='estudiante')
            if not ok:
                if "El usuario ya existe" in str(result):
                    user_username = f"{user_email.split('@')[0]}_{secrets.token_hex(4)}"
                    ok, result = auth_service.create_user(nombre=user_name, correo=user_email, user=user_username, password=random_pass, rol='estudiante')
                if not ok: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al crear usuario: {result}")
            db_user = db.get(models.Usuario, result["id"])
            if not db_user: raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, detail="Usuario creado pero no se pudo recuperar.")
        
        expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
        token_data_payload = {"sub": db_user.user, "rol": db_user.rol, "id": db_user.id}
        access_token = security.create_access_token(data=token_data_payload, expires_delta=expires)
        
        # --- AÑADIDO PARA RBAC ---
        user_role = db_user.rol
        user_routes = rbac.allowed_routes(user_role)
        
        return {"access_token": access_token, "token_type": "bearer", "user": db_user, "allowed_routes": user_routes}
        
    except GoogleAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token de Google inválido o expirado: {e}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno del servidor: {e}")

@app.post("/register", response_model=schemas.Usuario, tags=["Auth"], status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UsuarioCreate, db: DbSession):
    ok, result = auth_service.create_user(**user.model_dump())
    if not ok: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(result))
    
    user_db = db.get(models.Usuario, result["id"])
    if not user_db: raise HTTPException(status_code=404, detail="Usuario creado pero no recuperado.")
    
    return user_db

# ==============================================================================
# --- USER MANAGEMENT ENDPOINTS (Copiados de main.py ) ---
# ==============================================================================

@app.get("/usuarios", response_model=List[schemas.Usuario], tags=["Usuarios (Admin)"])
def get_all_users(user: AdminUser, db: DbSession, q: Optional[str] = "", rol: Optional[str] = ""):
    query = db.query(models.Usuario)
    if rol: query = query.filter(models.Usuario.rol == rol)
    if q:
        search = f"%{q.lower()}%"
        query = query.filter((models.Usuario.nombre.ilike(search)) | (models.Usuario.user.ilike(search)) | (models.Usuario.correo.ilike(search)))
    return query.order_by(models.Usuario.nombre.asc()).all()

@app.put("/usuarios/{user_id}", response_model=schemas.Usuario, tags=["Usuarios (Admin)"])
def update_user_by_admin(user_id: int, user_update: UsuarioAdminUpdate, user: AdminUser, db: DbSession):
    user_to_update = db.get(models.Usuario, user_id)
    if not user_to_update: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user_id == user["id"] and user_update.rol and user_update.rol != "admin": 
        raise HTTPException(status_code=403, detail="No puedes revocar tu propio rol.")
    
    update_data = user_update.model_dump(exclude_unset=True)
    if not update_data: raise HTTPException(status_code=400, detail="No se proporcionaron datos.")
    
    # ... (Resto de validaciones de update_user_by_admin) ...
    
    for key, value in update_data.items(): setattr(user_to_update, key, value)
    try: 
        db.commit(); db.refresh(user_to_update); return user_to_update
    except Exception as e: 
        db.rollback(); raise HTTPException(status_code=500, detail="Error interno.")

@app.delete("/usuarios/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Usuarios (Admin)"])
def delete_user(user_id: int, user: AdminUser, db: DbSession):
    if user_id == user["id"]: 
        raise HTTPException(status_code=403, detail="No puedes eliminar tu propia cuenta.")
    user_to_delete = db.get(models.Usuario, user_id)
    if not user_to_delete: 
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # --- IMPORTANTE: Chequeo de Préstamos ---
    # En una arquitectura de microservicios, este chequeo YA NO SE PUEDE HACER ASÍ.
    # El `servicio_usuarios` no debe conocer la tabla `Prestamo`.
    #
    # ¿Solución?
    # 1. (Sincrónica): El servicio llama al `servicio_inventario`
    #    GET /prestamos?usuario_id={user_id}&estado=activo
    #    Y si la respuesta no está vacía, lanza el error 409.
    # 2. (Asincrónica): "Borrado suave" (soft delete). Marcas al usuario como `desactivado`
    #    y un proceso luego verifica si se puede borrar de verdad.
    #
    # Por ahora, *comentaremos esta validación* para mantener el servicio desacoplado.
    # active_prestamos = db.query(models.Prestamo)...
    # if active_prestamos > 0: raise HTTPException(status_code=409, detail=...)

    try:
        db.delete(user_to_delete); db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        # Si la base de datos (por foreign key) no te deja borrar,
        # significa que aún hay dependencias en otros servicios.
        if "violates foreign key constraint" in str(e).lower():
            raise HTTPException(status_code=409, detail="No se puede eliminar: el usuario tiene datos asociados en otros servicios (reservas o préstamos).")
        raise HTTPException(status_code=500, detail=f"Error interno al eliminar usuario: {e}")

@app.put("/usuarios/me/profile", response_model=schemas.Usuario, tags=["Usuarios"])
def update_my_profile(profile_data: schemas.ProfileUpdate, user: CurrentUser, db: DbSession):
    user_to_update = db.get(models.Usuario, user["id"])
    if not user_to_update: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    update_data = profile_data.model_dump(exclude_unset=True)
    if not update_data: raise HTTPException(status_code=400, detail="No se proporcionaron datos.")
    
    # ... (Resto de validaciones de update_my_profile) ...
    
    for key, value in update_data.items(): setattr(user_to_update, key, value)
    try: 
        db.commit(); db.refresh(user_to_update); return user_to_update
    except Exception as e: 
        db.rollback(); raise HTTPException(status_code=500, detail="Error interno.")

@app.put("/usuarios/me/password", tags=["Usuarios"])
def change_my_password(pass_data: schemas.PasswordUpdate, user: CurrentUser, db: DbSession):
    user_in_db = db.get(models.Usuario, user["id"])
    if not user_in_db: raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if not auth_service.verify_password(pass_data.old_password, user_in_db.password_hash): 
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta.")
    if len(pass_data.new_password) < 6: 
        raise HTTPException(status_code=400, detail="Contraseña debe tener >= 6 caracteres.")
    
    user_in_db.password_hash = auth_service.hash_password(pass_data.new_password)
    try: 
        db.commit(); return {"message": "Contraseña actualizada."}
    except Exception as e: 
        db.rollback(); raise HTTPException(status_code=500, detail="Error interno.")

# ==============================================================================
# --- ENDPOINTS INTERNOS (Servicio-a-Servicio) ---
# ==============================================================================

@app.get("/usuarios/internal/{user_id}", response_model=schemas.Usuario, tags=["Internal"])
def get_user_by_id_internal(user_id: int, db: DbSession):
    """
    Endpoint interno para que otros servicios (como Inventario) 
    puedan verificar un ID de usuario y obtener sus detalles.
    """
    user = db.get(models.Usuario, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user