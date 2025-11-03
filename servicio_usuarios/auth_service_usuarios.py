import bcrypt
from sqlalchemy import or_

# --- Importar desde los nuevos archivos locales ---
from db import SessionLocal, engine # <--- Quita 'Base' de aquí
from models_usuarios import Usuario, Base # <--- Importa 'Base' desde models_usuarios

# --------------------------------------------------------------------------------------
# Inicialización de BD
# --------------------------------------------------------------------------------------
def init_db(create_dev_admin: bool = False) -> None:
    # Asegúrate que Base tenga el modelo Usuario registrado
    Base.metadata.create_all(bind=engine) 
    if create_dev_admin:
        _ensure_dev_admin()

def _ensure_dev_admin() -> None:
    db = SessionLocal()
    try:
        admin = db.query(Usuario).filter(Usuario.user == "admin").first()
        if not admin:
            print("INFO: Creando usuario admin por defecto (admin / admin123)")
            u = Usuario(
                nombre="Administrador",
                correo="admin@example.com",
                user="admin",
                password_hash=hash_password("admin123"),
                rol="admin",
            )
            db.add(u)
            db.commit()
        else:
            print("INFO: Usuario admin ya existe.")
    except Exception as e:
        print(f"ERROR: No se pudo verificar/crear el usuario admin: {e}")
        db.rollback()
    finally:
        db.close()

# --------------------------------------------------------------------------------------
# Password helpers
# --------------------------------------------------------------------------------------
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(p: str, h: str | bytes) -> bool:
    h_bytes = h.encode("utf-8") if isinstance(h, str) else h
    return bcrypt.checkpw(p.encode("utf-8"), h_bytes)

# --------------------------------------------------------------------------------------
# Auth API (Login)
# --------------------------------------------------------------------------------------
def login(username_or_email: str, password: str):
    username_or_email = (username_or_email or "").strip()
    db = SessionLocal()
    try:
        u = (
            db.query(Usuario)
            .filter(
                or_(
                    Usuario.user == username_or_email,
                    Usuario.correo == username_or_email.lower(),
                )
            )
            .first()
        )
        if not u:
            return None # Usuario no encontrado
        
        if not verify_password(password or "", u.password_hash):
            return None # Contraseña incorrecta

        return {
            "id": u.id,
            "nombre": u.nombre,
            "user": u.user,
            "rol": u.rol,
            "correo": u.correo,
        }
    except Exception as e:
        print(f"ERROR: Excepción durante el login: {e}")
        return None
    finally:
        db.close()

# --------------------------------------------------------------------------------------
# Auth API (Create User)
# --------------------------------------------------------------------------------------
ALLOWED_ROLES = {"admin", "docente", "estudiante"}

def create_user(nombre: str, correo: str, user: str, password: str, rol: str):
    nombre = (nombre or "").strip()
    correo = (correo or "").strip().lower()
    user_param = (user or "").strip()
    rol_norm = (rol or "").strip().lower()

    if rol_norm not in ALLOWED_ROLES:
        return False, "Rol no permitido (usa: admin, docente o estudiante)"
    if not nombre or not correo or not user_param or not password:
        return False, "Campos incompletos"
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres"

    db = SessionLocal()
    try:
        if db.query(Usuario).filter(Usuario.user == user_param).first():
            return False, "El usuario ya existe"
        if db.query(Usuario).filter(Usuario.correo == correo).first():
            return False, "El correo ya está registrado"

        u = Usuario(
            nombre=nombre,
            correo=correo,
            user=user_param,
            password_hash=hash_password(password),
            rol=rol_norm,
        )
        db.add(u)
        db.commit()
        db.refresh(u)

        return True, {
            "id": u.id,
            "nombre": u.nombre,
            "user": u.user,
            "rol": u.rol,
            "correo": u.correo,
        }
    except Exception as e:
        db.rollback()
        print(f"ERROR: Excepción al crear usuario: {e}")
        return False, f"Error interno al crear usuario: {e}"
    finally:
        db.close()