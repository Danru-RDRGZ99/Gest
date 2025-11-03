ALLOWED={
    "admin":["dashboard","planteles","laboratorios","recursos","reservas","usuarios"],
    "docente":["dashboard","recursos","reservas","ajustes"],
    "estudiante":["dashboard","recursos","ajustes"],
}
def allowed_routes(role:str):
    return ALLOWED.get(role,["dashboard"])
