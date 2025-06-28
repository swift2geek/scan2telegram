"""
Telegram бот для сканирования документов
"""
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, Bot
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes,
    MessageHandler,
    filters
)
import config
from scanner import scanner, ScannerError

logger = logging.getLogger(__name__)

class ScanBot:
    def __init__(self):
        self.application = None
        self.bot = None
        
    async def initialize(self):
        """Инициализация бота"""
        try:
            # Создание приложения
            self.application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
            self.bot = self.application.bot
            
            # Регистрация обработчиков команд
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("scan", self.scan_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(CommandHandler("cleanup", self.cleanup_command))
            
            # Обработчик для неизвестных команд
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.unknown_command))
            
            logger.info("Telegram бот инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации бота: {e}")
            raise
    
    def _is_authorized(self, user_id: int) -> bool:
        """Проверка авторизации пользователя"""
        return user_id in config.TELEGRAM_CHAT_IDS or not config.TELEGRAM_CHAT_IDS
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        welcome_text = """
🖨️ *Бот для сканирования документов*

Доступные команды:
• /scan - Сканировать документ
• /status - Статус сканера
• /cleanup - Очистить старые файлы
• /help - Помощь

Просто отправьте /scan чтобы начать сканирование!
        """
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        logger.info(f"Пользователь {user_id} запустил бота")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        help_text = """
🔧 *Помощь по использованию бота*

*Основные команды:*
• `/scan` - Сканирует документ и отправляет вам файл
• `/status` - Показывает текущий статус сканера
• `/cleanup` - Удаляет старые отсканированные файлы

*Настройки сканирования:*
• Разрешение: {dpi} DPI
• Режим: {mode}
• Формат: {format}

*Ограничения:*
• Максимальный размер файла: {max_size} МБ
• Автоудаление файлов через: {cleanup_hours} часов

*Поддержка:*
Если сканер не отвечает, попробуйте перезапустить бота или проверьте подключение принтера.
        """.format(
            dpi=config.SCAN_DPI,
            mode=config.SCAN_MODE,
            format=config.SCAN_FORMAT,
            max_size=config.MAX_FILE_SIZE_MB,
            cleanup_hours=config.CLEANUP_AFTER_HOURS
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /scan"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        # Отправка уведомления о начале сканирования
        status_message = await update.message.reply_text("🔄 Начинаю сканирование...")
        
        try:
            logger.info(f"Пользователь {user_id} запросил сканирование")
            
            # Выполнение сканирования
            scan_file = await scanner.scan_document()
            
            if scan_file and scan_file.exists():
                # Обновление статуса
                await status_message.edit_text("📤 Отправляю отсканированный документ...")
                
                # Отправка файла
                with open(scan_file, 'rb') as file:
                    await update.message.reply_document(
                        document=file,
                        filename=scan_file.name,
                        caption=f"📄 Документ отсканирован\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                    )
                
                # Удаление статусного сообщения
                await status_message.delete()
                
                logger.info(f"Файл {scan_file.name} отправлен пользователю {user_id}")
                
            else:
                await status_message.edit_text("❌ Ошибка: файл сканирования не создан")
                
        except ScannerError as e:
            await status_message.edit_text(f"❌ Ошибка сканера: {e}")
            logger.error(f"Ошибка сканирования для пользователя {user_id}: {e}")
            
        except Exception as e:
            await status_message.edit_text(f"❌ Неожиданная ошибка: {e}")
            logger.error(f"Неожиданная ошибка при сканировании для пользователя {user_id}: {e}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        try:
            # Получение статуса сканера
            status = await scanner.get_scanner_status()
            
            status_emoji = {
                "ready": "✅",
                "not_initialized": "⚠️",
                "error": "❌"
            }.get(status["status"], "❓")
            
            status_text = f"""
{status_emoji} *Статус сканера*

*Состояние:* {status["message"]}
*Устройство:* {status.get("device", "Неизвестно")}
*Разрешение:* {status.get("dpi", config.SCAN_DPI)} DPI
*Режим:* {status.get("mode", config.SCAN_MODE)}
*Формат:* {status.get("format", config.SCAN_FORMAT)}

*Директория сканов:* `{config.SCAN_DIR}`
*Количество файлов:* {len(list(config.SCAN_DIR.glob("*"))) if config.SCAN_DIR.exists() else 0}
            """
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения статуса: {e}")
            logger.error(f"Ошибка получения статуса для пользователя {user_id}: {e}")
    
    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /cleanup"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        try:
            cleaned_count = await self._cleanup_old_files()
            
            if cleaned_count > 0:
                await update.message.reply_text(f"🗑️ Удалено {cleaned_count} старых файлов")
            else:
                await update.message.reply_text("✨ Нет файлов для удаления")
                
            logger.info(f"Пользователь {user_id} выполнил очистку: удалено {cleaned_count} файлов")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка очистки: {e}")
            logger.error(f"Ошибка очистки для пользователя {user_id}: {e}")
    
    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик неизвестных сообщений"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            return
        
        await update.message.reply_text(
            "❓ Неизвестная команда. Используйте /help для списка доступных команд."
        )
    
    async def _cleanup_old_files(self) -> int:
        """Очистка старых файлов сканирования"""
        try:
            if not config.SCAN_DIR.exists():
                return 0
            
            cutoff_time = datetime.now() - timedelta(hours=config.CLEANUP_AFTER_HOURS)
            cleaned_count = 0
            
            for file_path in config.SCAN_DIR.glob("*"):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_time:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.info(f"Удален старый файл: {file_path}")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки файлов: {e}")
            raise
    
    async def start_polling(self):
        """Запуск бота в режиме polling"""
        try:
            logger.info("Запуск Telegram бота...")
            
            # Инициализация сканера
            await scanner.initialize()
            
            # Создание задачи для автоочистки
            asyncio.create_task(self._auto_cleanup_task())
            
            # Запуск бота
            await self.application.run_polling(drop_pending_updates=True)
            
        except Exception as e:
            logger.error(f"Ошибка запуска бота: {e}")
            raise
        finally:
            # Очистка ресурсов
            scanner.cleanup()
    
    async def _auto_cleanup_task(self):
        """Автоматическая очистка старых файлов"""
        while True:
            try:
                await asyncio.sleep(3600)  # Проверка каждый час
                cleaned_count = await self._cleanup_old_files()
                if cleaned_count > 0:
                    logger.info(f"Автоочистка: удалено {cleaned_count} файлов")
            except Exception as e:
                logger.error(f"Ошибка автоочистки: {e}")

# Глобальный экземпляр бота
bot = ScanBot() 