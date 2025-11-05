# 1. Usar la imagen base de Nginx
FROM nginx:latest

# --- ¡SOLUCIÓN PARA ROMPER LA CACHÉ! ---
# 2. Esta línea le dice a Docker que no use la caché
#    para los siguientes pasos. Es un "argumento" que
#    cambia cada vez que haces un build.
ARG CACHE_BUSTER=refrescar

# 3. Eliminar la configuración por defecto
RUN rm /etc/nginx/conf.d/default.conf

# 4. Copiar nuestra nueva configuración estática
#    Como el paso 2 es nuevo, Docker se verá forzado a
#    re-ejecutar este COPY, copiando tu NUEVO nginx.conf.
COPY nginx.conf /etc/nginx/nginx.conf