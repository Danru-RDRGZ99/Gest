FROM python:3.11-slim
WORKDIR /app

COPY servicio_usuarios/requirements_usuarios.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY servicio_usuarios/ /app/
ENV PYTHONUNBUFFERED=1

# Falla si $PORT no está (así no despliega mal)
CMD test -n "$PORT" || (echo "ERROR: PORT no está definido" && exit 1); \
    uvicorn main_usuarios:app --host 0.0.0.0 --port "$PORT"
