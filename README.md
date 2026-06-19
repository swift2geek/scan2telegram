# 🖨️ Scan2Telegram Bot

Telegram бот для удалённого сканирования и печати документов через **HP Color LaserJet Pro MFP M177fw**. Работает на **Raspberry Pi** (systemd) и в **Docker** (например, на Synology Container Manager).

## 📋 Возможности

- 🤖 **Telegram интеграция** - управление через команды бота
- 📄 **Автоматическое сканирование** - команда `/scan` запускает процесс
- 🔧 **Гибкие настройки** - разрешение, формат, режим сканирования
- 🗂️ **Автоочистка** - удаление старых файлов
- 👥 **Контроль доступа** - авторизация по Chat ID
- 📊 **Мониторинг** - статус сканера и системы
- 🔄 **Автозапуск** - systemd service для непрерывной работы

## 🐳 Запуск в Docker (рекомендуется)

Бот собирается в self-contained образ со всем необходимым: SANE/HPLIP, CUPS, D-Bus, проприетарный HP-плагин и LibreOffice (для DOCX). Подходит для любого Linux-хоста с сетевым доступом к МФУ — в т.ч. Synology Container Manager.

### Запуск

```bash
cp config_example.env .env      # впишите токен, chat id и IP принтера
docker compose up -d --build    # первая сборка ставит hplip+cups+плагин, ~3-5 мин
docker compose logs -f
```

### Минимальный `.env` для Docker

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_IDS=...
SCANNER_DEVICE=hpaio:/net/HP_Color_LaserJet_Pro_MFP_M177fw?ip=192.168.88.11
SCAN_DIR=/app/scans
PRINTER_NAME=HP_Color_LaserJet_Pro_MFP_M177fw
PRINTER_URI=hp:/net/HP_Color_LaserJet_Pro_MFP_M177fw?ip=192.168.88.11
PRINTER_PPD=/app/printer-m177fw.ppd
```

### Важные детали реализации

- **`network_mode: host` обязателен** — сетевой скан-канал HPLIP/hpaio не работает через Docker bridge NAT.
- **HP-плагин ставится при сборке** (`hp-plugin -i`). Host-based МФУ (M177fw) требует его и для скана, **и для печати** — без плагина задание печати «уходит в очередь», но лист не выходит.
- **D-Bus** поднимается в `entrypoint.sh` — без системной шины бэкенд hpaio падает при скане.
- **eSCL/AirScan не подошёл**: M177fw отдаёт `ScannerCapabilities` в старом неймспейсе eSCL 0.98, который `sane-airscan` не распознаёт. Используется hpaio + плагин.

### Другой принтер

Замените `printer-m177fw.ppd` на PPD вашего устройства (`/etc/cups/ppd/<name>.ppd` с рабочей машины) и пропишите в `.env`: `PRINTER_NAME`, `PRINTER_URI`, `PRINTER_PPD`, `SCANNER_DEVICE`.

## 🔧 Системные требования

- **Raspberry Pi 3** (или новее)
- **Raspberry Pi OS** (Debian-based)
- **HP Color LaserJet Pro MFP M177fw** (подключен по USB/Wi-Fi)
- **Python 3.7+**
- **Интернет-соединение** для Telegram API

## 🚀 Быстрая установка

### 1. Подготовка

Подключите принтер к Raspberry Pi и убедитесь, что он доступен:

```bash
# Проверка подключения
lsusb | grep HP
```

### 2. Клонирование репозитория

```bash
git clone <repository_url>
cd scan2telegram
```

### 3. Автоматическая установка

```bash
chmod +x setup_raspberry_pi.sh
sudo ./setup_raspberry_pi.sh
```

Скрипт автоматически:
- Обновит систему
- Установит все зависимости
- Настроит HP принтер
- Создаст пользователя и сервис
- Подготовит окружение

### 4. Настройка Telegram бота

#### Создание бота:
1. Напишите **@BotFather** в Telegram
2. Создайте бота: `/newbot`
3. Следуйте инструкциям и сохраните **токен**

#### Получение Chat ID:
1. Напишите **@userinfobot** в Telegram
2. Скопируйте ваш **ID**

### 5. Конфигурация

```bash
sudo nano /opt/scan2telegram/.env
```

Заполните обязательные поля:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_IDS=your_chat_id_here
```

### 6. Запуск

```bash
# Запуск бота
scan2telegram start

# Включение автозапуска
scan2telegram enable

# Проверка статуса
scan2telegram status
```

## 📖 Использование

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и список команд |
| `/scan` | Сканирование документа |
| `/status` | Статус сканера и системы |
| `/cleanup` | Удаление старых файлов |
| `/help` | Подробная справка |

### Процесс сканирования

1. Положите документ в сканер
2. Отправьте `/scan` боту в Telegram
3. Дождитесь уведомления о завершении
4. Получите отсканированный файл

## ⚙️ Конфигурация

### Основные настройки

```env
# Разрешение сканирования (75-1200 DPI)
SCAN_DPI=300

# Формат файла (PNG, JPEG)
SCAN_FORMAT=PNG

# Режим сканирования
SCAN_MODE=Color  # Color, Gray, Lineart

# Максимальный размер файла (МБ)
MAX_FILE_SIZE_MB=50
```

### Расширенные настройки

```env
# Автоудаление файлов (часы)
CLEANUP_AFTER_HOURS=24

# Директория сканов
SCAN_DIR=/opt/scan2telegram/scans

# Уровень логирования
LOG_LEVEL=INFO
```

## 🛠️ Управление сервисом

```bash
# Основные команды
scan2telegram start      # Запуск
scan2telegram stop       # Остановка
scan2telegram restart    # Перезапуск
scan2telegram status     # Статус
scan2telegram logs       # Просмотр логов

# Автозапуск
scan2telegram enable     # Включить
scan2telegram disable    # Отключить
```

## 📊 Мониторинг

### Логи приложения
```bash
# Реальное время
scan2telegram logs

# Файл логов
tail -f /opt/scan2telegram/scan_bot.log
```

### Системные логи
```bash
# Systemd журнал
sudo journalctl -u scan2telegram -f

# Статус сервиса
sudo systemctl status scan2telegram
```

## 🔧 Устранение неполадок

### Сканер не найден

```bash
# Проверка подключения
scanimage -L

# Перезапуск SANE
sudo systemctl restart saned

# Проверка HP драйверов
hp-check
```

### Ошибки разрешений

```bash
# Добавление пользователя в группы
sudo usermod -a -G scanner,lp scanbot

# Проверка прав на директорию
ls -la /opt/scan2telegram/
```

### Проблемы с Telegram

```bash
# Проверка токена бота
curl -s "https://api.telegram.org/bot${TOKEN}/getMe"

# Проверка Chat ID
# Отправьте сообщение боту и проверьте логи
```

### Ошибки Python зависимостей

```bash
# Переустановка окружения
sudo rm -rf /opt/scan2telegram/.venv
sudo -u scanbot python3 -m venv /opt/scan2telegram/.venv
sudo -u scanbot bash -c "
    source /opt/scan2telegram/.venv/bin/activate
    pip install -r /opt/scan2telegram/requirements.txt
"
```

## 📁 Структура проекта

```
scan2telegram/
├── main.py               # Точка входа
├── bot.py                # Telegram бот
├── scanner.py            # Модуль сканирования (SANE/hpaio)
├── printer.py            # Модуль печати (CUPS) + конвертация DOCX
├── config.py             # Конфигурация
├── requirements.txt      # Python зависимости
├── Dockerfile            # Docker-образ (SANE/HPLIP, CUPS, плагин, LibreOffice)
├── docker-compose.yml    # Запуск контейнера (host network)
├── entrypoint.sh         # Старт D-Bus/CUPS + регистрация принтера + бот
├── printer-m177fw.ppd    # PPD драйвер принтера (для очереди печати в контейнере)
├── setup_raspberry_pi.sh # Скрипт установки на Raspberry Pi (systemd)
├── config_example.env    # Пример конфигурации
└── README.md             # Документация
```

## 🔒 Безопасность

- ✅ **Авторизация по Chat ID** - только разрешенные пользователи
- ✅ **Автоудаление файлов** - конфиденциальность данных
- ✅ **Изолированный пользователь** - отдельный системный аккаунт
- ✅ **Ограничение размера файлов** - защита от переполнения

## 🚀 Дополнительные возможности

### Настройка Wi-Fi сканирования

Если принтер подключен по Wi-Fi:

```bash
# Поиск сетевых сканеров
hp-probe -bnet

# Добавление сетевого устройства в конфигурацию
echo "hp:net:192.168.1.100" > ~/.sane/net.conf
```

### Мониторинг через веб-интерфейс

Можно добавить простой веб-интерфейс для мониторинга:

```bash
# Установка дополнительных зависимостей
pip install flask

# Запуск веб-интерфейса (опционально)
python web_monitor.py
```

## 📞 Поддержка

При возникновении проблем:

1. **Проверьте логи**: `scan2telegram logs`
2. **Статус сервиса**: `scan2telegram status`
3. **Подключение сканера**: `scanimage -L`
4. **HP диагностика**: `hp-check`

## 📄 Лицензия

MIT License - свободное использование и модификация.

---

**Разработано для Raspberry Pi 3 + HP Color LaserJet Pro MFP M177fw**

🎯 *Простое и надежное решение для удаленного сканирования через Telegram* 