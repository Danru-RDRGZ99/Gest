FROM nginx:1.29-alpine

# Elimina cualquier conf previa
RUN rm -f /etc/nginx/conf.d/default.conf || true \
 && rm -rf /etc/nginx/templates || true

# Copia un default.conf FINAL (no plantilla)
COPY gateway/default.conf /etc/nginx/conf.d/default.conf
