# 🚀 Инструкция по деплою обновлений

## Основные изменения

✅ **Исправлено зацикливание сообщений** - убраны уведомления при запуске
✅ **Добавлен интерфейс с кнопками** - теперь бот имеет красивые inline кнопки
✅ **Улучшен UX** - все команды теперь показывают меню для удобства
✅ **Создан скрипт исправления прав доступа к сканеру**

## Что нужно сделать на Raspberry Pi

### 1. Обновить код
```bash
# Подключаемся к Raspberry Pi
ssh pi@192.168.88.X

# Переходим в директорию проекта
cd ~/scan2telegram

# Получаем обновления из GitHub
git pull origin master
```

### 2. Исправить права доступа к сканеру
```bash
# Останавливаем бота
sudo systemctl stop scan2telegram

# Запускаем скрипт исправления прав доступа
sudo ./fix_scanner_permissions.sh

# Проверяем, что сканер обнаруживается пользователем scanbot
sudo -u scanbot scanimage -L
```

### 3. Перезапустить службу
```bash
# Перезапускаем бота
sudo systemctl restart scan2telegram

# Проверяем статус
sudo systemctl status scan2telegram

# Смотрим логи
sudo journalctl -u scan2telegram -f
```

## Проверка работы

1. **Telegram бот**: Отправьте `/start` - должны появиться кнопки
2. **Кнопки**: Попробуйте все кнопки - сканирование, статус, очистка, помощь
3. **Команды**: Старые команды `/scan`, `/status`, `/cleanup` тоже должны работать
4. **Сканирование**: Попробуйте сканировать документ

## Если что-то не работает

### Проблемы со сканером:
```bash
# Проверка обнаружения сканера
sudo -u scanbot scanimage -L

# Проверка групп пользователя
groups scanbot

# Повторный запуск скрипта прав доступа
sudo ./fix_scanner_permissions.sh
```

### Проблемы с ботом:
```bash
# Логи службы
sudo journalctl -u scan2telegram -f

# Ручной запуск для отладки
sudo -u scanbot /opt/scan2telegram/venv/bin/python /opt/scan2telegram/main.py
```

### Проблемы с сетью:
```bash
# Проверка IP принтера
ping 192.168.88.11

# Проверка HPLIP
hp-info

# Проверка CUPS
lpstat -p
```

## Возможные ошибки и решения

| Ошибка | Решение |
|--------|---------|
| `Error during device I/O` | Запустить `sudo ./fix_scanner_permissions.sh` |
| `Permission denied` | Проверить права пользователя scanbot |
| `Device not found` | Проверить IP принтера и сеть |
| `ImportError` | Проверить виртуальную среду Python |

## Контакты для поддержки

Если возникли проблемы, проверьте:
1. Логи службы: `sudo journalctl -u scan2telegram -f`
2. Статус сканера через кнопку "📊 Статус сканера" в боте
3. Подключение принтера к сети

---
*Обновление создано: $(date)* 