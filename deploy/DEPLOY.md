# Deenify — деплой на Contabo + frienfinity.uz

Домен: **frienfinity.uz**  
API и админка: **https://api.frienfinity.uz**

---

## 1. DNS (у регистратора домена)

| Тип | Имя (Host) | Значение | TTL |
|-----|------------|----------|-----|
| A | `api` | IP вашего VPS Contabo | 300 |
| A | `@` | тот же IP (опционально) | 300 |

Проверка (на Mac, через 5–30 мин):

```bash
dig +short api.frienfinity.uz
```

Должен вернуть IP сервера.

---

## 2. Подключение SSH

```bash
ssh root@IP_СЕРВЕРА
```

После входа — обновление:

```bash
apt update && apt upgrade -y
```

---

## 3. Пользователь и пакеты

```bash
adduser deenify
usermod -aG sudo deenify
```

На Mac (удобный вход по ключу):

```bash
ssh-copy-id deenify@IP_СЕРВЕРА
ssh deenify@IP_СЕРВЕРА
```

На сервере:

```bash
sudo apt install -y python3 python3-venv python3-pip git nginx postgresql postgresql-contrib certbot python3-certbot-nginx ufw
```

---

## 4. PostgreSQL

```bash
sudo -u postgres psql
```

```sql
CREATE USER deenify_user WITH PASSWORD 'СИЛЬНЫЙ_ПАРОЛЬ';
CREATE DATABASE deenify_db OWNER deenify_user;
\q
```

---

## 5. Код проекта

```bash
sudo mkdir -p /var/www/deenify
sudo chown deenify:deenify /var/www/deenify
cd /var/www/deenify
```

Git:

```bash
git clone https://github.com/ВАШ_АККАУНТ/Deenify-backend.git .
```

Или с Mac:

```bash
rsync -avz --exclude .venv --exclude db.sqlite3 --exclude __pycache__ --exclude staticfiles \
  ./ deenify@IP_СЕРВЕРА:/var/www/deenify/
```

```bash
cd /var/www/deenify
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 6. Файл `.env`

```bash
cp deploy/env.production.example .env
nano .env
```

Обязательно заполните:

- `SECRET_KEY` — `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- `DATABASE_URL` — пароль из шага 4
- `BOT_TOKEN` — от @BotFather
- `ALLOWED_HOSTS` — `api.frienfinity.uz,frienfinity.uz,IP`
- `CSRF_TRUSTED_ORIGINS` — `https://api.frienfinity.uz`
- `BACKEND_BASE_URL` — `https://api.frienfinity.uz/api/v1` (после SSL; до SSL `http://IP/api/v1`)

---

## 7. Django

```bash
cd /var/www/deenify
source .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py seed_deenify   # опционально
```

---

## 8. Systemd (Gunicorn + бот)

```bash
sudo cp deploy/systemd/deenify-web.service /etc/systemd/system/
sudo cp deploy/systemd/deenify-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable deenify-web deenify-bot
sudo systemctl start deenify-web deenify-bot
sudo systemctl status deenify-web deenify-bot
```

Логи бота:

```bash
sudo journalctl -u deenify-bot -f
```

---

## 9. Nginx

```bash
sudo cp deploy/nginx/deenify.conf /etc/nginx/sites-available/deenify
sudo ln -sf /etc/nginx/sites-available/deenify /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

---

## 10. SSL (HTTPS)

Когда DNS `api.frienfinity.uz` указывает на сервер:

```bash
sudo certbot --nginx -d api.frienfinity.uz
```

В `.env` обновите:

```env
BACKEND_BASE_URL=https://api.frienfinity.uz/api/v1
ATMOS_CALLBACK_URL=https://api.frienfinity.uz/api/v1/payments/atmos/callback/
```

```bash
sudo systemctl restart deenify-web deenify-bot
```

---

## 11. Файрвол

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 12. Проверка

| URL | Что |
|-----|-----|
| https://api.frienfinity.uz/admin/ | Админка |
| https://api.frienfinity.uz/api/docs/ | Swagger |
| Telegram | Бот отвечает на /start |

---

## 13. Обновление после git pull

```bash
cd /var/www/deenify
git pull
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart deenify-web deenify-bot
```

---

## 14. Бэкап БД (cron)

```bash
mkdir -p /home/deenify/backups
crontab -e
```

```
0 3 * * * pg_dump -U deenify_user deenify_db > /home/deenify/backups/deenify_$(date +\%F).sql
```

---

## Схема

```
Пользователь / Telegram
        ↓
api.frienfinity.uz (Nginx :443)
        ↓
Gunicorn :8001 → Django
bot.py → BACKEND_BASE_URL (тот же API)
PostgreSQL deenify_db
```
