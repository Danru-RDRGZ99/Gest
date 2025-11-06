FROM nginx:1.25-alpine

# Copiamos la plantilla que envsubst va a renderizar en arranque
COPY default.conf.template /etc/nginx/templates/default.conf.template

# (Opcional) logs a stdout/stderr ya vienen configurados
# CMD por defecto de la imagen ya hace el envsubst y arranca nginx
