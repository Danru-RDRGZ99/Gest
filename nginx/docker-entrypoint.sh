set -eu

envsubst '$USUARIOS_HOSTPORT,$RESERVAS_HOSTPORT,$INVENTARIO_HOSTPORT' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

nginx -g 'daemon off;'
