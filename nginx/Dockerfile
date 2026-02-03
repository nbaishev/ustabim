FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/nginx.https.conf
COPY nginx.http.conf /etc/nginx/nginx.http.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /var/www/certbot \
    && mkdir -p /usr/share/nginx/html
COPY dist/ /usr/share/nginx/html/

ENTRYPOINT ["/entrypoint.sh"]
