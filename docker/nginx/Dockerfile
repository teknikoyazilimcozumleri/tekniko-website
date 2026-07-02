FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY docker/nginx/default.conf /etc/nginx/conf.d/default.conf
CMD ["/bin/sh", "-c", "set -eu; CERT_DIR=/etc/nginx/certs; CRT_PATH=$CERT_DIR/selfsigned.crt; KEY_PATH=$CERT_DIR/selfsigned.key; CERT_DOMAIN=${SSL_CERT_DOMAIN:-localhost}; mkdir -p $CERT_DIR; if [ ! -f $CRT_PATH ] || [ ! -f $KEY_PATH ]; then echo Generating self-signed certificate for ${CERT_DOMAIN}...; openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout $KEY_PATH -out $CRT_PATH -subj /CN=${CERT_DOMAIN}; fi; exec nginx -g 'daemon off;'"]
