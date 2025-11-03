# --- Standard FastAPI and SQLAlchemy Imports ---
from fastapi import FastAPI, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session, joinedload
from typing import List, Annotated, Optional
from datetime import timezone
import traceback
from db import engine
import models_inventario as models
# --- Configuración y Otros ---
from starlette.config import Config
import httpx # Importante: para llamadas entre servicios

# --- Project-specific Core Imports ---
from db import SessionLocal, get_db
import models_inventario as models
import security_inventario as security
import schemas_inventario as schemas

# --- Cargar Configuración ---
config = Config(".env")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="API de Servicio de Inventario",
    description="Servicio dedicado para gestionar planteles, laboratorios, recursos y préstamos.",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    print("INFO: Creando tablas de Inventario (si no existen)...")
    models.Base.metadata.create_all(bind=engine)
    print("INFO: Tablas de Inventario listas.")

# --- Database Dependency ---
DbSession = Annotated[Session, Depends(get_db)]

# --- Security Dependencies ---
CurrentUser = Annotated[dict, Depends(security.get_current_user)]
AdminUser = Annotated[dict, Depends(security.get_current_admin_user)]

# ==============================================================================
# --- HELPER: Service-to-Service Communication ---
# ==============================================================================

# Define las URLs de los otros servicios (deberían estar en .env)
USER_SERVICE_URL = config("USER_SERVICE_URL", default="http://localhost:8001")
RESERVA_SERVICE_URL = config("RESERVA_SERVICE_URL", default="http://localhost:8002")

async def _get_user_details_from_api(user_id: int) -> Optional[dict]:
    """Obtiene los detalles de un usuario llamando al servicio_usuarios."""
    try:
        async with httpx.AsyncClient() as client:
            # Asume un endpoint /usuarios/internal/{id} en servicio_usuarios
            response = await client.get(f"{USER_SERVICE_URL}/usuarios/internal/{user_id}")
            if response.status_code == 200:
                user_data = response.json()
                return {"correo": user_data.get("correo"), "nombre": user_data.get("nombre")}
            return None
    except httpx.RequestError as e:
        print(f"ERROR: No se pudo contactar a servicio_usuarios: {e}")
        return None

async def _get_reservas_count_from_api(lab_id: int) -> int:
    """Pregunta al servicio_reservas cuántas reservas activas tiene un lab."""
    try:
        async with httpx.AsyncClient() as client:
            # Asume un endpoint /reservas/{lab_id}/count en servicio_reservas
            response = await client.get(f"{RESERVA_SERVICE_URL}/reservas/{lab_id}/count")
            if response.status_code == 200:
                return response.json().get("active_count", 0)
            return 0 # Si falla la llamada, asumimos 0 (o podríamos bloquear)
    except httpx.RequestError as e:
        print(f"ERROR: No se pudo contactar a servicio_reservas: {e}")
        return -1 # Devuelve -1 para indicar error

# NOTA: Necesitarás añadir un endpoint /reservas/{lab_id}/count
# en `servicio_reservas` que devuelva el conteo.

# ==============================================================================
# --- PLANTELES ENDPOINTS (COMPLETOS) ---
# ==============================================================================

@app.get("/planteles", response_model=List[schemas.Plantel], tags=["Admin: Gestión"])
def get_all_planteles(user: CurrentUser, db: DbSession):
    return db.query(models.Plantel).order_by(models.Plantel.nombre.asc()).all()

@app.post("/planteles", response_model=schemas.Plantel, status_code=status.HTTP_201_CREATED, tags=["Admin: Gestión"])
def create_plantel(plantel: schemas.PlantelCreate, user: AdminUser, db: DbSession):
    new_plantel = models.Plantel(**plantel.model_dump()); db.add(new_plantel)
    try: 
        db.commit(); db.refresh(new_plantel); return new_plantel
    except Exception as e: 
        db.rollback(); raise HTTPException(status_code=400, detail=f"Error: {e}")

# --- ¡MODIFICACIÓN AÑADIDA! ---
@app.put("/planteles/{plantel_id}", response_model=schemas.Plantel, tags=["Admin: Gestión"])
def update_plantel(
    plantel_id: int, 
    plantel_update: schemas.PlantelCreate, 
    user: AdminUser, 
    db: DbSession
):
    db_plantel = db.get(models.Plantel, plantel_id)
    if not db_plantel:
        raise HTTPException(status_code=404, detail="Plantel no encontrado")
    
    # Actualiza los datos
    update_data = plantel_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_plantel, key, value)
    
    try:
        db.commit()
        db.refresh(db_plantel)
        return db_plantel
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error al actualizar plantel: {e}")

# --- ¡MODIFICACIÓN AÑADIDA! ---
@app.delete("/planteles/{plantel_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Gestión"])
def delete_plantel(plantel_id: int, user: AdminUser, db: DbSession):
    db_plantel = db.get(models.Plantel, plantel_id)
    if not db_plantel:
        raise HTTPException(status_code=404, detail="Plantel no encontrado")
    
    # Verifica si hay laboratorios asociados
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

# ==============================================================================
# --- LABORATORIOS ENDPOINTS (COMPLETOS) ---
# ==============================================================================

@app.get("/laboratorios", response_model=List[schemas.Laboratorio], tags=["Admin: Gestión"])
def get_all_laboratorios(user: CurrentUser, db: DbSession):
    return db.query(models.Laboratorio).options(joinedload(models.Laboratorio.plantel)).order_by(models.Laboratorio.id.desc()).all()

@app.post("/laboratorios", response_model=schemas.Laboratorio, status_code=status.HTTP_201_CREATED, tags=["Admin: Gestión"])
def create_laboratorio(lab: schemas.LaboratorioCreate, user: AdminUser, db: DbSession):
    plantel = db.get(models.Plantel, lab.plantel_id);
    if not plantel: raise HTTPException(status_code=404, detail=f"Plantel id {lab.plantel_id} no encontrado.")
    new_lab = models.Laboratorio(**lab.model_dump()); db.add(new_lab)
    try:
        db.commit(); db.refresh(new_lab)
        db.refresh(new_lab.plantel)
        return new_lab
    except Exception as e: 
        db.rollback(); raise HTTPException(status_code=400, detail=f"Error: {e}")

# --- ¡MODIFICACIÓN AÑADIDA! ---
@app.put("/laboratorios/{lab_id}", response_model=schemas.Laboratorio, tags=["Admin: Gestión"])
def update_laboratorio(
    lab_id: int, 
    lab_update: schemas.LaboratorioCreate, 
    user: AdminUser, 
    db: DbSession
):
    db_lab = db.get(models.Laboratorio, lab_id)
    if not db_lab:
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado")

    # Verifica si el plantel existe (si se está cambiando)
    if lab_update.plantel_id and not db.get(models.Plantel, lab_update.plantel_id):
        raise HTTPException(status_code=404, detail=f"Plantel id {lab_update.plantel_id} no encontrado.")

    # Actualiza los datos
    update_data = lab_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_lab, key, value)
    
    try:
        db.commit()
        db.refresh(db_lab)
        db.refresh(db_lab.plantel) # Refresca la relación
        return db_lab
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error al actualizar laboratorio: {e}")

@app.delete("/laboratorios/{lab_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Gestión"])
async def delete_laboratorio(lab_id: int, user: AdminUser, db: DbSession):
    db_lab = db.get(models.Laboratorio, lab_id);
    if not db_lab: raise HTTPException(status_code=404, detail="Laboratorio no encontrado")
    
    # Validaciones locales (propiedad de este servicio)
    recursos_count = db.query(models.Recurso).filter(models.Recurso.laboratorio_id == lab_id).count()
    if recursos_count > 0: 
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: hay {recursos_count} recurso(s) asociados.")
    
    # ! --- CAMBIO DE MICROSERVICIO --- !
    # Preguntamos al servicio_reservas si hay reservas
    reservas_count = await _get_reservas_count_from_api(lab_id)
    if reservas_count == -1:
        raise HTTPException(status_code=503, detail="No se pudo verificar el estado de las reservas. Intente de nuevo.")
    if reservas_count > 0: 
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: hay {reservas_count} reserva(s) asociada(s).")

    try:
        db.delete(db_lab); db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e: 
        db.rollback(); raise HTTPException(status_code=500, detail=f"Error: {e}")

# ==============================================================================
# --- RECURSOS ENDPOINTS (COMPLETOS) ---
# ==============================================================================

@app.get("/recursos", response_model=List[schemas.Recurso], tags=["Recursos"])
def get_recursos_filtrados(
    user: CurrentUser, db: DbSession, plantel_id: Optional[int] = None, lab_id: Optional[int] = None, estado: Optional[str] = None, tipo: Optional[str] = None
):
    q = db.query(models.Recurso)
    if lab_id: q = q.filter(models.Recurso.laboratorio_id == lab_id)
    elif plantel_id:
        lab_ids_subquery = db.query(models.Laboratorio.id).filter(models.Laboratorio.plantel_id == plantel_id).subquery()
        q = q.filter(models.Recurso.laboratorio_id.in_(lab_ids_subquery))
    if estado: q = q.filter(models.Recurso.estado == estado)
    if tipo: q = q.filter(models.Recurso.tipo == tipo)
    q = q.options(joinedload(models.Recurso.laboratorio).joinedload(models.Laboratorio.plantel))
    return q.order_by(models.Recurso.id.desc()).all()

@app.get("/recursos/tipos", response_model=List[str], tags=["Recursos"])
def get_recurso_tipos(user: CurrentUser, db: DbSession):
    tipos = db.query(models.Recurso.tipo).distinct().order_by(models.Recurso.tipo).all()
    return [tipo[0] for tipo in tipos if tipo and tipo[0] and tipo[0].strip()]

@app.post("/recursos", response_model=schemas.Recurso, status_code=status.HTTP_201_CREATED, tags=["Admin: Gestión"])
def create_recurso(recurso: schemas.RecursoCreate, user: AdminUser, db: DbSession):
    lab = db.get(models.Laboratorio, recurso.laboratorio_id)
    if not lab: raise HTTPException(status_code=404, detail="Laboratorio id no encontrado.")
    new_recurso = models.Recurso(**recurso.model_dump()); db.add(new_recurso)
    try:
        db.commit(); db.refresh(new_recurso); db.refresh(new_recurso.laboratorio)
        return new_recurso
    except Exception as e: 
        db.rollback(); raise HTTPException(status_code=400, detail=f"Error al crear recurso: {e}")

# --- ¡MODIFICACIÓN AÑADIDA! ---
@app.put("/recursos/{recurso_id}", response_model=schemas.Recurso, tags=["Admin: Gestión"])
def update_recurso(
    recurso_id: int, 
    recurso_update: schemas.RecursoCreate, # Usa el Create schema para recibir datos
    user: AdminUser, 
    db: DbSession
):
    db_recurso = db.get(models.Recurso, recurso_id)
    if not db_recurso:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    
    # Verifica si el lab existe
    if recurso_update.laboratorio_id and not db.get(models.Laboratorio, recurso_update.laboratorio_id):
            raise HTTPException(status_code=404, detail=f"Laboratorio id {recurso_update.laboratorio_id} no encontrado.")
    
    update_data = recurso_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_recurso, key, value)
    
    try:
        db.commit()
        db.refresh(db_recurso)
        db.refresh(db_recurso.laboratorio) # Refresca la relación
        return db_recurso
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error al actualizar recurso: {e}")

@app.delete("/recursos/{recurso_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Gestión"])
def delete_recurso(recurso_id: int, user: AdminUser, db: DbSession):
    db_recurso = db.get(models.Recurso, recurso_id)
    if not db_recurso: raise HTTPException(status_code=404, detail="Recurso no encontrado")
    
    # Validación local (correcta, este servicio posee 'Prestamo')
    prestamos_count = db.query(models.Prestamo).filter(models.Prestamo.recurso_id == recurso_id).count()
    if prestamos_count > 0: 
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: hay {prestamos_count} préstamo(s) asociado(s).")
    try:
        db.delete(db_recurso); db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e: 
        db.rollback(); raise HTTPException(status_code=500, detail=f"Error interno al eliminar recurso: {e}")

# ==============================================================================
# --- PRÉSTAMOS ENDPOINTS (COMPLETOS) ---
# ==============================================================================

@app.get("/prestamos/mis-solicitudes", response_model=List[schemas.Prestamo], tags=["Préstamos"])
def get_mis_prestamos(user: CurrentUser, db: DbSession):
    # Lógica sin cambios, usa el ID del token JWT
    prestamos = db.query(models.Prestamo).options(
        joinedload(models.Prestamo.recurso).joinedload(models.Recurso.laboratorio), 
        joinedload(models.Prestamo.usuario)
    ).filter(models.Prestamo.usuario_id == user["id"]).order_by(models.Prestamo.id.desc()).all()
    
    for p in prestamos:
        p.inicio = p.inicio.astimezone(timezone.utc)
        p.fin = p.fin.astimezone(timezone.utc)
        p.created_at = p.created_at.astimezone(timezone.utc)
    return prestamos

@app.post("/prestamos", response_model=schemas.Prestamo, status_code=status.HTTP_201_CREATED, tags=["Préstamos"])
async def create_prestamo(prestamo: schemas.PrestamoCreate, user: CurrentUser, db: DbSession):
    recurso = db.get(models.Recurso, prestamo.recurso_id)
    if not recurso: raise HTTPException(status_code=404, detail=f"Recurso id {prestamo.recurso_id} no encontrado.")
    
    if prestamo.usuario_id != user["id"] and user["rol"] != "admin": 
        raise HTTPException(status_code=403, detail="No autorizado para crear préstamo para otro usuario.")

    # ! --- CAMBIO DE MICROSERVICIO --- !
    # Validamos que el usuario existe llamando al servicio_usuarios
    user_details = await _get_user_details_from_api(prestamo.usuario_id)
    if not user_details:
        raise HTTPException(status_code=404, detail=f"Usuario id {prestamo.usuario_id} no encontrado (via servicio_usuarios).")
    
    solicitante_nombre = user_details.get("nombre", "Usuario Desconocido")

    inicio = prestamo.inicio.astimezone(timezone.utc)
    fin = prestamo.fin.astimezone(timezone.utc)
    
    new_prestamo = models.Prestamo(
        recurso_id=prestamo.recurso_id, 
        usuario_id=prestamo.usuario_id, 
        solicitante=solicitante_nombre, # Usamos el nombre de la API
        cantidad=prestamo.cantidad, 
        inicio=inicio, 
        fin=fin, 
        comentario=prestamo.comentario, 
        estado="pendiente"
    )
    db.add(new_prestamo)
    try:
        db.commit(); db.refresh(new_prestamo)
        db.refresh(new_prestamo.recurso); db.refresh(new_prestamo.usuario)
        
        new_prestamo.inicio = new_prestamo.inicio.astimezone(timezone.utc)
        new_prestamo.fin = new_prestamo.fin.astimezone(timezone.utc)
        new_prestamo.created_at = new_prestamo.created_at.astimezone(timezone.utc)
        return new_prestamo
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=400, detail=f"Error al crear préstamo: {e}")

@app.get("/admin/prestamos", response_model=List[schemas.Prestamo], tags=["Préstamos (Admin)"])
def get_todos_los_prestamos(user: AdminUser, db: DbSession):
    # Lógica sin cambios
    prestamos = db.query(models.Prestamo).options(
        joinedload(models.Prestamo.recurso), 
        joinedload(models.Prestamo.usuario)
    ).order_by(models.Prestamo.id.desc()).all()
    
    for p in prestamos:
        p.inicio = p.inicio.astimezone(timezone.utc)
        p.fin = p.fin.astimezone(timezone.utc)
        p.created_at = p.created_at.astimezone(timezone.utc)
    return prestamos

@app.put("/admin/prestamos/{prestamo_id}/estado", response_model=schemas.Prestamo, tags=["Préstamos (Admin)"])
def update_prestamo_estado(prestamo_id: int, nuevo_estado: str, user: AdminUser, db: DbSession):
    # Lógica sin cambios
    prestamo = db.query(models.Prestamo).options(joinedload(models.Prestamo.recurso)).filter(models.Prestamo.id == prestamo_id).first()
    if not prestamo: raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    
    # --- ¡MODIFICACIÓN AÑADIDA! ---
    # (Lógica de transición de estado)
    allowed_states = {"aprobado", "rechazado", "entregado", "devuelto"}
    if nuevo_estado not in allowed_states:
        raise HTTPException(status_code=400, detail=f"Estado '{nuevo_estado}' no permitido")

    current_status = prestamo.estado
    recurso = prestamo.recurso # Recurso asociado

    # Máquina de estados simple
    if current_status == "pendiente":
        if nuevo_estado not in ["aprobado", "rechazado"]:
            raise HTTPException(status_code=409, detail=f"No se puede cambiar de '{current_status}' a '{nuevo_estado}'")
    
    elif current_status == "aprobado":
        if nuevo_estado != "entregado":
            raise HTTPException(status_code=409, detail=f"No se puede cambiar de '{current_status}' a '{nuevo_estado}'")
        recurso.estado = "prestado" # El recurso sale de inventario
    
    elif current_status == "entregado":
        if nuevo_estado != "devuelto":
            raise HTTPException(status_code=409, detail=f"No se puede cambiar de '{current_status}' a '{nuevo_estado}'")
        recurso.estado = "disponible" # El recurso vuelve a inventario
    
    elif current_status in ["devuelto", "rechazado"]:
        raise HTTPException(status_code=409, detail=f"El préstamo ya está en un estado final ('{current_status}')")

    prestamo.estado = nuevo_estado
    # --- FIN DE LA MODIFICACIÓN ---
    
    try:
        db.commit(); db.refresh(prestamo)
        db.refresh(prestamo.recurso); db.refresh(prestamo.usuario)
        
        prestamo.inicio = prestamo.inicio.astimezone(timezone.utc)
        prestamo.fin = prestamo.fin.astimezone(timezone.utc)
        prestamo.created_at = prestamo.created_at.astimezone(timezone.utc)
        return prestamo
    except Exception as e:

        db.rollback(); raise HTTPException(status_code=500, detail=f"Error al actualizar estado: {e}")
