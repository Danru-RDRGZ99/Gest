FROM nginx:latest

# 1. Borrar la configuración por defecto
RUN rm /etc/nginx/conf.d/default.conf

# 2. CREAR el archivo nginx.conf.template directamente
RUN cat <<'EOF' > /etc/nginx/nginx.conf.template
worker_processes 1;
events { worker_connections 1024; }

http {
    limit_req_zone $binary_remote_addr zone=reserva_limit:10m rate=10r/m;

    upstream servicio_usuarios {
        server $USUARIOS_HOSTPORT;
    }
    upstream servicio_reservas {
        server $RESERVAS_HOSTPORT;
    }
    upstream servicio_inventario {
        server $INVENTARIO_HOSTPORT;
    }
    
    server {
        listen 80;

        location = /__health {
            return 200 "OK";
            add_header Content-Type text/plain;
        }

        location /ws {
            proxy_pass http://servicio_reservas;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "Upgrade";
            proxy_set_header Host $host;
        }
    
        location ~ ^/(token|register|auth|usuarios|captcha) {
            proxy_pass http://servicio_usuarios;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    
        location ~ ^/(reservas|laboratorios/.*/horario|admin/horarios) {
            limit_req zone=reserva_limit burst=20 nodelay;
            proxy_pass http://servicio_reservas;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    
        location / {
            proxy_pass http://servicio_inventario;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
EOF

# 3. CREAR el archivo docker-entrypoint.sh directamente
RUN cat <<'EOF' > /docker-entrypoint.sh
#!/bin/sh
set -eu
envsubst '$USUARIOS_HOSTPORT,$RESERVAS_HOSTPORT,$INVENTARIO_HOSTPORT' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
nginx -g 'daemon off;'
EOF

# 4. ---- ESTA ES LA LÍNEA MODIFICADA ----
#    Arregla los finales de línea (quita \r) Y da permisos
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

# 5. Definir el script como el punto de entrada
ENTRYPOINT ["/docker-entrypoint.sh"]