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
rsync -avz --exclude .venv --exclude venv --exclude db.sqlite3 --exclude __pycache__ --exclude staticfiles \
  ./ deenify@IP_СЕРВЕРА:/var/www/deenify/
```

> `venv`/`Scripts` (Windows-venv) исключаем обязательно: venv пересоздаётся на
> сервере командой ниже, иначе `ExecStart` падает с `203/EXEC`.

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

> Юнит-файллар номи **`deenify-web`** ва **`deenify-bot`**. Агар серверда
> `deenify.service` деган ўринга бор (қўлда ёзилган ёки эски версия) — у ўрнига
> ўша иккисини ўрнатинг ва `deenify.service` ни ўчиринг.

Логи бота:

```bash
sudo journalctl -u deenify-bot -f
```

### Оплата подписки (Click)

Click не хранит карту и не списывает её автоматически: каждая подписка — это
одна оплата на нашей собственной странице оплаты. Продление пользователь
подтверждает сам (кнопка в боте → `/api/v1/payments/click/start/`).

Проверить, что всё настроено (ничего не отправляет в Click, только локальная проверка):

```bash
cd /var/www/deenify
sudo -u deenify .venv/bin/python manage.py check_click
```

Если команда пишет `Missing .env: ...` — заполните значения в `/var/www/deenify/.env`
и перезапустите `sudo systemctl restart deenify-web`.

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
python manage.py cleanup_stale_click_orders --all-unpaid --dry-run
python manage.py cleanup_stale_click_orders --all-unpaid
```

В админке: выделить заказы → action **«Delete selected unpaid orders»**.

Переменная `.env`: `CLICK_STALE_ORDER_RETENTION_DAYS=1`

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

### Тест короткой подписки (месячная за 15 минут)

Временно в `.env` (годовая подписка остаётся на 365 дней):

```env
DEENIFY_TEST_MONTHLY_RENEWAL_MINUTES=15
```

```bash
sudo systemctl restart deenify-web deenify-bot
```

Купить месячную подписку — она сразу活 будет действовать 15 минут вместо 30 дней.
Чтобы вернуть прод, уберите переменную из `.env` (или поставьте `=0`) и
перезапустите `sudo systemctl restart deenify-web`.

Связанные переменные `.env` (необязательные, есть значения по умолчанию):

```env
CLICK_REFERRAL_BONUS_DAYS_MONTHLY=10    # бонус пригласившему за месячную подписку приглашённого
CLICK_REFERRAL_BONUS_DAYS_YEARLY=30     # бонус за годовую
BOT_USERNAME=DeenifyUzBot               # для реферальных ссылок t.me/<username>?start=ref_<id>
```

---

## 9. Nginx
## 9. Nginx

```bash
sudo cp deploy/nginx/deenify.conf /etc/nginx/sites-available/deenify
sudo ln -sf /etc/nginx/sites-available/deenify /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### Click payments (своя страница оплаты + callback)

Схема по [docs.click.uz](https://docs.click.uz/):

1. Кнопка тарифа в боте ведёт на **нашу** страницу
   `GET /api/v1/payments/click/start/?telegram_id=…&plan_id=…&exp=…&sig=…`
2. Бэкенд создаёт заказ и рендерит свою HTML-страницу со скрытой формой
3. Форма `POST`-ится на `https://my.click.uz/services/pay` — это страница оплаты Click
4. Click вызывает наш **callback**: `action=0` (Prepare) и `action=1` (Complete)
5. После оплаты Click возвращает пользователя на **return URL** — тоже нашу страницу

Зарегистрировать в кабинете [my.click.uz](https://my.click.uz) (Мерчант → Настройки):

| Setting | Value |
|---------|--------|
| Callback URL | `https://api.frienfinity.uz/api/v1/payments/click/callback/` |
| Return URL | `https://api.frienfinity.uz/api/v1/payments/click/return/` |

`.env` example:

```env
CLICK_SERVICE_ID=        # Service ID из кабинета
CLICK_MERCHANT_ID=       # Merchant ID из кабинета
CLICK_MERCHANT_USER_ID=  # Merchant user ID из кабинета
CLICK_SECRET_KEY=        # Secret key для проверки подписи callback
CLICK_PAYMENT_URL=https://my.click.uz/services/pay
CLICK_RETURN_URL=https://api.frienfinity.uz/api/v1/payments/click/return/
CLICK_CALLBACK_URL=https://api.frienfinity.uz/api/v1/payments/click/callback/
CLICK_BOT_URL=https://t.me/DeenifyUzBot
CLICK_LANG=uz
```

Подпись callback (MD5) проверяется всегда:
`click_trans_id + service_id + secret_key + merchant_trans_id + [merchant_prepare_id] + amount + action + sign_time`.

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

CLICK_CALLBACK_URL=https://api.frienfinity.uz/api/v1/payments/click/callback/
CLICK_RETURN_URL=https://api.frienfinity.uz/api/v1/payments/click/return/
CLICK_BOT_URL=https://t.me/DeenifyUzBot
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

Локальные тесты (в проекте есть Django-приложение `tests`, поэтому discovery с
пустым ярлыком падает на совпадении имён пакетов — указываем ярлыки явно):

```bash
cd /var/www/deenify
.venv/bin/python manage.py check
.venv/bin/python manage.py test users.tests tests
```

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

## Troubleshooting: `status=203/EXEC`

`203/EXEC` — systemd `ExecStart` dagi faylni **ishga tushira olmadi**: fayl yo'q,
`+x` yo'q, yoki shebang noto'g'ri. Bu kod xatosi emas, deploy konfiguratsiyasi xatosi.

1. Avval qayta urinish tugatilsin (hozir 50 000+ marta restart bo'lgan):

```bash
sudo systemctl stop deenify.service
sudo systemctl reset-failed deenify.service
```

2. Ko'ring nima ishga tushirilmoqda va fayl bor-mi:

```bash
sudo systemctl cat deenify.service
ls -la /var/www/deenify/
ls -la /var/www/deenify/.venv/bin/ | head
sudo -u deenify /var/www/deenify/.venv/bin/python -V
```

3. Sabab bo'yicha tuzatish:

| Holat | Tuzatish |
|-------|---------|
| `.venv/bin/gunicorn` yo'q | `cd /var/www/deenify && sudo -u deenify python3 -m venv .venv && sudo -u deenify .venv/bin/pip install -r requirements.txt` |
| venv nomi `venv` (nuqtasiz) | `.env`/unit ichidagi yo'lni `.venv` ga o'zgartiring yoki venv'ni `.venv` ga ko'chiring |
| fayl bor, lekin `+x` yo'q | `sudo chmod +x /var/www/deenify/.venv/bin/gunicorn` |
| `venv/Scripts/` (Windows'dan rsync qilingan) | Windows venv'ini serverga yubormang: `rm -rf venv` va `.venv` ni qayta yarating |
| eski `deenify.service` uniti | `sudo systemctl disable --now deenify.service && sudo systemctl mask deenify.service` va `deenify-web`/`deenify-bot` ni o'rnatish |

4. To'g'ri unitlarni o'rnatish:

```bash
sudo cp deploy/systemd/deenify-web.service deploy/systemd/deenify-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now deenify-web deenify-bot
systemctl is-active deenify-web deenify-bot
```

5. Tezkor tekshiruv (`.env` to'g'ri bo'lishi uchun):

```bash
cd /var/www/deenify
sudo -u deenify .venv/bin/python manage.py check
sudo -u deenify .venv/bin/python manage.py check_click
sudo -u deenify .venv/bin/python manage.py collectstatic --noinput
```

> Eslatma: `EnvironmentFile=/var/www/deenify/.env` yo'q bo'lsa xato `226/ENV` bo'ladi —
> `203/EXEC` esa aynan binary/interpreter muammosi.

### Migratsiya xatosi: `KeyError: ('users', 'atmosorder')`

Sabab: serverda `makemigrations` bilan yaratilgan, lekin **gitga qo'shilmagan** eski
migration fayli qolib ketgan (masalan `0012_alter_atmosorder_status_and_more.py`).
Bizning `0012_switch_atmos_orders_to_click.py` modelni `AtmosOrder` → `ClickOrder`
qilib o'zgartirgani uchun o'sha fayldagi `alter_field` endi mos modelni topa olmaydi.

```bash
cd /var/www/deenify
git status --short users/migrations tests/migrations   # begona (??) fayllarni ko'rish
rm -f users/migrations/0012_alter_atmosorder_status_and_more.py
sudo -u deenify .venv/bin/python manage.py migrate
```

> Muhim: `makemigrations` faqat lokal, `git status` toza holatda bajarilishi kerak —
> generatsiya qilingan fayllar hech qachon serverga yuborilmasin.

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
