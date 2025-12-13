FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/nginx.conf
RUN mkdir -p /var/www/certbot && mkdir -p /usr/share/nginx/html
COPY dist/ /usr/share/nginx/html/

