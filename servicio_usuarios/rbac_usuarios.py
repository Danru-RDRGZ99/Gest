ALLOWED={
    "admin":["*"],
    "docente":["dashboard","recursos","reservas","ajustes"],
    "estudiante":["dashboard","recursos","ajustes"],
}

def is_route_allowed(role: str, route: str) -> bool:
    if role == "admin":
        return True  # <-- admin sin restricciones
    allowed = ALLOWED.get(role, set())
    return "*" in allowed or route in allowed