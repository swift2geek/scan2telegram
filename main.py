#!/usr/bin/env python3
"""
Главный файл запуска Telegram бота для сканирования документов
Для Raspberry Pi 3 + HP Color LaserJet Pro MFP M177fw
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

import config
from bot import bot

logger = logging.getLogger(__name__)

class GracefulShutdown:
    """Класс для корректного завершения работы"""
    def __init__(self):
        self.shutdown = False
        
    def exit_gracefully(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        logger.info(f"Получен сигнал {signum}, завершение работы...")
        self.shutdown = True

async def main():
    """Главная функция"""
    try:
        # Валидация конфигурации
        config.validate_config()
        
        # Настройка обработчиков сигналов
        shutdown_handler = GracefulShutdown()
        signal.signal(signal.SIGTERM, shutdown_handler.exit_gracefully)
        signal.signal(signal.SIGINT, shutdown_handler.exit_gracefully)
        
        logger.info("🚀 Запуск Telegram бота для сканирования...")
        logger.info(f"📁 Директория сканов: {config.SCAN_DIR}")
        logger.info(f"🖨️ Устройство сканера: {config.SCANNER_DEVICE or 'автоопределение'}")
        logger.info(f"👥 Авторизованные пользователи: {len(config.TELEGRAM_CHAT_IDS)}")
        
        # Инициализация и запуск бота
        await bot.initialize()
        
        # Запуск основного цикла (убрано уведомление о запуске для предотвращения спама)
        logger.info("✅ Бот инициализирован, запускаю polling...")
        await bot.start_polling()
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания от пользователя")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        logger.info("🛑 Бот завершил работу")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1) 