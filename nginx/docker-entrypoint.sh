#!/bin/sh

# Configura el script para fallar si hay un error
set -eu

# 1. Lee la plantilla (nginx.conf.template)
# 2. Reemplaza las variables ($USUARIOS_HOSTPORT, etc.) con los valores
#    que Render inyectó en el entorno.
# 3. Guarda el resultado en el archivo de configuración real de Nginx.
envsubst '$USUARIOS_HOSTPORT,$RESERVAS_HOSTPORT,$INVENTARIO_HOSTPORT' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# 4. Inicia el servidor Nginx en primer plano.
nginx -g 'daemon off;'
