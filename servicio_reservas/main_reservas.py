# --- Standard FastAPI and SQLAlchemy Imports ---
from fastapi import FastAPI, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session, joinedload
from typing import List, Annotated, Optional, Dict, Tuple
from datetime import datetime, timedelta, timezone, date, time
import traceback
from collections import defaultdict

# --- Configuración y Otros ---
from starlette.config import Config
import httpx # Importante: para llamadas entre servicios

# --- Project-specific Core Imports ---
from db import SessionLocal, get_db
import models_reservas as models
import security_reservas as security
import schemas_reservas as schemas
import calendar_service_reservas as calendar_service

# --- Cargar Configuración ---
config = Config(".env")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="API de Servicio de Reservas",
    description="Servicio dedicado para gestionar horarios, disponibilidad y reservas.",
    version="1.0.0"
)

# --- Database Dependency ---
DbSession = Annotated[Session, Depends(get_db)]

# --- Security Dependencies ---
CurrentUser = Annotated[dict, Depends(security.get_current_user)]
AdminUser = Annotated[dict, Depends(security.get_current_admin_user)]

# --- Caché de Laboratorios (Necesaria para lógica de negocio) ---
labs_cache_main = {}
def load_labs_cache():
    global labs_cache_main
    db = SessionLocal()
    try:
        # PRAGMATIC COMPROMISE: Leemos la tabla de laboratorios.
        labs = db.query(models.Laboratorio).all()
        labs_cache_main = {lab.id: lab for lab in labs}
        print("INFO: Cache de laboratorios (local read) cargada.")
    except Exception as e:
        print(f"ERROR: No se pudo cargar la caché de laboratorios: {e}")
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    models.Base.metadata.create_all(bind=engine)
    load_labs_cache()

# ==============================================================================
# --- HELPER: Service-to-Service Communication ---
# ==============================================================================

# Define la URL del servicio de usuarios (debería estar en .env)
USER_SERVICE_URL = config("USER_SERVICE_URL", default="http://localhost:8001")

async def _get_user_details_from_api(user_id: int) -> Optional[dict]:
    """
    Obtiene los detalles de un usuario (especialmente email y nombre)
    llamando al servicio_usuarios.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{USER_SERVICE_URL}/usuarios/internal/{user_id}")
            
            if response.status_code == 200:
                user_data = response.json()
                return {"correo": user_data.get("correo"), "nombre": user_data.get("nombre")}
            else:
                print(f"WARN: servicio_usuarios devolvió {response.status_code} para user_id {user_id}")
                return None
    except httpx.RequestError as e:
        print(f"ERROR: No se pudo contactar a servicio_usuarios en {USER_SERVICE_URL}: {e}")
        return None

# ==============================================================================
# --- ENDPOINTS DE GESTIÓN DE HORARIOS (ADMIN) ---
# ==============================================================================

@app.post("/admin/horarios/reglas", response_model=schemas.ReglaHorario, status_code=status.HTTP_201_CREATED, tags=["Admin: Horarios"])
def create_regla_horario(regla: schemas.ReglaHorarioCreate, user: AdminUser, db: DbSession):
    if not (0 <= regla.dia_semana <= 6): raise HTTPException(status_code=400, detail="dia_semana debe estar entre 0 (Lunes) y 6 (Domingo).")
    if regla.hora_inicio >= regla.hora_fin: raise HTTPException(status_code=400, detail="hora_inicio debe ser anterior a hora_fin.")
    db_regla = models.ReglaHorario(**regla.model_dump())
    try:
        db.add(db_regla); db.commit(); db.refresh(db_regla)
        return db_regla
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"Error al crear regla: {e}")

# --- ¡MODIFICACIÓN AÑADIDA! (Corrección 405) ---
@app.get("/admin/horarios/reglas", response_model=List[schemas.ReglaHorario], tags=["Admin: Horarios"])
def get_reglas(user: AdminUser, db: DbSession, laboratorio_id: Optional[int] = None):
    query = db.query(models.ReglaHorario)
    if laboratorio_id is not None:
        query = query.filter(models.ReglaHorario.laboratorio_id == laboratorio_id)
    return query.order_by(models.ReglaHorario.laboratorio_id, models.ReglaHorario.dia_semana).all()

# --- ¡MODIFICACIÓN AÑADIDA! (Corrección 405) ---
@app.put("/admin/horarios/reglas/{regla_id}", response_model=schemas.ReglaHorario, tags=["Admin: Horarios"])
def update_regla(
    regla_id: int, 
    regla_data: schemas.ReglaHorarioUpdate,
    user: AdminUser, 
    db: DbSession
):
    db_regla = db.get(models.ReglaHorario, regla_id)
    if not db_regla:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    
    update_data = regla_data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No se enviaron datos para actualizar")

    if "hora_inicio" in update_data or "hora_fin" in update_data:
        inicio = update_data.get("hora_inicio", db_regla.hora_inicio)
        fin = update_data.get("hora_fin", db_regla.hora_fin)
        if inicio >= fin:
            raise HTTPException(status_code=400, detail="hora_inicio debe ser anterior a hora_fin.")

    for key, value in update_data.items():
        setattr(db_regla, key, value)
    
    try:
        db.commit(); db.refresh(db_regla); return db_regla
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=500, detail=f"Error al actualizar: {e}")

# --- ¡MODIFICACIÓN AÑADIDA! (Corrección 405) ---
@app.delete("/admin/horarios/reglas/{regla_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Horarios"])
def delete_regla(regla_id: int, user: AdminUser, db: DbSession):
    db_regla = db.get(models.ReglaHorario, regla_id)
    if not db_regla:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    try:
        db.delete(db_regla); db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=500, detail=f"Error al eliminar: {e}")

@app.post("/admin/horarios/excepciones", response_model=schemas.ExcepcionHorario, status_code=status.HTTP_201_CREATED, tags=["Admin: Horarios"])
def create_excepcion_horario(excepcion: schemas.ExcepcionHorarioCreate, user: AdminUser, db: DbSession):
    if (excepcion.hora_inicio and not excepcion.hora_fin) or (not excepcion.hora_inicio and excepcion.hora_fin):
        raise HTTPException(status_code=400, detail="Debe especificar ambas horas (inicio y fin) o ninguna (para todo el día).")
    if excepcion.hora_inicio and excepcion.hora_fin and excepcion.hora_inicio >= excepcion.hora_fin:
        raise HTTPException(status_code=400, detail="hora_inicio debe ser anterior a hora_fin.")
    db_excepcion = models.ExcepcionHorario(**excepcion.model_dump())
    try:
        db.add(db_excepcion); db.commit(); db.refresh(db_excepcion)
        return db_excepcion
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"Error al crear excepción: {e}")

# --- ¡MODIFICACIÓN AÑADIDA! (Corrección 405) ---
@app.get("/admin/horarios/excepciones", response_model=List[schemas.ExcepcionHorario], tags=["Admin: Horarios"])
def get_excepciones(user: AdminUser, db: DbSession, laboratorio_id: Optional[int] = None):
    query = db.query(models.ExcepcionHorario)
    if laboratorio_id is not None:
        query = query.filter(models.ExcepcionHorario.laboratorio_id == laboratorio_id)
    return query.order_by(models.ExcepcionHorario.fecha.desc()).all()

# --- ¡MODIFICACIÓN AÑADIDA! (Corrección 405) ---
@app.put("/admin/horarios/excepciones/{excepcion_id}", response_model=schemas.ExcepcionHorario, tags=["Admin: Horarios"])
def update_excepcion(
    excepcion_id: int,
    excepcion_data: schemas.ExcepcionHorarioUpdate,
    user: AdminUser,
    db: DbSession
):
    db_excepcion = db.get(models.ExcepcionHorario, excepcion_id)
    if not db_excepcion:
        raise HTTPException(status_code=404, detail="Excepción no encontrada")

    update_data = excepcion_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_excepcion, key, value)
    
    try:
        db.commit(); db.refresh(db_excepcion); return db_excepcion
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=500, detail=f"Error al actualizar excepción: {e}")

# --- ¡MODIFICACIÓN AÑADIDA! (Corrección 405) ---
@app.delete("/admin/horarios/excepciones/{excepcion_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Horarios"])
def delete_excepcion(excepcion_id: int, user: AdminUser, db: DbSession):
    db_excepcion = db.get(models.ExcepcionHorario, excepcion_id)
    if not db_excepcion:
        raise HTTPException(status_code=404, detail="Excepción no encontrada")
    try:
        db.delete(db_excepcion); db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=500, detail=f"Error al eliminar excepción: {e}")


# ==============================================================================
# --- ENDPOINT PARA OBTENER RESERVAS POR LABORATORIO ---
# ==============================================================================

@app.get("/reservas/{lab_id}", response_model=List[schemas.Reserva], tags=["Reservas"])
def get_reservas_por_lab_y_fecha(
    lab_id: int,
    start_dt: date,
    end_dt: date,
    user: CurrentUser,
    db: DbSession
):
    lab = labs_cache_main.get(lab_id) or db.get(models.Laboratorio, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado")

    try:
        # --- LÓGICA CORREGIDA ---
        # El frontend envía fechas 'naive', las convertimos a UTC para la consulta
        start_dt_utc = datetime.combine(start_dt, time.min).astimezone(timezone.utc)
        # Para el final, tomamos el final del día
        end_dt_utc = datetime.combine(end_dt, time.max).astimezone(timezone.utc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fechas inválidas: {e}")

    reservas_db = db.query(models.Reserva).options(
        joinedload(models.Reserva.usuario)
    ).filter(
        models.Reserva.laboratorio_id == lab_id,
        models.Reserva.estado != "cancelada",
        # --- LÓGICA CORREGIDA (Solapamiento de rangos) ---
        models.Reserva.inicio <= end_dt_utc, # Inicia ANTES de que termine el rango
        models.Reserva.fin >= start_dt_utc   # Termina DESPUÉS de que comience el rango
    ).order_by(models.Reserva.inicio.asc()).all()

    # Aseguramos que todas las fechas devueltas sean UTC
    for r in reservas_db:
            r.inicio = r.inicio.astimezone(timezone.utc)
            r.fin = r.fin.astimezone(timezone.utc)

    return reservas_db

# --- ¡MODIFICACIÓN AÑADIDA! (Endpoint faltante de api_client) ---
@app.get("/reservas/mis-reservas", response_model=List[schemas.Reserva], tags=["Reservas"])
def get_mis_reservas(user: CurrentUser, db: DbSession):
    user_id = user["id"]
    reservas_db = db.query(models.Reserva).options(
        joinedload(models.Reserva.usuario)
    ).filter(
        models.Reserva.usuario_id == user_id
    ).order_by(models.Reserva.inicio.desc()).all()

    for r in reservas_db:
            r.inicio = r.inicio.astimezone(timezone.utc)
            r.fin = r.fin.astimezone(timezone.utc)

    return reservas_db

# --- ¡MODIFICACIÓN AÑADIDA! (Endpoint faltante para Inventario) ---
@app.get("/reservas/{lab_id}/count", response_model=dict, tags=["Internal"])
def get_reservas_count_for_lab(lab_id: int, db: DbSession):
    count = db.query(models.Reserva).filter(
        models.Reserva.laboratorio_id == lab_id,
        models.Reserva.estado.in_(["activa"]), # Solo contar activas
        models.Reserva.fin > datetime.now(timezone.utc) # Que estén en el futuro
    ).count()
    
    return {"lab_id": lab_id, "active_count": count}

# ==============================================================================
# --- ENDPOINT PARA CALCULAR HORARIO DISPONIBLE ---
# ==============================================================================

# --- ¡LÓGICA DE PLACEHOLDER ELIMINADA Y REEMPLAZADA! ---
@app.get("/laboratorios/{lab_id}/horario", response_model=Dict[str, List[schemas.SlotHorario]], tags=["Reservas"])
def get_horario_laboratorio(
    lab_id: int, fecha_inicio: date, fecha_fin: date, user: CurrentUser, db: DbSession
):
    lab = db.get(models.Laboratorio, lab_id)
    if not lab: raise HTTPException(status_code=404, detail="Laboratorio no encontrado")
    
    # 1. Obtener todas las reglas y excepciones relevantes de una sola vez
    reglas_generales_q = db.query(models.ReglaHorario).filter(models.ReglaHorario.laboratorio_id == None).all()
    reglas_especificas_q = db.query(models.ReglaHorario).filter(models.ReglaHorario.laboratorio_id == lab_id).all()
    
    excepciones_q = db.query(models.ExcepcionHorario).filter(
        models.ExcepcionHorario.fecha >= fecha_inicio,
        models.ExcepcionHorario.fecha <= fecha_fin,
        (models.ExcepcionHorario.laboratorio_id == lab_id) | (models.ExcepcionHorario.laboratorio_id == None)
    ).all()

    # Mapear para búsqueda rápida
    reglas_generales = defaultdict(list)
    for r in reglas_generales_q: reglas_generales[r.dia_semana].append(r)
    
    reglas_especificas = defaultdict(list)
    for r in reglas_especificas_q: reglas_especificas[r.dia_semana].append(r)
    
    excepciones_por_fecha = defaultdict(list)
    for e in excepciones_q: excepciones_por_fecha[e.fecha].append(e)

    horario_final: Dict[str, List[schemas.SlotHorario]] = {}
    current_date = fecha_inicio

    while current_date <= fecha_fin:
        dia_semana = current_date.weekday()
        slots_del_dia: List[schemas.SlotHorario] = []

        # 2. Revisar Excepciones para este día
        excepciones_hoy = excepciones_por_fecha.get(current_date, [])
        excepcion_especifica = next((e for e in excepciones_hoy if e.laboratorio_id == lab_id), None)
        excepcion_general = next((e for e in excepciones_hoy if e.laboratorio_id == None), None)
        
        excepcion_a_usar = excepcion_especifica if excepcion_especifica else excepcion_general

        if excepcion_a_usar:
            if not excepcion_a_usar.es_habilitado and excepcion_a_usar.hora_inicio is None:
                # Excepción de DÍA COMPLETO CERRADO
                horario_final[current_date.isoformat()] = [
                    schemas.SlotHorario(
                        inicio=datetime.combine(current_date, time.min),
                        fin=datetime.combine(current_date, time.max),
                        tipo=excepcion_a_usar.descripcion or "no_habilitado"
                    )
                ]
                current_date += timedelta(days=1)
                continue
            
            # (Aquí iría lógica más compleja para excepciones de medio día,
            # por ahora, priorizamos las reglas si la excepción no es de día completo)

        # 3. Determinar qué conjunto de reglas usar
        reglas_a_usar = reglas_especificas.get(dia_semana, [])
        if not reglas_a_usar: # Si no hay específicas, usar generales
            reglas_a_usar = reglas_generales.get(dia_semana, [])

        # 4. Generar Slots base a partir de las reglas
        if not reglas_a_usar:
            # No hay reglas para este día
            slots_del_dia = [schemas.SlotHorario(
                inicio=datetime.combine(current_date, time.min),
                fin=datetime.combine(current_date, time.max),
                tipo="no_habilitado"
            )]
        else:
            for regla in sorted(reglas_a_usar, key=lambda r: r.hora_inicio):
                tipo = regla.tipo_intervalo if regla.es_habilitado else "no_habilitado"
                slots_del_dia.append(schemas.SlotHorario(
                    inicio=datetime.combine(current_date, regla.hora_inicio),
                    fin=datetime.combine(current_date, regla.hora_fin),
                    tipo=tipo
                ))
        
        horario_final[current_date.isoformat()] = slots_del_dia
        current_date += timedelta(days=1)
        
    return horario_final

# ==============================================================================
# --- RESERVATION ENDPOINTS (MODIFICADOS) ---
# ==============================================================================

@app.post("/reservas", response_model=schemas.Reserva, status_code=status.HTTP_201_CREATED, tags=["Reservas"])
async def create_reserva(reserva: schemas.ReservaCreate, user: CurrentUser, db: DbSession):
    # --- Validaciones ---
    if user.get("rol") not in ["admin", "docente"]: 
        raise HTTPException(status_code=403, detail="Solo admins/docentes pueden crear reservas.")
    
    lab = labs_cache_main.get(reserva.laboratorio_id) or db.get(models.Laboratorio, reserva.laboratorio_id)
    if not lab: raise HTTPException(status_code=404, detail=f"Laboratorio id {reserva.laboratorio_id} no encontrado.")

    user_details = await _get_user_details_from_api(reserva.usuario_id)
    if not user_details:
        raise HTTPException(status_code=404, detail=f"Usuario id {reserva.usuario_id} no encontrado (via servicio_usuarios).")
    
    user_email = user_details.get("correo")
    user_name = user_details.get("nombre", "Usuario")

    # El frontend envía fechas 'naive' (locales), las convertimos a UTC
    inicio = reserva.inicio.astimezone(timezone.utc)
    fin = reserva.fin.astimezone(timezone.utc)
    if inicio >= fin: raise HTTPException(status_code=400, detail="Inicio debe ser anterior a fin.")
    if inicio < datetime.now(timezone.utc): raise HTTPException(status_code=400, detail="No se pueden crear reservas en el pasado.")

    # --- Validación de Horario (Llama al endpoint local) ---
    try:
        # Llama a la lógica real de get_horario_laboratorio
        horario_dia_dict = get_horario_laboratorio(lab_id=reserva.laboratorio_id, fecha_inicio=inicio.date(), fecha_fin=inicio.date(), user=user, db=db)
        slots_disponibles = horario_dia_dict.get(inicio.date().isoformat(), [])
        
        slot_valido_encontrado = False
        for slot in slots_disponibles:
            # Comprueba si el slot de la regla coincide EXACTAMENTE con la reserva
            # Y si el tipo es "disponible"
            if (slot.inicio == reserva.inicio and 
                slot.fin == reserva.fin and 
                slot.tipo == "disponible"):
                slot_valido_encontrado = True
                break
        
        if not slot_valido_encontrado:
                raise HTTPException(status_code=409, detail="El horario solicitado no está disponible o no coincide con un slot exacto.")
    except HTTPException as http_ex: raise http_ex
    except Exception as val_ex: raise HTTPException(status_code=500, detail=f"Error al validar disponibilidad: {val_ex}")

    # --- ¡MODIFICACIÓN CORREGIDA! (Comprobar solapamiento) ---
    overlapping = db.query(models.Reserva).filter(
        models.Reserva.laboratorio_id == reserva.laboratorio_id,
        models.Reserva.estado != "cancelada",
        models.Reserva.inicio < fin, # Inicia antes de que la nueva termine
        models.Reserva.fin > inicio    # Termina después de que la nueva inicie
    ).first()
    if overlapping: 
        raise HTTPException(status_code=409, detail=f"Conflicto de horario detectado con la reserva ID {overlapping.id}.")

    # --- Crear Reserva y Evento Calendar ---
    new_reserva = models.Reserva(usuario_id=reserva.usuario_id, laboratorio_id=reserva.laboratorio_id, inicio=inicio, fin=fin, estado="activa", google_event_id=None)
    google_event_id = None
    try:
        db.add(new_reserva); db.commit(); db.refresh(new_reserva)
        
        try:
            lab_name = lab.nombre
            lab_location = getattr(lab, 'ubicacion', '')
            
            summary = f"Reserva Lab: {lab_name} - {user_name}"
            description = f"Reserva ID Local: {new_reserva.id}\nUsuario: {user_name} (ID: {new_reserva.usuario_id})"

            google_event_id = calendar_service.create_calendar_event(
                summary=summary,
                start_time=new_reserva.inicio, # Pasa UTC
                end_time=new_reserva.fin,     # Pasa UTC
                description=description,
                location=lab_location
            )

            if google_event_id:
                new_reserva.google_event_id = google_event_id; db.commit(); db.refresh(new_reserva)
            
        except Exception as calendar_e: 
            print(f"ERROR: Falló la creación/actualización del evento en Google Calendar: {calendar_e}")

        new_reserva.inicio = new_reserva.inicio.astimezone(timezone.utc)
        new_reserva.fin = new_reserva.fin.astimezone(timezone.utc)
        
        db.refresh(new_reserva.usuario) # Carga los datos del usuario para la respuesta
        return new_reserva
        
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=400, detail=f"Error al crear reserva local: {e}")

@app.put("/reservas/{reserva_id}/cancelar", response_model=schemas.Reserva, tags=["Reservas"])
def cancel_reserva(reserva_id: int, user: CurrentUser, db: DbSession):
    reserva = db.get(models.Reserva, reserva_id)
    if not reserva: raise HTTPException(status_code=404, detail="Reserva no encontrada")
    if user["rol"] != 'admin' and reserva.usuario_id != user["id"]: 
        raise HTTPException(status_code=403, detail="No autorizado")
    
    if reserva.estado == "cancelada":
        raise HTTPException(status_code=409, detail="La reserva ya estaba cancelada.")

    google_event_id_to_delete = getattr(reserva, 'google_event_id', None)
    reserva.estado = "cancelada"
    
    try:
        db.commit(); db.refresh(reserva)
        if google_event_id_to_delete:
            try:
                calendar_service.delete_calendar_event(google_event_id_to_delete)
                reserva.google_event_id = None; db.commit(); db.refresh(reserva)
            except Exception as calendar_e: 
                print(f"ERROR: Falló la eliminación del evento en Google Calendar: {calendar_e}")

        reserva.inicio = reserva.inicio.astimezone(timezone.utc)
        reserva.fin = reserva.fin.astimezone(timezone.utc)
        
        db.refresh(reserva.usuario) # Carga los datos del usuario
        return reserva
    except Exception as e:

        db.rollback(); raise HTTPException(status_code=500, detail=f"Error al cancelar reserva local: {e}")
