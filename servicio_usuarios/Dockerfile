# 1. Empezar desde una imagen base ligera de Python
FROM python:3.11-slim

# 2. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Copiar el archivo de requerimientos (desde la subcarpeta correcta)
COPY servicio_usuarios/requirements_usuarios.txt .

# 4. Instalar las dependencias
RUN pip install --no-cache-dir -r requirements_usuarios.txt

# 5. Copiar todo el código del servicio (solo esta subcarpeta)
COPY servicio_usuarios/ .

# 6. Exponer el puerto que Railway nos dará (opcional pero buena práctica)
EXPOSE $PORT

# 7. El comando para iniciar el servidor (USANDO $PORT, NO 8001)
CMD ["uvicorn", "main_usuarios:app", "--host", "0.0.0.0", "--port", "$PORT"]