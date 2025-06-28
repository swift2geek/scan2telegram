#!/bin/bash
# Скрипт для исправления прав доступа к сканеру HP M177fw
# Запускать с правами sudo

set -e

echo "🔧 Настройка прав доступа к сканеру HP M177fw..."

# Добавляем пользователя scanbot в дополнительные группы
echo "👤 Добавляю пользователя scanbot в группы scanner, lp, dialout..."
usermod -a -G scanner,lp,dialout scanbot

# Проверяем и создаем правила udev для HP принтеров
echo "📋 Настройка udev правил..."
cat > /etc/udev/rules.d/60-hp-scanner.rules << 'EOF'
# HP LaserJet Pro MFP M177fw scanner rules
SUBSYSTEM=="usb", ATTRS{idVendor}=="03f0", ATTRS{idProduct}=="*", GROUP="scanner", MODE="0664"
SUBSYSTEM=="usbmisc", ATTRS{idVendor}=="03f0", ATTRS{idProduct}=="*", GROUP="scanner", MODE="0664" 
KERNEL=="lp*", GROUP="lp", MODE="0664"

# Network scanning access
ACTION=="add", SUBSYSTEM=="net", KERNEL=="eth*", RUN+="/bin/chmod 666 /dev/hp*"
ACTION=="add", SUBSYSTEM=="net", KERNEL=="wlan*", RUN+="/bin/chmod 666 /dev/hp*"
EOF

# Перезагружаем udev правила
echo "🔄 Перезагружаю udev правила..."
udevadm control --reload-rules
udevadm trigger

# Настройка SANE для работы по сети
echo "🌐 Настройка SANE для сетевого доступа..."
if ! grep -q "192.168.88.11" /etc/sane.d/net.conf; then
    echo "192.168.88.11" >> /etc/sane.d/net.conf
fi

# Настройка hplip для работы по сети
echo "🖨️ Настройка HPLIP..."
if [ -f /etc/hp/hplip.conf ]; then
    sed -i 's/network-discovery=0/network-discovery=1/g' /etc/hp/hplip.conf
fi

# Проверяем статус демонов
echo "🔍 Проверка сервисов..."
systemctl restart cups
systemctl restart saned || true
systemctl restart hplip || true

# Проверяем обнаружение сканера
echo "🔍 Проверяю обнаружение сканера..."
echo "Сканеры, обнаруженные SANE:"
scanimage -L || echo "❌ Ошибка обнаружения сканеров"

echo "Устройства HP:"
hp-info || echo "❌ HPLIP не может найти устройства"

# Проверяем права доступа пользователя scanbot
echo "👤 Проверка групп пользователя scanbot:"
groups scanbot

echo "✅ Настройка завершена!"
echo ""
echo "📝 Рекомендации:"
echo "1. Перезапустите службу бота: sudo systemctl restart scan2telegram"
echo "2. Проверьте, что принтер включен и подключен к сети"
echo "3. Убедитесь, что IP адрес принтера 192.168.88.11 актуален"
echo "4. Проверьте работу: sudo -u scanbot scanimage -L" 