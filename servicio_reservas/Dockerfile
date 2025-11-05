# 1) Imagen base ligera
FROM python:3.11-slim

# 2) Directorio de trabajo
WORKDIR /app

# 3) Instalar dependencias
COPY servicio_reservas/requirements_reservas.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 4) Copiar el código del servicio
COPY servicio_reservas/ .

# 5) Log sin buffer (útil en contenedores)
ENV PYTHONUNBUFFERED=1

# 6) Arranque: usa $PORT de Railway (fallback local 8002)
CMD ["sh", "-c", "uvicorn main_reservas:app --host 0.0.0.0 --port ${PORT:-8002}"]
