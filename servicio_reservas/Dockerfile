# 1. Empezar desde una imagen base ligera de Python
FROM python:3.11-slim

# 2. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Copiar el archivo de requerimientos (desde la subcarpeta correcta)
COPY servicio_reservas/requirements_reservas.txt .

# 4. Instalar las dependencias
RUN pip install --no-cache-dir -r requirements_reservas.txt

# 5. Copiar todo el código del servicio (solo esta subcarpeta)
COPY servicio_reservas/ .

# 6. Exponer el puerto que Railway nos dará (opcional pero buena práctica)
EXPOSE $PORT

# 7. El comando para iniciar el servidor (USANDO $PORT, NO 8002)
CMD ["uvicorn", "main_reservas:app", "--host", "0.0.0.0", "--port", "$PORT"]