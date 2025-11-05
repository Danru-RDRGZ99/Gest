# 1. Empezar desde una imagen base ligera de Python
FROM python:3.11-slim

# 2. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Copiar el archivo de requerimientos (desde la subcarpeta correcta)
COPY servicio_inventario/requirements_inventario.txt .

# 4. Instalar las dependencias
RUN pip install --no-cache-dir -r requirements_inventario.txt

# 5. Copiar todo el código del servicio (solo esta subcarpeta)
COPY servicio_inventario/ .

# 6. Exponer el puerto que Railway nos dará (opcional pero buena práctica)
EXPOSE $PORT

# 7. El comando para iniciar el servidor (USANDO $PORT, NO 8003)
CMD ["uvicorn", "main_inventario:app", "--host", "0.0.0.0", "--port", "$PORT"]