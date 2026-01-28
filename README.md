# UstaBIM / Revit Academy Online

Проект состоит из SPA-фронтенда и API-бэкенда:
- `revit-academy-online/` — фронтенд (Vite + React + Tailwind/shadcn-ui)
- `backend/` — бэкенд (Django + DRF, JWT, Google OAuth)
- `nginx/` — Nginx для статики и проксирования `/api` и `/admin`
- `docker-compose.local.yml` — локальный стенд
- `docker-compose.yml` — продакшен стенд (с certbot)

## Конфигурация
- Шаблон переменных окружения: `.env.example`.
- Локально используется `.env.local`, на сервере — `.env`.
- Обязательно проверьте:
  - `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_CORS_ALLOWED_ORIGINS`
  - `VITE_API_BASE_URL`
  - параметры Google OAuth (`GOOGLE_*`, `VITE_GOOGLE_*`)

## Локальный запуск (Docker)
1. Подготовьте конфиг:
   ```sh
   cp .env.example .env.local
   ```
2. Запустите сервисы:
   ```sh
   docker compose -f docker-compose.local.yml up --build
   ```
3. Инициализируйте БД:
   ```sh
   docker compose -f docker-compose.local.yml exec web python manage.py migrate
   docker compose -f docker-compose.local.yml exec web python manage.py createsuperuser
   ```
4. Откройте:
   - фронтенд: `http://localhost`
   - API: `http://localhost/api`
   - админка: `http://localhost/admin`

Примечание: в локальном стенде фронтенд собирается в контейнере `frontend`. После изменений пересоберите:
```sh
docker compose -f docker-compose.local.yml exec frontend npm run build
```

## Запуск на боевом сервере (Docker)
1. Подготовьте `.env` (на основе `.env.example`). Убедитесь, что `DJANGO_DEBUG=False` и домены указаны корректно.
2. Соберите фронтенд и скопируйте сборку в `nginx/dist/`:
   ```sh
   cd revit-academy-online
   npm ci
   npm run build
   mkdir -p ../nginx/dist
   cp -R dist/* ../nginx/dist/
   ```
3. Проверьте домен в `nginx/nginx.conf` и параметры certbot в `docker-compose.yml`.
4. Запустите:
   ```sh
   docker compose up -d --build
   ```
5. Примените миграции и соберите статику:
   ```sh
   docker compose exec web python manage.py migrate
   docker compose exec web python manage.py collectstatic --noinput
   docker compose exec web python manage.py createsuperuser
   ```

### SSL (certbot)
Сервис `certbot` получает сертификаты через webroot. Убедитесь, что:
- DNS домена указывает на сервер
- в `docker-compose.yml` указаны актуальные email и домены

