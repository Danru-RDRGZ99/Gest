# Usar la imagen base de Nginx
FROM nginx:latest

# Eliminar la configuración por defecto
RUN rm /etc/nginx/conf.d/default.conf

# Copiar nuestra nueva configuración estática
COPY nginx.conf /etc/nginx/nginx.conf