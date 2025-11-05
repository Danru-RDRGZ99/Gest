# 1. Imagen base ligera
FROM python:3.11-slim

# 2. Directorio de trabajo
WORKDIR /app

# 3. Requerimientos
COPY servicio_inventario/requirements_inventario.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 4. Código del servicio
COPY servicio_inventario/ .

# 5. (Opcional) Ajustes de runtime
ENV PYTHONUNBUFFERED=1

# 6. Comando: escuchar en $PORT (Railway lo inyecta). Fallback local 8003.
CMD ["sh", "-c", "uvicorn main_inventario:app --host 0.0.0.0 --port ${PORT:-8003}"]
