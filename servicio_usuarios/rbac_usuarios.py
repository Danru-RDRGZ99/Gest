from typing import List

ROUTES = {
    "root": "/",
    "dashboard": "/dashboard",
    "ajustes": "/ajustes",
    "prestamos": "/prestamos",
    "planteles": "/planteles",
    "laboratorios": "/laboratorios",
    "usuarios": "/usuarios",
    "captcha-request": "/captcha",
    "captcha-verify": "/captcha-verify",
}

def allowed_routes(role: str) -> List[str]:
    if role == "admin":
        return list(ROUTES.values())
    if role == "docente":
        return [ROUTES["dashboard"], ROUTES["prestamos"], ROUTES["laboratorios"], ROUTES["planteles"]]
    if role == "estudiante":
        return [ROUTES["dashboard"], ROUTES["prestamos"]]
    return [ROUTES["root"]]
