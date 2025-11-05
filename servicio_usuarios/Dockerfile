FROM python:3.11-slim
WORKDIR /app
COPY servicio_usuarios/requirements_usuarios.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY servicio_usuarios/ .
ENV PYTHONUNBUFFERED=1
CMD ["sh","-c","uvicorn main_usuarios:app --host 0.0.0.0 --port ${PORT:-8001}"]
