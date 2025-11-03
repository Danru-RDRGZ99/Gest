# 1. Empezar desde una imagen base ligera de Python
FROM python:3.11-slim

# 2. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Copiar el archivo de requerimientos
COPY requirements_usuarios.txt .

# 4. Instalar las dependencias
RUN pip install --no-cache-dir -r requirements_usuarios.txt

# 5. Copiar todo el código del servicio
COPY . .

# 6. Exponer el puerto en el que corre el servicio
EXPOSE 8001

# 7. El comando para iniciar el servidor (escuchando en 0.0.0.0)
CMD ["uvicorn", "main_usuarios:app", "--host", "0.0.0.0", "--port", "8001"]