FROM nginx:1.29

# Borra cualquier conf previa para evitar que otra .conf se cargue además
RUN rm -f /etc/nginx/conf.d/default.conf || true

# Copia SOLO tu template (el que puse arriba)
COPY gateway/default.conf.template /etc/nginx/templates/default.conf.template
