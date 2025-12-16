#!/bin/bash

# Скрипт установки и настройки Telegram бота сканирования для Raspberry Pi 3
# HP Color LaserJet Pro MFP M177fw

set -e

echo "🚀 Установка Telegram бота для сканирования на Raspberry Pi 3"
echo "=========================================================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка что мы root или имеем sudo
if [[ $EUID -ne 0 ]] && ! sudo -n true 2>/dev/null; then
    print_error "Этот скрипт требует sudo права. Запустите с sudo или как root."
    exit 1
fi

# Обновление системы
print_status "Обновление системы..."
sudo apt update && sudo apt upgrade -y

# Установка зависимостей системы
print_status "Установка системных зависимостей..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    sane-utils \
    libsane \
    libsane-dev \
    python3-dev \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libffi-dev \
    curl \
    wget

# Установка HPLIP для HP принтеров
print_status "Установка HPLIP для поддержки HP принтеров..."
sudo apt install -y hplip hplip-gui

# Установка HPLIP плагина (автоматически, без интерактивного режима)
print_status "Установка HPLIP плагина..."
if ! [ -f /var/lib/hp/hplip.state ]; then
    print_status "Устанавливаю HPLIP плагин (может потребоваться подключение к интернету)..."
    # Убиваем зависшие процессы и удаляем lock файл
    sudo pkill -9 hp-plugin 2>/dev/null || true
    sudo rm -f /var/hp-plugin.lock 2>/dev/null || true
    # Отправляем 'd' для download, затем 'y' для подтверждения
    (echo d; sleep 2; echo y) | sudo hp-plugin -i 2>&1 | grep -v "^$" || print_warning "Плагин HPLIP может потребовать ручной установки. Выполните: sudo hp-plugin"
else
    print_status "HPLIP плагин уже установлен"
fi

# Проверка подключения принтера
print_status "Проверка подключения принтеров..."
hp-check

# Настройка принтера (автоматический поиск)
print_status "Настройка HP LaserJet M177fw..."
sudo hp-setup -i

# Проверка доступности сканера
print_status "Проверка доступности сканера..."
scanimage -L

# Создание пользователя для бота (если не существует)
if ! id "scanbot" &>/dev/null; then
    print_status "Создание пользователя scanbot..."
    sudo useradd -m -s /bin/bash scanbot
    sudo usermod -a -G scanner,lp scanbot
fi

# Создание директории проекта
PROJECT_DIR="/opt/scan2telegram"
print_status "Создание директории проекта $PROJECT_DIR..."
sudo mkdir -p $PROJECT_DIR
sudo chown scanbot:scanbot $PROJECT_DIR

# Копирование файлов проекта
print_status "Копирование файлов проекта..."
sudo cp -r * $PROJECT_DIR/
sudo chown -R scanbot:scanbot $PROJECT_DIR

# Создание виртуального окружения
print_status "Создание виртуального окружения..."
sudo -u scanbot python3 -m venv $PROJECT_DIR/.venv

# Активация и установка зависимостей Python
print_status "Установка зависимостей Python..."
sudo -u scanbot bash -c "
    source $PROJECT_DIR/.venv/bin/activate
    pip install --upgrade pip
    pip install -r $PROJECT_DIR/requirements.txt
"

# Создание директории для сканов
SCAN_DIR="/opt/scan2telegram/scans"
print_status "Создание директории для сканов $SCAN_DIR..."
sudo mkdir -p $SCAN_DIR
sudo chown scanbot:scanbot $SCAN_DIR
sudo chmod 755 $SCAN_DIR

# Создание файла конфигурации
print_status "Создание файла конфигурации..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    sudo -u scanbot tee $PROJECT_DIR/.env > /dev/null <<EOF
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_IDS=

# Scanner Configuration
SCANNER_DEVICE=
SCAN_DPI=300
SCAN_FORMAT=PNG
SCAN_MODE=Color
SCAN_DIR=$SCAN_DIR

# System Configuration
MAX_FILE_SIZE_MB=50
CLEANUP_AFTER_HOURS=24
LOG_LEVEL=INFO
EOF
    print_warning "Необходимо настроить .env файл в $PROJECT_DIR/.env"
fi

# Создание systemd service
print_status "Создание systemd service..."
sudo tee /etc/systemd/system/scan2telegram.service > /dev/null <<EOF
[Unit]
Description=Telegram Scanner Bot
After=network.target

[Service]
Type=simple
User=scanbot
Group=scanbot
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/.venv/bin
ExecStart=$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/main.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=scan2telegram

[Install]
WantedBy=multi-user.target
EOF

# Создание логrotate конфигурации
print_status "Настройка ротации логов..."
sudo tee /etc/logrotate.d/scan2telegram > /dev/null <<EOF
$PROJECT_DIR/scan_bot.log {
    daily
    missingok
    rotate 7
    compress
    notifempty
    create 644 scanbot scanbot
    postrotate
        systemctl reload scan2telegram
    endscript
}
EOF

# Создание скрипта управления
print_status "Создание скрипта управления..."
sudo tee /usr/local/bin/scan2telegram > /dev/null <<'EOF'
#!/bin/bash

SCRIPT_NAME="Scan2Telegram Bot Manager"
SERVICE_NAME="scan2telegram"

case $1 in
    start)
        echo "Запуск $SCRIPT_NAME..."
        sudo systemctl start $SERVICE_NAME
        ;;
    stop)
        echo "Остановка $SCRIPT_NAME..."
        sudo systemctl stop $SERVICE_NAME
        ;;
    restart)
        echo "Перезапуск $SCRIPT_NAME..."
        sudo systemctl restart $SERVICE_NAME
        ;;
    status)
        sudo systemctl status $SERVICE_NAME
        ;;
    logs)
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    enable)
        echo "Включение автозапуска..."
        sudo systemctl enable $SERVICE_NAME
        ;;
    disable)
        echo "Отключение автозапуска..."
        sudo systemctl disable $SERVICE_NAME
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|logs|enable|disable}"
        exit 1
        ;;
esac
EOF

sudo chmod +x /usr/local/bin/scan2telegram

# Перезагрузка systemd
print_status "Перезагрузка systemd daemon..."
sudo systemctl daemon-reload

print_status "✅ Установка завершена!"
echo ""
echo "========================================"
echo "📋 СЛЕДУЮЩИЕ ШАГИ:"
echo "========================================"
echo ""
echo "1. Создайте Telegram бота:"
echo "   - Напишите @BotFather в Telegram"
echo "   - Создайте нового бота командой /newbot"
echo "   - Сохраните токен бота"
echo ""
echo "2. Получите ваш Chat ID:"
echo "   - Напишите боту @userinfobot"
echo "   - Скопируйте ваш ID"
echo ""
echo "3. Настройте конфигурацию:"
echo "   sudo nano $PROJECT_DIR/.env"
echo "   Заполните TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_IDS"
echo ""
echo "4. Запустите бота:"
echo "   scan2telegram start"
echo "   scan2telegram enable  # для автозапуска"
echo ""
echo "5. Проверьте статус:"
echo "   scan2telegram status"
echo "   scan2telegram logs"
echo ""
echo "🎉 Готово! Теперь отправьте /scan боту для сканирования!" 