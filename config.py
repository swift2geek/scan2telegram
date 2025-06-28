"""
Конфигурация для Telegram бота сканирования
"""
import os
import logging
from pathlib import Path
from decouple import config
from typing import List

# Базовые пути
BASE_DIR = Path(__file__).parent
SCAN_DIR = Path(config('SCAN_DIR', default='/tmp/scans'))

# Telegram настройки
TELEGRAM_BOT_TOKEN = config('TELEGRAM_BOT_TOKEN', default='')
TELEGRAM_CHAT_IDS = [
    int(chat_id.strip()) 
    for chat_id in config('TELEGRAM_CHAT_IDS', default='').split(',') 
    if chat_id.strip()
]

# Настройки сканера
SCANNER_DEVICE = config('SCANNER_DEVICE', default='')
SCAN_DPI = config('SCAN_DPI', default=300, cast=int)
SCAN_FORMAT = config('SCAN_FORMAT', default='PNG')
SCAN_MODE = config('SCAN_MODE', default='Color')

# Системные настройки
MAX_FILE_SIZE_MB = config('MAX_FILE_SIZE_MB', default=50, cast=int)
CLEANUP_AFTER_HOURS = config('CLEANUP_AFTER_HOURS', default=24, cast=int)
LOG_LEVEL = config('LOG_LEVEL', default='INFO')

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scan_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def validate_config():
    """Проверка корректности конфигурации"""
    errors = []
    
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN не задан")
    
    if not TELEGRAM_CHAT_IDS:
        errors.append("TELEGRAM_CHAT_IDS не заданы")
    
    if not SCAN_DIR.exists():
        try:
            SCAN_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"Создана директория для сканов: {SCAN_DIR}")
        except Exception as e:
            errors.append(f"Не удается создать директорию сканов: {e}")
    
    if errors:
        for error in errors:
            logger.error(error)
        raise ValueError("Ошибки конфигурации: " + "; ".join(errors))
    
    logger.info("Конфигурация успешно валидирована") 