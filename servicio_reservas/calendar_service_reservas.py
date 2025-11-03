import os
import datetime
import pytz # Para zonas horarias
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv() # Carga las variables de .env

# Configuración desde .env
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
LOCAL_TIMEZONE_STR = os.getenv("LOCAL_TIMEZONE", "UTC") # Default a UTC si no está en .env
try:
    LOCAL_TIMEZONE = pytz.timezone(LOCAL_TIMEZONE_STR)
except pytz.exceptions.UnknownTimeZoneError:
    print(f"WARN: Zona horaria '{LOCAL_TIMEZONE_STR}' desconocida. Usando UTC.")
    LOCAL_TIMEZONE_STR = "UTC"
    LOCAL_TIMEZONE = pytz.utc


# Alcance necesario para la API de Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def _get_calendar_service():
    """Autentica con la cuenta de servicio y devuelve el cliente de la API."""
    if not SERVICE_ACCOUNT_FILE:
        print("ERROR: GOOGLE_SERVICE_ACCOUNT_FILE no está definido en .env")
        return None
        
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('calendar', 'v3', credentials=creds)
        return service
    except FileNotFoundError:
        print(f"ERROR: No se encontró el archivo de credenciales: {SERVICE_ACCOUNT_FILE}")
        return None
    except Exception as e:
        print(f"ERROR al autenticar con Google Calendar: {e}")
        return None

def create_calendar_event(summary: str, start_time: datetime.datetime, end_time: datetime.datetime, description: str = "", location: str = ""):
    """Crea un evento en el Google Calendar configurado."""
    service = _get_calendar_service()
    if not service or not CALENDAR_ID:
        print("ERROR: Servicio de calendario o ID no configurados (verifica .env y credenciales).")
        return None # Falló la creación

    # Asegurarse de que las fechas tengan zona horaria correcta para Google
    start_time_aware = LOCAL_TIMEZONE.localize(start_time) if start_time.tzinfo is None else start_time.astimezone(LOCAL_TIMEZONE)
    end_time_aware = LOCAL_TIMEZONE.localize(end_time) if end_time.tzinfo is None else end_time.astimezone(LOCAL_TIMEZONE)

    event = {
        'summary': summary,
        'location': location,
        'description': description,
        'start': {
            'dateTime': start_time_aware.isoformat(), # Formato RFC3339 requerido
            'timeZone': LOCAL_TIMEZONE_STR,
        },
        'end': {
            'dateTime': end_time_aware.isoformat(), # Formato RFC3339 requerido
            'timeZone': LOCAL_TIMEZONE_STR,
        },
        # Puedes añadir más detalles aquí si quieres (ej. attendees, reminders)
    }

    try:
        print(f"INFO: Creando evento en Google Calendar: '{summary}'")
        created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        event_id = created_event.get('id')
        print(f"INFO: Evento creado: {created_event.get('htmlLink')} (ID: {event_id})")
        return event_id # Devuelve el ID del evento creado
    except HttpError as error:
        print(f"ERROR al crear evento en Google Calendar: {error}")
        return None # Falló la creación
    except Exception as e:
        print(f"ERROR inesperado al crear evento: {e}")
        return None

# --- Opcional: Función para cancelar/eliminar evento ---
def delete_calendar_event(event_id: str):
    """Elimina un evento del Google Calendar usando su ID."""
    service = _get_calendar_service()
    if not service or not CALENDAR_ID or not event_id:
        print("ERROR: Servicio, ID de calendario o ID de evento no proporcionados.")
        return False

    try:
        print(f"INFO: Eliminando evento de Google Calendar: ID={event_id}")
        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
        print("INFO: Evento eliminado exitosamente.")
        return True
    except HttpError as error:
        # Si el evento ya no existe, Google devuelve 404 o 410, lo cual no es un error fatal aquí
        if error.resp.status in [404, 410]:
             print(f"WARN: El evento {event_id} no se encontró en Google Calendar (posiblemente ya eliminado).")
             return True # Considerarlo éxito si no se encontró
        else:
             print(f"ERROR al eliminar evento {event_id} de Google Calendar: {error}")
             return False
    except Exception as e:
        print(f"ERROR inesperado al eliminar evento {event_id}: {e}")
        return False