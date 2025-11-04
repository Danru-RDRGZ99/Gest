FROM nginx:latest

# Borra la config por defecto
RUN rm /etc/nginx/conf.d/default.conf

# Copia TU plantilla (con el nombre corregido)
COPY nginx.conf.template /etc/nginx/nginx.conf.template

# Copia el script que acabas de crear
COPY docker-entrypoint.sh /docker-entrypoint.sh

# Dale permisos
RUN chmod +x /docker-entrypoint.sh

# Ejecútalo al arrancar
ENTRYPOINT ["/docker-entrypoint.sh"]
