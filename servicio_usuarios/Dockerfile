FROM python:3.11-slim
WORKDIR /app
# Asegúrate de que esta ruta es correcta
COPY servicio_usuarios/requirements_usuarios.txt .
RUN pip install --no-cache-dir -r requirements_usuarios.txt
# Asegúrate de que esta ruta es correcta
COPY servicio_usuarios/ .
EXPOSE $PORT
# Asegúrate de que usa $PORT
CMD uvicorn main_usuarios:app --host 0.0.0.0 --port $PORT