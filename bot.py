"""
Telegram бот для сканирования документов
"""
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
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
            
            # Обработчик для callback запросов (кнопки)
            self.application.add_handler(CallbackQueryHandler(self.button_callback))
            
            # Обработчик для неизвестных команд
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.unknown_command))
            
            logger.info("Telegram бот инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации бота: {e}")
            raise
    
    def _is_authorized(self, update: Update) -> bool:
        """Проверка авторизации пользователя или чата"""
        # Если список пуст, разрешаем всем
        if not config.TELEGRAM_CHAT_IDS:
            return True
        
        # Проверяем ID пользователя (для личных сообщений)
        user_id = update.effective_user.id if update.effective_user else None
        if user_id and user_id in config.TELEGRAM_CHAT_IDS:
            logger.debug(f"Авторизация по user_id: {user_id}")
            return True
        
        # Проверяем ID чата (для групп и каналов)
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id and chat_id in config.TELEGRAM_CHAT_IDS:
            logger.debug(f"Авторизация по chat_id: {chat_id}")
            return True
        
        logger.warning(f"Доступ запрещен: user_id={user_id}, chat_id={chat_id}, разрешенные={config.TELEGRAM_CHAT_IDS}")
        return False
    
    def _get_main_keyboard(self):
        """Создание основной клавиатуры с кнопками"""
        keyboard = [
            [
                InlineKeyboardButton("🖨️ Сканировать документ", callback_data="scan"),
                InlineKeyboardButton("📊 Статус сканера", callback_data="status")
            ],
            [
                InlineKeyboardButton("🗑️ Очистить старые файлы", callback_data="cleanup"),
                InlineKeyboardButton("❓ Помощь", callback_data="help")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(update):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        welcome_text = """🖨️ *HP M177fw Scanner Bot*

Добро пожаловать! Этот бот поможет вам сканировать документы удаленно.

Выберите действие из меню ниже:"""
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode='Markdown',
            reply_markup=self._get_main_keyboard()
        )
        logger.info(f"Пользователь {user_id} запустил бота")
        
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        user_id = query.from_user.id
        
        if not self._is_authorized(update):
            await query.answer("❌ У вас нет доступа к этому боту.")
            return
        
        await query.answer()  # Убираем "часики" с кнопки
        
        if query.data == "scan":
            await self._handle_scan_callback(query)
        elif query.data == "status":
            await self._handle_status_callback(query)
        elif query.data == "cleanup":
            await self._handle_cleanup_callback(query)
        elif query.data == "help":
            await self._handle_help_callback(query)
        elif query.data == "back_to_menu":
            await self._handle_back_to_menu(query)
    
    async def _handle_scan_callback(self, query):
        """Обработка нажатия кнопки сканирования"""
        user_id = query.from_user.id
        
        # Обновляем сообщение на статус сканирования
        await query.edit_message_text("🔄 Начинаю сканирование...\n\nПожалуйста, подождите...")
        
        try:
            logger.info(f"Пользователь {user_id} запросил сканирование через кнопку")
            
            # Выполнение сканирования
            scan_file = await scanner.scan_document()
            
            if scan_file and scan_file.exists():
                # Обновление статуса
                await query.edit_message_text("📤 Отправляю отсканированный документ...")
                
                # Отправка файла
                with open(scan_file, 'rb') as file:
                    await query.message.reply_document(
                        document=file,
                        filename=scan_file.name,
                        caption=f"📄 Документ отсканирован\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                    )
                
                # Возвращаемся к главному меню
                await query.edit_message_text(
                    "✅ Документ успешно отсканирован и отправлен!\n\nВыберите следующее действие:",
                    reply_markup=self._get_main_keyboard()
                )
                
                logger.info(f"Файл {scan_file.name} отправлен пользователю {user_id}")
                
            else:
                await query.edit_message_text(
                    "❌ Ошибка: файл сканирования не создан\n\nПопробуйте еще раз или проверьте статус сканера.",
                    reply_markup=self._get_main_keyboard()
                )
                
        except ScannerError as e:
            await query.edit_message_text(
                f"❌ Ошибка сканера: {e}\n\nПопробуйте еще раз или обратитесь к администратору.",
                reply_markup=self._get_main_keyboard()
            )
            logger.error(f"Ошибка сканирования для пользователя {user_id}: {e}")
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Неожиданная ошибка: {e}\n\nПопробуйте еще раз позже.",
                reply_markup=self._get_main_keyboard()
            )
            logger.error(f"Неожиданная ошибка при сканировании для пользователя {user_id}: {e}")
    
    async def _handle_status_callback(self, query):
        """Обработка нажатия кнопки статуса"""
        user_id = query.from_user.id
        
        try:
            # Обновляем сообщение на загрузку
            await query.edit_message_text("🔄 Получаю статус сканера...")
            
            # Получение статуса сканера
            status = await scanner.get_scanner_status()
            
            status_emoji = {
                "ready": "✅",
                "not_initialized": "⚠️",
                "error": "❌"
            }.get(status["status"], "❓")
            
            status_text = f"""{status_emoji} *Статус сканера*

*Состояние:* {status["message"]}
*Устройство:* {status.get("device", "Неизвестно")}
*Разрешение:* {status.get("dpi", config.SCAN_DPI)} DPI
*Режим:* {status.get("mode", config.SCAN_MODE)}
*Формат:* {status.get("format", config.SCAN_FORMAT)}

*Директория сканов:* `{config.SCAN_DIR}`
*Количество файлов:* {len(list(config.SCAN_DIR.glob("*"))) if config.SCAN_DIR.exists() else 0}"""
            
            # Кнопка возврата к меню
            back_keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]]
            
            await query.edit_message_text(
                status_text, 
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(back_keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Ошибка получения статуса: {e}",
                reply_markup=self._get_main_keyboard()
            )
            logger.error(f"Ошибка получения статуса для пользователя {user_id}: {e}")
    
    async def _handle_cleanup_callback(self, query):
        """Обработка нажатия кнопки очистки"""
        user_id = query.from_user.id
        
        try:
            await query.edit_message_text("🔄 Выполняю очистку старых файлов...")
            
            cleaned_count = await self._cleanup_old_files()
            
            if cleaned_count > 0:
                result_text = f"🗑️ Очистка завершена!\n\nУдалено файлов: {cleaned_count}"
            else:
                result_text = "✨ Все файлы актуальны!\n\nНет файлов для удаления."
                
            # Кнопка возврата к меню
            back_keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]]
            
            await query.edit_message_text(
                result_text,
                reply_markup=InlineKeyboardMarkup(back_keyboard)
            )
                
            logger.info(f"Пользователь {user_id} выполнил очистку: удалено {cleaned_count} файлов")
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Ошибка очистки: {e}",
                reply_markup=self._get_main_keyboard()
            )
            logger.error(f"Ошибка очистки для пользователя {user_id}: {e}")
    
    async def _handle_help_callback(self, query):
        """Обработка нажатия кнопки помощи"""
        help_text = f"""🔧 *Помощь по использованию бота*

*Основные функции:*
• 🖨️ *Сканирование* - создает PDF/JPEG файл документа
• 📊 *Статус* - показывает состояние сканера  
• 🗑️ *Очистка* - удаляет старые файлы сканирования
• ❓ *Помощь* - это сообщение

*Настройки сканирования:*
• Разрешение: {config.SCAN_DPI} DPI
• Режим: {config.SCAN_MODE}
• Формат: {config.SCAN_FORMAT}

*Автоматика:*
• Файлы удаляются автоматически через {config.CLEANUP_AFTER_HOURS} часов
• Максимальный размер файла: {config.MAX_FILE_SIZE_MB} МБ

*Поддержка:*
Если сканер не отвечает, попробуйте проверить:
1. Включен ли принтер
2. Подключен ли к сети Wi-Fi
3. Нет ли бумаги в лотке"""
        
        # Кнопка возврата к меню
        back_keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]]
        
        await query.edit_message_text(
            help_text, 
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(back_keyboard)
        )
    
    async def _handle_back_to_menu(self, query):
        """Возврат к главному меню"""
        await query.edit_message_text(
            "🖨️ *HP M177fw Scanner Bot*\n\nВыберите действие:",
            parse_mode='Markdown',
            reply_markup=self._get_main_keyboard()
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(update):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        help_text = f"""🔧 *Помощь по использованию бота*

*Основные функции:*
• 🖨️ *Сканирование* - создает PDF/JPEG файл документа
• 📊 *Статус* - показывает состояние сканера  
• 🗑️ *Очистка* - удаляет старые файлы сканирования
• ❓ *Помощь* - это сообщение

*Настройки сканирования:*
• Разрешение: {config.SCAN_DPI} DPI
• Режим: {config.SCAN_MODE}
• Формат: {config.SCAN_FORMAT}

*Автоматика:*
• Файлы удаляются автоматически через {config.CLEANUP_AFTER_HOURS} часов
• Максимальный размер файла: {config.MAX_FILE_SIZE_MB} МБ

*Поддержка:*
Если сканер не отвечает, попробуйте проверить:
1. Включен ли принтер
2. Подключен ли к сети Wi-Fi
3. Нет ли бумаги в лотке

Используйте кнопки ниже или команды: /scan, /status, /cleanup"""
        
        await update.message.reply_text(
            help_text, 
            parse_mode='Markdown',
            reply_markup=self._get_main_keyboard()
        )
    
    async def scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /scan"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(update):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        # Отправка уведомления о начале сканирования
        status_message = await update.message.reply_text("🔄 Начинаю сканирование...\n\nПожалуйста, подождите...")
        
        try:
            logger.info(f"Пользователь {user_id} запросил сканирование через команду")
            
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
                
                # Удаление статусного сообщения и показ меню
                await status_message.delete()
                await update.message.reply_text(
                    "✅ Документ успешно отсканирован и отправлен!\n\nВыберите следующее действие:",
                    reply_markup=self._get_main_keyboard()
                )
                
                logger.info(f"Файл {scan_file.name} отправлен пользователю {user_id}")
                
            else:
                await status_message.edit_text(
                    "❌ Ошибка: файл сканирования не создан\n\nПопробуйте еще раз или проверьте статус сканера.",
                    reply_markup=self._get_main_keyboard()
                )
                
        except ScannerError as e:
            await status_message.edit_text(
                f"❌ Ошибка сканера: {e}\n\nПопробуйте еще раз или обратитесь к администратору.",
                reply_markup=self._get_main_keyboard()
            )
            logger.error(f"Ошибка сканирования для пользователя {user_id}: {e}")
            
        except Exception as e:
            await status_message.edit_text(
                f"❌ Неожиданная ошибка: {e}\n\nПопробуйте еще раз позже.",
                reply_markup=self._get_main_keyboard()
            )
            logger.error(f"Неожиданная ошибка при сканировании для пользователя {user_id}: {e}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(update):
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
            
            await update.message.reply_text(
                status_text, 
                parse_mode='Markdown',
                reply_markup=self._get_main_keyboard()
            )
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка получения статуса: {e}",
                reply_markup=self._get_main_keyboard()
            )
            logger.error(f"Ошибка получения статуса для пользователя {user_id}: {e}")
    
    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /cleanup"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(update):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        try:
            cleaned_count = await self._cleanup_old_files()
            
            if cleaned_count > 0:
                result_text = f"🗑️ Очистка завершена!\n\nУдалено файлов: {cleaned_count}"
            else:
                result_text = "✨ Все файлы актуальны!\n\nНет файлов для удаления."
                
            await update.message.reply_text(
                result_text,
                reply_markup=self._get_main_keyboard()
            )
                
            logger.info(f"Пользователь {user_id} выполнил очистку: удалено {cleaned_count} файлов")
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка очистки: {e}",
                reply_markup=self._get_main_keyboard()
            )
            logger.error(f"Ошибка очистки для пользователя {user_id}: {e}")
    
    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик неизвестных сообщений"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(update):
            return
        
        await update.message.reply_text(
            "❓ Неизвестная команда или сообщение.\n\nВыберите действие из меню ниже:",
            reply_markup=self._get_main_keyboard()
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
            
            # Сканер будет инициализирован лениво при первом запросе сканирования
            logger.info("Сканер будет инициализирован при первом запросе сканирования")
            
            # Создание задачи для автоочистки
            logger.info("Создаю задачу автоочистки...")
            cleanup_task = asyncio.create_task(self._auto_cleanup_task())
            
            try:
                # Инициализация и запуск бота в существующем event loop
                logger.info("Инициализирую приложение...")
                await self.application.initialize()
                
                logger.info("Запускаю updater...")
                await self.application.updater.start_polling(drop_pending_updates=True)
                
                logger.info("Запускаю обработку...")
                await self.application.start()
                
                # Ожидание завершения (бесконечный цикл)
                logger.info("Бот запущен. Ожидаю сообщения...")
                while True:
                    await asyncio.sleep(1)
                    
            finally:
                # Корректное завершение
                logger.info("Останавливаю бота...")
                try:
                    await self.application.stop()
                    await self.application.updater.stop()
                    await self.application.shutdown()
                except Exception as stop_error:
                    logger.error(f"Ошибка при остановке бота: {stop_error}")
                
                # Отменяем задачу автоочистки
                logger.info("Отменяю задачу автоочистки...")
                cleanup_task.cancel()
                try:
                    await cleanup_task
                except asyncio.CancelledError:
                    logger.info("Задача автоочистки отменена")
            
        except Exception as e:
            import traceback
            logger.error(f"Ошибка запуска бота: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
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