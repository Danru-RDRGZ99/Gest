# 1. Usar la imagen base de Nginx
FROM nginx:latest

# 2. Eliminar la configuración por defecto
RUN rm /etc/nginx/conf.d/default.conf

# 3. Copiar nuestra configuración estática de Railway
COPY nginx.conf /etc/nginx/nginx.conf