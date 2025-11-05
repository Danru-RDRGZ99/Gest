from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from db import Base, engine, get_db
import models_usuarios as models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_db(create_dev_admin: bool = False):
    Base.metadata.create_all(bind=engine)
    if create_dev_admin:
        with next(get_db()) as db:
            if not db.query(models.Usuario).filter(models.Usuario.user == "admin").first():
                u = models.Usuario(
                    nombre="Administrador",
                    correo="admin@example.com",
                    user="admin",
                    password_hash=hash_password("admin"),
                    rol="admin",
                )
                db.add(u)
                db.commit()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def login(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
    with next(get_db()) as db:
        q = db.query(models.Usuario).filter(
            (models.Usuario.user == username_or_email) | (models.Usuario.correo == username_or_email)
        ).first()
        if not q:
            return None
        if not verify_password(password, q.password_hash):
            return None
        return {"id": q.id, "user": q.user, "rol": q.rol}

def create_user(nombre: str, correo: str, user: str, password: str, rol: str) -> Tuple[bool, Any]:
    with next(get_db()) as db:
        if db.query(models.Usuario).filter(models.Usuario.user == user).first():
            return False, "El usuario ya existe"
        if db.query(models.Usuario).filter(models.Usuario.correo == correo).first():
            return False, "El correo ya existe"
        u = models.Usuario(
            nombre=nombre,
            correo=correo.lower(),
            user=user,
            password_hash=hash_password(password),
            rol=rol,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return True, {"id": u.id}
