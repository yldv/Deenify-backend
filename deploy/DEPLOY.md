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
- `ALLOWED_HOSTS` — `api.frienfinity.uz,frienfinity.uz` (`127.0.0.1` и `localhost` добавляются автоматически)
- `CSRF_TRUSTED_ORIGINS` — `https://api.frienfinity.uz`
- `BACKEND_BASE_URL` — **`http://127.0.0.1:8001/api/v1`** (бот на том же сервере; не через HTTPS)

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

### Автосписания подписок (bind-card)

Подписки продлеваются по токену привязанной карты. Atmos списывает по инициативе
мерчанта, поэтому нужен ежедневный запуск команды `charge_due_subscriptions` через
systemd timer:

```bash
sudo cp deploy/systemd/deenify-billing.service /etc/systemd/system/
sudo cp deploy/systemd/deenify-billing.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now deenify-billing.timer
sudo systemctl list-timers deenify-billing.timer   # проверить расписание
```

### Очистка неоплаченных заказов (админка)

Тестовые `created` / `pending` / `failed` заказы копятся в «To'lov buyurtmalari».
Оплаченные (`paid`) **никогда не удаляются** автоматически.

Ежедневная автоочистка (неоплаченные заказы старше 1 дня по умолчанию):

```bash
sudo cp deploy/systemd/deenify-cleanup-orders.service /etc/systemd/system/
sudo cp deploy/systemd/deenify-cleanup-orders.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now deenify-cleanup-orders.timer
```

Перед prod — разовая зачистка всего мусора (сначала dry-run):

```bash
cd /var/www/deenify
source .venv/bin/activate
python manage.py cleanup_stale_atmos_orders --all-unpaid --dry-run
python manage.py cleanup_stale_atmos_orders --all-unpaid
```

В админке: выделить заказы → action **«Delete selected unpaid orders»**.

Переменная `.env`: `ATMOS_STALE_ORDER_RETENTION_DAYS=1`

### Автоудаление каталога тарифов в Telegram (если не купил)

Сообщение «⭐ Deenify Premium … 👇 Tarifni tanlang» удаляется из чата через **1 час**,
если оплата не прошла (ссылки на оплату тоже живут ~1 час). При успешной оплате
сообщение удаляется сразу, как и раньше.

```bash
sudo cp deploy/systemd/deenify-cleanup-offers.service /etc/systemd/system/
sudo cp deploy/systemd/deenify-cleanup-offers.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now deenify-cleanup-offers.timer
sudo systemctl list-timers deenify-cleanup-offers.timer
```

Проверка вручную:

```bash
python manage.py cleanup_expired_offer_messages --dry-run
```

`.env`: `OFFER_MESSAGE_TTL_SECONDS=3600` (1 час)

> **Нужно ли дропать всю БД перед prod?** Обычно **нет**. Достаточно удалить неоплаченные заказы командой выше.
> Полный сброс (`DROP DATABASE` / `flush`) — только если **все** пользователи и подписки тестовые и их можно потерять.

Проверка вручную (без списания — только список должников):

```bash
cd /var/www/deenify
sudo -u deenify .venv/bin/python manage.py charge_due_subscriptions --dry-run
```

Связанные переменные `.env` (необязательные, есть значения по умолчанию):

```env
ATMOS_TOKEN_PAYMENT_OTP=111111          # OTP для apply при списании по токену (подтвердить у Atmos для прода)
ATMOS_RENEW_LEAD_DAYS=1                  # за сколько дней до конца продлевать
ATMOS_RENEW_FAIL_GRACE_DAYS=3           # сколько дней пытаться, прежде чем выключить авто-продление
ATMOS_REFERRAL_BONUS_DAYS_MONTHLY=10    # бонус пригласившему за месячную подписку приглашённого
ATMOS_REFERRAL_BONUS_DAYS_YEARLY=30     # бонус за годовую
BOT_USERNAME=DeenifyUzBot               # для реферальных ссылок t.me/<username>?start=ref_<id>
```

> Если Atmos подтвердит, что списывает сам (push-модель), таймер можно не включать —
> код первичной оплаты при привязке карты от этого не зависит.

---

## 9. Nginx

```bash
sudo cp deploy/nginx/deenify.conf /etc/nginx/sites-available/deenify
sudo cp deploy/nginx/atmos-checkout-proxy.conf /etc/nginx/snippets/atmos-checkout-proxy.conf
sudo ln -sf /etc/nginx/sites-available/deenify /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### Atmos payments (merchant/pay + callback)

Integration flow per [docs.atmos.uz](https://docs.atmos.uz/en/index.html):

1. `POST https://apigw.atmos.uz/merchant/pay/create` — create transaction
2. User pays on `http://test-checkout.pays.uz/invoice/get?...` (sandbox) or `https://checkout.pays.uz/...` (production)
3. Atmos calls your **callback** before confirming payment
4. After payment, user is redirected to **return** URL; backend polls `merchant/pay/get` and activates subscription

Register in **partner-test.atmos.uz** (then Atmos will issue `ATMOS_API_KEY`):

| Setting | Value |
|---------|--------|
| Callback URL | `https://api.frienfinity.uz/api/v1/payments/atmos/callback/` |
| Return URL (redirectLink) | `https://api.frienfinity.uz/api/v1/payments/atmos/return/` |

`.env` example:

```env
ATMOS_TEST_MODE=True
ATMOS_BASE_URL=https://apigw.atmos.uz
ATMOS_CALLBACK_URL=https://api.frienfinity.uz/api/v1/payments/atmos/callback/
ATMOS_RETURN_URL=https://api.frienfinity.uz/api/v1/payments/atmos/return/
ATMOS_SUCCESS_REDIRECT_URL=https://t.me/DeenifyUzBot
ATMOS_API_KEY=   # from Atmos after callback URL is registered
```

---

## 10. SSL (HTTPS)

Когда DNS `api.frienfinity.uz` указывает на сервер.

### Если openssl показывает чужой сертификат (vt-travel.uz и т.д.)

На сервере нет `listen 443 ssl` для `api.frienfinity.uz` — nginx отдаёт **default_server** другого сайта.

```bash
cd /var/www/deenify
git pull
sudo bash deploy/scripts/fix-nginx-ssl.sh
```

Или вручную в certbot выберите **1** (reinstall), затем:

```bash
sudo cp deploy/nginx/deenify.conf /etc/nginx/sites-available/deenify
sudo cp deploy/nginx/atmos-checkout-proxy.conf /etc/nginx/snippets/
sudo ln -sf /etc/nginx/sites-available/deenify /etc/nginx/sites-enabled/deenify
sudo nginx -t && sudo systemctl reload nginx
```

Проверка:

```bash
echo | openssl s_client -connect api.frienfinity.uz:443 -servername api.frienfinity.uz 2>/dev/null \
  | openssl x509 -noout -subject -ext subjectAltName
# Должно быть: api.frienfinity.uz (не vt-travel.uz)
```

### `.env` после SSL

```env
# Бот — всегда localhost (на том же сервере):
BACKEND_BASE_URL=http://127.0.0.1:8001/api/v1

ATMOS_CALLBACK_URL=https://api.frienfinity.uz/api/v1/payments/atmos/callback/
ATMOS_RETURN_URL=https://api.frienfinity.uz/api/v1/payments/atmos/return/
ATMOS_SUCCESS_REDIRECT_URL=https://t.me/DeenifyUzBot
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

При первом деплое cleanup timer (если ещё не включён):

```bash
sudo cp deploy/systemd/deenify-cleanup-orders.service /etc/systemd/system/
sudo cp deploy/systemd/deenify-cleanup-orders.timer /etc/systemd/system/
sudo cp deploy/systemd/deenify-cleanup-offers.service /etc/systemd/system/
sudo cp deploy/systemd/deenify-cleanup-offers.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now deenify-cleanup-orders.timer deenify-cleanup-offers.timer
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
