# Archivo: GEST/nginx/Dockerfile

# Usar la imagen oficial de Nginx
FROM nginx:latest

# Borrar la configuración por defecto
RUN rm /etc/nginx/conf.d/default.conf

# Copiar nuestra configuración personalizada
COPY nginx.conf /etc/nginx/nginx.conf