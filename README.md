# 🤖 Telegram Bot — Полная документация

## Архитектура проекта

```
tgbot/
├── bot.py                    # Точка входа, webhook-сервер
├── config.py                 # Конфигурация через .env
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── database/
│   ├── schema.sql            # Схема PostgreSQL
│   └── db.py                 # asyncpg pool + все запросы
│
├── handlers/
│   ├── start.py              # /start + главное меню
│   ├── submit.py             # FSM: подача новости/опроса/желания
│   ├── admin.py              # Панель админа (ревью, FAQ, клуб, юзеры)
│   ├── faq.py                # FAQ для пользователей
│   ├── search.py             # Поиск по ID и ключевым словам
│   ├── catalog.py            # Просмотр категорий + клуб
│   └── spam.py               # Жалобы + авто-детект спама
│
├── keyboards/
│   └── kb.py                 # Все InlineKeyboardMarkup
│
├── middlewares/
│   └── register.py           # Авто-регистрация пользователей
│
├── services/
│   ├── publisher.py          # Публикация постов в каналы
│   └── spam_detector.py      # Эвристика детекции спама
│
└── utils/
    └── states.py             # FSM States для aiogram 3
```

---

## Схема базы данных

```
users           — Telegram-пользователи (id, is_admin, is_club_member)
posts           — Контент (news/poll/wish) со статусами pending→published
poll_options    — Варианты ответов для опросов
spam_reports    — Жалобы на сообщения в каналах
faq             — Вопросы/ответы с полнотекстовым поиском
club_videos     — Видео для закрытого клуба
channels        — Реестр каналов, в которые добавлен бот
```

### Жизненный цикл поста
```
[Пользователь] → pending → [Админ одобряет] → approved → [Публикация] → published
                          → [Админ отклоняет] → rejected
```

---

## Функциональность

| Функция | Описание |
|---------|----------|
| 📰 Новости | Публикация в канал новостей после ревью |
| 📊 Опросы | Нативный Telegram Poll в канал опросов |
| 💫 Желания | Публикация в канал желаний |
| ❤️ Мои желания | Список своих желаний со статусами |
| 🔍 Поиск | По UID (NEWS-0001) или ключевым словам (FTS) |
| ❓ FAQ | Полнотекстовый поиск ответов |
| 🔒 Клуб | Закрытые видео для участников клуба |
| 🚨 Жалобы | Кнопка под каждым постом в канале |
| 🤖 Авто-спам | Эвристика: ссылки, капслок, спам-слова |
| ⚙️ Админка | Ревью, FAQ CRUD, добавление видео, роли |

---

## Установка и запуск

### 1. Создать бота в Telegram

1. Откройте **@BotFather** в Telegram
2. Отправьте `/newbot`
3. Введите имя бота: например `My Community Bot`
4. Введите username: например `my_community_bot` (должен заканчиваться на `bot`)
5. Скопируйте токен вида `7123456789:AAF_...`

### 2. Получить ID админа

1. Напишите **@userinfobot** или **@getidsbot**
2. Он вернёт ваш `user_id` (число)

### 3. Создать каналы

Для каждой категории создайте отдельный канал:
1. В Telegram: Новый канал → укажите название
2. Добавьте бота в канал как **администратора** (права: публикация сообщений, редактирование)
3. Узнайте ID канала:
   - Перешлите любое сообщение из канала боту **@getidsbot**
   - Или временно добавьте бота и он сам сообщит ID при добавлении

### 4. Настройка сервера (VPS)

```bash
# Клонируйте/скопируйте проект
git clone <your-repo> tgbot
cd tgbot

# Настройте переменные окружения
cp .env.example .env
nano .env  # заполните все значения
```

### 5. Запуск через Docker Compose (рекомендуется)

```bash
# Убедитесь что Docker и Docker Compose установлены
docker --version
docker compose version

# Запуск
docker compose up -d

# Проверка логов
docker compose logs -f bot

# Остановка
docker compose down
```

### 6. Настройка Nginx как reverse proxy

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location /webhook {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Получить SSL-сертификат
certbot --nginx -d yourdomain.com
```

### 7. Запуск без Docker (прямой деплой)

```bash
# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Создать базу данных
psql -U postgres -c "CREATE USER tgbot_user WITH PASSWORD 'strongpassword';"
psql -U postgres -c "CREATE DATABASE tgbot_db OWNER tgbot_user;"
psql -U tgbot_user -d tgbot_db -f database/schema.sql

# Запустить
python bot.py
```

### 8. Systemd service (автозапуск)

```ini
# /etc/systemd/system/tgbot.service
[Unit]
Description=Telegram Bot
After=network.target postgresql.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/tgbot
ExecStart=/home/ubuntu/tgbot/venv/bin/python bot.py
Restart=always
RestartSec=5
EnvironmentFile=/home/ubuntu/tgbot/.env

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable tgbot
systemctl start tgbot
systemctl status tgbot
```

---

## Добавление бота в каналы

### Шаг 1: Открыть настройки канала
- **Мобильный**: нажмите на название канала → «Управление каналом» → «Администраторы»
- **Desktop**: правая кнопка на канале → «Управление» → «Администраторы»

### Шаг 2: Добавить администратора
1. Нажмите «Добавить администратора»
2. Найдите вашего бота по username (например `@my_community_bot`)
3. Установите права:
   - ✅ Публикация сообщений
   - ✅ Редактирование сообщений (для обновления кнопок)
   - ✅ Удаление сообщений (опционально)
   - ❌ Остальные права не нужны

### Шаг 3: Получить ID канала
Бот автоматически отправит вам ID при добавлении.  
Внесите ID в `.env`:
```
CHANNEL_NEWS=-1001234567890
CHANNEL_POLL=-1009876543210
CHANNEL_WISH=-1001122334455
CHANNEL_CLUB=-1005566778899
```

---

## Команды администратора

| Callback / действие | Описание |
|---------------------|----------|
| Кнопка «⚙️ Панель админа» | Открыть панель (видна только админам) |
| «📋 Ожидают ревью» | Просмотр и одобрение/отклонение постов |
| «➕ Добавить FAQ» | Добавить новый вопрос/ответ |
| «📝 FAQ — список» | Редактировать или удалить FAQ |
| «🎬 Добавить видео в клуб» | Загрузить видео в закрытый клуб |
| «👤 Сделать админом» | Выдать права администратора по ID |
| «🔒 Добавить в клуб» | Дать доступ к клубному разделу |

---

## Система уникальных ID

| Тип | Формат | Пример |
|-----|--------|--------|
| Новость | `NEWS-XXXX` | `NEWS-0001` |
| Опрос | `POLL-XXXX` | `POLL-0042` |
| Желание | `WISH-XXXX` | `WISH-0007` |
| Клуб-видео | `VID-XXXX` | `VID-0003` |

Поиск по ID: бот принимает точный UID или ключевые слова.

---

## Детекция спама

Бот автоматически проверяет сообщения в каналах/группах по критериям:
- Более 3 URL-ссылок в одном сообщении
- 3+ спам-слова («казино», «заработок», «крипта» и др.)
- Более 60% заглавных букв
- Сообщение состоит только из ссылки

При срабатывании — немедленное уведомление всем администраторам.  
Пользователи могут дополнительно жаловаться через кнопку 🚨 под постом.

---

## Лимиты Telegram API

Бот учитывает следующие ограничения:
- **30 сообщений/сек** — publisher использует `TelegramRetryAfter`
- **Текст сообщения** — до 4096 символов (тело поста обрезается)
- **Варианты опроса** — от 2 до 10, каждый до 100 символов
- **Заголовок поста** — до 512 символов

---

## Переменные окружения

| Переменная | Описание | Обязательно |
|-----------|----------|-------------|
| `BOT_TOKEN` | Токен от BotFather | ✅ |
| `ADMIN_IDS` | ID администраторов через запятую | ✅ |
| `WEBHOOK_HOST` | Публичный URL сервера | ✅ |
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `CHANNEL_NEWS` | ID канала новостей | ✅ |
| `CHANNEL_POLL` | ID канала опросов | ✅ |
| `CHANNEL_WISH` | ID канала желаний | ✅ |
| `CHANNEL_CLUB` | ID закрытого канала клуба | ✅ |
| `SPAM_REPORT_THRESHOLD` | Порог жалоб для уведомления (по умолч. 3) | ❌ |
| `WEBAPP_PORT` | Порт веб-сервера (по умолч. 8080) | ❌ |
