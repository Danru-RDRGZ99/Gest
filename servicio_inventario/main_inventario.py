# --- Standard FastAPI and SQLAlchemy Imports ---
from fastapi import FastAPI, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session, joinedload
from typing import List, Annotated, Optional
from datetime import timezone
from starlette.config import Config
import httpx

from db import engine, SessionLocal, get_db
import models_inventario as models
import security_inventario as security
import schemas_inventario as schemas

config = Config(".env")

app = FastAPI(
    title="API de Servicio de Inventario",
    description="Servicio dedicado para gestionar planteles, laboratorios, recursos y préstamos.",
    version="1.0.0",
)

@app.on_event("startup")
async def startup_event():
    models.Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "ok"}

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(security.get_current_user)]
AdminUser = Annotated[dict, Depends(security.get_current_admin_user)]

def _normalize_url(v: str, default: str) -> str:
    if not v:
        return default
    v = v.strip()
    if v.startswith(("http://", "https://")):
        return v.rstrip("/")
    return f"http://{v}".rstrip("/")

USER_SERVICE_URL = _normalize_url(config("USER_SERVICE_URL", default="http://localhost:8001"), "http://localhost:8001")
RESERVA_SERVICE_URL = _normalize_url(config("RESERVA_SERVICE_URL", default="http://localhost:8002"), "http://localhost:8002")

async def _get_user_details_from_api(user_id: int) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            r = await client.get(f"{USER_SERVICE_URL}/usuarios/internal/{user_id}")
            if r.status_code == 200:
                d = r.json()
                return {"correo": d.get("correo"), "nombre": d.get("nombre")}
            return None
    except httpx.RequestError:
        return None

async def _get_reservas_count_from_api(lab_id: int) -> int:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            r = await client.get(f"{RESERVA_SERVICE_URL}/reservas/{lab_id}/count")
            if r.status_code == 200:
                j = r.json()
                return int(j.get("active_count", 0))
            return 0
    except httpx.RequestError:
        return -1

@app.get("/planteles", response_model=List[schemas.Plantel], tags=["Admin: Gestión"])
def get_all_planteles(user: CurrentUser, db: DbSession):
    return db.query(models.Plantel).order_by(models.Plantel.nombre.asc()).all()

@app.post("/planteles", response_model=schemas.Plantel, status_code=status.HTTP_201_CREATED, tags=["Admin: Gestión"])
def create_plantel(plantel: schemas.PlantelCreate, user: AdminUser, db: DbSession):
    new_plantel = models.Plantel(**plantel.model_dump())
    db.add(new_plantel)
    try:
        db.commit()
        db.refresh(new_plantel)
        return new_plantel
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error: {e}")

@app.put("/planteles/{plantel_id}", response_model=schemas.Plantel, tags=["Admin: Gestión"])
def update_plantel(plantel_id: int, plantel_update: schemas.PlantelCreate, user: AdminUser, db: DbSession):
    db_plantel = db.get(models.Plantel, plantel_id)
    if not db_plantel:
        raise HTTPException(status_code=404, detail="Plantel no encontrado")
    update_data = plantel_update.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(db_plantel, k, v)
    try:
        db.commit()
        db.refresh(db_plantel)
        return db_plantel
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error al actualizar plantel: {e}")

@app.delete("/planteles/{plantel_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Gestión"])
def delete_plantel(plantel_id: int, user: AdminUser, db: DbSession):
    db_plantel = db.get(models.Plantel, plantel_id)
    if not db_plantel:
        raise HTTPException(status_code=404, detail="Plantel no encontrado")
    labs_count = db.query(models.Laboratorio).filter(models.Laboratorio.plantel_id == plantel_id).count()
    if labs_count > 0:
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: hay {labs_count} laboratorios asociados.")
    try:
        db.delete(db_plantel)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")

@app.get("/laboratorios", response_model=List[schemas.Laboratorio], tags=["Admin: Gestión"])
def get_all_laboratorios(user: CurrentUser, db: DbSession):
    return (
        db.query(models.Laboratorio)
        .options(joinedload(models.Laboratorio.plantel))
        .order_by(models.Laboratorio.id.desc())
        .all()
    )

@app.post("/laboratorios", response_model=schemas.Laboratorio, status_code=status.HTTP_201_CREATED, tags=["Admin: Gestión"])
def create_laboratorio(lab: schemas.LaboratorioCreate, user: AdminUser, db: DbSession):
    plantel = db.get(models.Plantel, lab.plantel_id)
    if not plantel:
        raise HTTPException(status_code=404, detail=f"Plantel id {lab.plantel_id} no encontrado.")
    new_lab = models.Laboratorio(**lab.model_dump())
    db.add(new_lab)
    try:
        db.commit()
        db.refresh(new_lab)
        db.refresh(new_lab.plantel)
        return new_lab
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error: {e}")

@app.put("/laboratorios/{lab_id}", response_model=schemas.Laboratorio, tags=["Admin: Gestión"])
def update_laboratorio(lab_id: int, lab_update: schemas.LaboratorioCreate, user: AdminUser, db: DbSession):
    db_lab = db.get(models.Laboratorio, lab_id)
    if not db_lab:
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado")
    if lab_update.plantel_id and not db.get(models.Plantel, lab_update.plantel_id):
        raise HTTPException(status_code=404, detail=f"Plantel id {lab_update.plantel_id} no encontrado.")
    update_data = lab_update.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(db_lab, k, v)
    try:
        db.commit()
        db.refresh(db_lab)
        db.refresh(db_lab.plantel)
        return db_lab
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error al actualizar laboratorio: {e}")

@app.delete("/laboratorios/{lab_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Gestión"])
async def delete_laboratorio(lab_id: int, user: CurrentUser, db: DbSession):
    db_lab = db.get(models.Laboratorio, lab_id)
    if not db_lab:
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado")
    recursos_count = db.query(models.Recurso).filter(models.Recurso.laboratorio_id == lab_id).count()
    if recursos_count > 0:
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: hay {recursos_count} recurso(s) asociados.")
    reservas_count = await _get_reservas_count_from_api(lab_id)
    if reservas_count == -1:
        raise HTTPException(status_code=503, detail="No se pudo verificar el estado de las reservas. Intente de nuevo.")
    if reservas_count > 0:
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: hay {reservas_count} reserva(s) asociada(s).")
    try:
        db.delete(db_lab)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {e}")

@app.get("/recursos", response_model=List[schemas.Recurso], tags=["Recursos"])
def get_recursos_filtrados(
    user: CurrentUser,
    db: DbSession,
    plantel_id: Optional[int] = None,
    lab_id: Optional[int] = None,
    estado: Optional[str] = None,
    tipo: Optional[str] = None,
):
    q = db.query(models.Recurso)
    if lab_id:
        q = q.filter(models.Recurso.laboratorio_id == lab_id)
    elif plantel_id:
        lab_ids_sub = db.query(models.Laboratorio.id).filter(models.Laboratorio.plantel_id == plantel_id).subquery()
        q = q.filter(models.Recurso.laboratorio_id.in_(lab_ids_sub))
    if estado:
        q = q.filter(models.Recurso.estado == estado)
    if tipo:
        q = q.filter(models.Recurso.tipo == tipo)
    q = q.options(joinedload(models.Recurso.laboratorio).joinedload(models.Laboratorio.plantel))
    return q.order_by(models.Recurso.id.desc()).all()

@app.get("/recursos/tipos", response_model=List[str], tags=["Recursos"])
def get_recurso_tipos(user: CurrentUser, db: DbSession):
    tipos = db.query(models.Recurso.tipo).distinct().order_by(models.Recurso.tipo).all()
    return [t[0] for t in tipos if t and t[0] and t[0].strip()]

@app.post("/recursos", response_model=schemas.Recurso, status_code=status.HTTP_201_CREATED, tags=["Admin: Gestión"])
def create_recurso(recurso: schemas.RecursoCreate, user: AdminUser, db: DbSession):
    lab = db.get(models.Laboratorio, recurso.laboratorio_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Laboratorio id no encontrado.")
    new_recurso = models.Recurso(**recurso.model_dump())
    db.add(new_recurso)
    try:
        db.commit()
        db.refresh(new_recurso)
        db.refresh(new_recurso.laboratorio)
        return new_recurso
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error al crear recurso: {e}")

@app.put("/recursos/{recurso_id}", response_model=schemas.Recurso, tags=["Admin: Gestión"])
def update_recurso(recurso_id: int, recurso_update: schemas.RecursoCreate, user: AdminUser, db: DbSession):
    db_recurso = db.get(models.Recurso, recurso_id)
    if not db_recurso:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    if recurso_update.laboratorio_id and not db.get(models.Laboratorio, recurso_update.laboratorio_id):
        raise HTTPException(status_code=404, detail=f"Laboratorio id {recurso_update.laboratorio_id} no encontrado.")
    update_data = recurso_update.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(db_recurso, k, v)
    try:
        db.commit()
        db.refresh(db_recurso)
        db.refresh(db_recurso.laboratorio)
        return db_recurso
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error al actualizar recurso: {e}")

@app.delete("/recursos/{recurso_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Gestión"])
def delete_recurso(recurso_id: int, user: AdminUser, db: DbSession):
    db_recurso = db.get(models.Recurso, recurso_id)
    if not db_recurso:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    prestamos_count = db.query(models.Prestamo).filter(models.Prestamo.recurso_id == recurso_id).count()
    if prestamos_count > 0:
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: hay {prestamos_count} préstamo(s) asociado(s).")
    try:
        db.delete(db_recurso)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno al eliminar recurso: {e}")

@app.get("/prestamos/mis-solicitudes", response_model=List[schemas.Prestamo], tags=["Préstamos"])
def get_mis_prestamos(user: CurrentUser, db: DbSession):
    prestamos = (
        db.query(models.Prestamo)
        .options(
            joinedload(models.Prestamo.recurso).joinedload(models.Recurso.laboratorio),
            joinedload(models.Prestamo.usuario),
        )
        .filter(models.Prestamo.usuario_id == user["id"])
        .order_by(models.Prestamo.id.desc())
        .all()
    )
    for p in prestamos:
        p.inicio = p.inicio.astimezone(timezone.utc)
        p.fin = p.fin.astimezone(timezone.utc)
        p.created_at = p.created_at.astimezone(timezone.utc)
    return prestamos

@app.post("/prestamos", response_model=schemas.Prestamo, status_code=status.HTTP_201_CREATED, tags=["Préstamos"])
async def create_prestamo(prestamo: schemas.PrestamoCreate, user: CurrentUser, db: DbSession):
    recurso = db.get(models.Recurso, prestamo.recurso_id)
    if not recurso:
        raise HTTPException(status_code=404, detail=f"Recurso id {prestamo.recurso_id} no encontrado.")
    if prestamo.usuario_id != user["id"] and user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="No autorizado para crear préstamo para otro usuario.")
    user_details = await _get_user_details_from_api(prestamo.usuario_id)
    if not user_details:
        raise HTTPException(status_code=404, detail=f"Usuario id {prestamo.usuario_id} no encontrado (via servicio_usuarios).")
    solicitante_nombre = user_details.get("nombre", "Usuario Desconocido")
    inicio = prestamo.inicio.astimezone(timezone.
