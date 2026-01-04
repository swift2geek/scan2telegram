"""
Telegram бот для сканирования документов
"""
import asyncio
import logging
import html
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
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
from printer import printer, PrinterError

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
            
            # Обработчик для печати файлов (файлы с упоминанием бота)
            # Используем filters.ALL чтобы получать ВСЕ сообщения, включая упоминания в группах
            # Проверка файла и упоминания делается внутри обработчика
            self.application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, self.handle_all_messages))
            
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
                InlineKeyboardButton("🖨️ Распечатать", callback_data="print"),
                InlineKeyboardButton("🗑️ Очистить старые файлы", callback_data="cleanup")
            ],
            [
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
        elif query.data == "print":
            await self._handle_print_callback(query, context)
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
• 🖨️ *Распечатать* - отправляет файлы на печать (нажмите кнопку и отправьте файл)
• 📊 *Статус* - показывает состояние сканера и принтера
• 🗑️ *Очистка* - удаляет старые файлы сканирования
• ❓ *Помощь* - это сообщение

*Настройки сканирования:*
• Разрешение: {config.SCAN_DPI} DPI
• Режим: {config.SCAN_MODE}
• Формат: {config.SCAN_FORMAT}

*Печать файлов:*
*Способ 1 (через кнопку):*
• Нажмите кнопку "🖨️ Распечатать"
• Отправьте файл в ответ на сообщение бота
• Бот автоматически обработает и отправит файл на печать

*Способ 2 (через упоминание):*
• Отправьте файл (фото, PDF, документ) в группу
• Упомяните бота в сообщении: @scan_2_telegram_bot
• Бот автоматически отправит файл на печать

*Поддерживаемые форматы для печати:*
• Изображения: JPG, PNG, GIF, BMP, TIFF
• Документы: PDF, DOCX, DOC, TXT
• Другие форматы обрабатываются автоматически

*Автоматика:*
• Файлы удаляются автоматически через {config.CLEANUP_AFTER_HOURS} часов
• Максимальный размер файла: {config.MAX_FILE_SIZE_MB} МБ

*Поддержка:*
Если сканер или принтер не отвечают, попробуйте проверить:
1. Включен ли принтер
2. Подключен ли к сети Wi-Fi
3. Нет ли бумаги в лотке
4. Используйте команду /status для проверки статуса"""
        
        # Кнопка возврата к меню
        back_keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]]
        
        await query.edit_message_text(
            help_text, 
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(back_keyboard)
        )
    
    async def _handle_print_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатия кнопки печати"""
        user_id = query.from_user.id
        
        # Устанавливаем флаг ожидания файла для печати
        context.user_data['waiting_for_print'] = True
        
        # Кнопка возврата к меню
        back_keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]]
        
        await query.edit_message_text(
            "🖨️ *Распечатать документ*\n\n"
            "Отправьте файл для печати (PDF, DOCX, изображения или другие поддерживаемые форматы).\n\n"
            "Файл будет автоматически обработан и отправлен на принтер.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(back_keyboard)
        )
        
        logger.info(f"Пользователь {user_id} запросил печать через кнопку")
    
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
• 🖨️ *Распечатать* - отправляет файлы на печать (нажмите кнопку и отправьте файл)
• 📊 *Статус* - показывает состояние сканера и принтера
• 🗑️ *Очистка* - удаляет старые файлы сканирования
• ❓ *Помощь* - это сообщение

*Настройки сканирования:*
• Разрешение: {config.SCAN_DPI} DPI
• Режим: {config.SCAN_MODE}
• Формат: {config.SCAN_FORMAT}

*Печать файлов:*
*Способ 1 (через кнопку):*
• Нажмите кнопку "🖨️ Распечатать"
• Отправьте файл в ответ на сообщение бота
• Бот автоматически обработает и отправит файл на печать

*Способ 2 (через упоминание):*
• Отправьте файл (фото, PDF, документ) в группу
• Упомяните бота в сообщении: @scan_2_telegram_bot
• Бот автоматически отправит файл на печать

*Поддерживаемые форматы для печати:*
• Изображения: JPG, PNG, GIF, BMP, TIFF
• Документы: PDF, DOCX, DOC, TXT
• Другие форматы обрабатываются автоматически

*Автоматика:*
• Файлы удаляются автоматически через {config.CLEANUP_AFTER_HOURS} часов
• Максимальный размер файла: {config.MAX_FILE_SIZE_MB} МБ

*Поддержка:*
Если сканер или принтер не отвечают, попробуйте проверить:
1. Включен ли принтер
2. Подключен ли к сети Wi-Fi
3. Нет ли бумаги в лотке
4. Используйте команду /status для проверки статуса

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
            scanner_status = await scanner.get_scanner_status()
            
            # Получение статуса принтера
            printer_status = await printer.get_printer_status()
            
            scanner_emoji = {
                "ready": "✅",
                "not_initialized": "⚠️",
                "error": "❌"
            }.get(scanner_status["status"], "❓")
            
            printer_emoji = {
                "ready": "✅",
                "busy": "🔄",
                "error": "❌"
            }.get(printer_status["status"], "❓")
            
            # Экранируем все поля для безопасного отображения в Markdown
            scanner_message = html.escape(str(scanner_status.get("message", "Неизвестно")))
            scanner_device = html.escape(str(scanner_status.get("device", "Неизвестно")))
            scanner_dpi = str(scanner_status.get("dpi", config.SCAN_DPI))
            scanner_mode = html.escape(str(scanner_status.get("mode", config.SCAN_MODE)))
            scanner_format = html.escape(str(scanner_status.get("format", config.SCAN_FORMAT)))
            
            printer_message = html.escape(str(printer_status.get("message", "Неизвестно")))
            printer_name = html.escape(str(printer_status.get("name", config.PRINTER_NAME)))
            
            scan_dir = html.escape(str(config.SCAN_DIR))
            file_count = len(list(config.SCAN_DIR.glob("*"))) if config.SCAN_DIR.exists() else 0
            
            status_text = f"""
{scanner_emoji} *Статус сканера*

*Состояние:* {scanner_message}
*Устройство:* {scanner_device}
*Разрешение:* {scanner_dpi} DPI
*Режим:* {scanner_mode}
*Формат:* {scanner_format}

{printer_emoji} *Статус принтера*

*Состояние:* {printer_message}
*Принтер:* {printer_name}

*Директория сканов:* `{scan_dir}`
*Количество файлов:* {file_count}
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
    
    async def handle_all_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик всех сообщений - логирует и перенаправляет на печать если нужно"""
        # Логируем все входящие сообщения для отладки
        user_id = update.effective_user.id if update.effective_user else "unknown"
        chat_id = update.effective_chat.id if update.effective_chat else "unknown"
        has_photo = bool(update.message and update.message.photo)
        has_document = bool(update.message and update.message.document)
        caption = update.message.caption if update.message else None
        text = update.message.text if update.message else None
        
        logger.info(f"📨 Получено сообщение: user={user_id}, chat={chat_id}, photo={has_photo}, doc={has_document}, caption={caption}, text={text}")
        
        # Если есть файл (фото или документ), обрабатываем как запрос на печать
        if has_photo or has_document:
            await self.handle_print_request(update, context)
        # Иначе - игнорируем (текстовые сообщения без команд)
    
    async def handle_print_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик запросов на печать файлов"""
        logger.info(f"Обработка файла для печати от пользователя {update.effective_user.id}")
        
        if not self._is_authorized(update):
            logger.debug("Запрос на печать от неавторизованного пользователя")
            return
        
        # Проверяем, ожидает ли бот файл от пользователя (нажата кнопка "Распечатать")
        waiting_for_print = context.user_data.get('waiting_for_print', False)
        
        # Проверяем, что бот упомянут в сообщении или в подписи к файлу
        bot_mentioned = False
        bot_username = (await self.bot.get_me()).username.lower()
        
        logger.info(f"Проверка упоминания бота. Username: {bot_username}, waiting_for_print: {waiting_for_print}")
        
        # Проверяем упоминания в тексте сообщения
        if update.message.text:
            text_lower = update.message.text.lower()
            logger.info(f"Текст сообщения: {text_lower}")
            if f"@{bot_username}" in text_lower:
                bot_mentioned = True
                logger.info(f"✅ Бот упомянут в тексте сообщения")
        
        # Проверяем упоминания в entities
        if not bot_mentioned and update.message.entities:
            for entity in update.message.entities:
                if entity.type == MessageEntity.MENTION:
                    mention_text = update.message.text[entity.offset:entity.offset + entity.length].lower()
                    logger.info(f"Найдено упоминание в entities: {mention_text}")
                    if f"@{bot_username}" in mention_text:
                        bot_mentioned = True
                        logger.info(f"✅ Бот упомянут через entity")
                        break
        
        # Проверяем упоминания в подписи к файлу
        if not bot_mentioned and update.message.caption:
            caption_lower = update.message.caption.lower()
            logger.info(f"Подпись к файлу: {caption_lower}")
            if f"@{bot_username}" in caption_lower:
                bot_mentioned = True
                logger.info(f"✅ Бот упомянут в подписи к файлу")
        
        # Проверяем упоминания в caption_entities
        if not bot_mentioned and update.message.caption_entities:
            for entity in update.message.caption_entities:
                if entity.type == MessageEntity.MENTION:
                    mention_text = update.message.caption[entity.offset:entity.offset + entity.length].lower()
                    logger.info(f"Найдено упоминание в caption_entities: {mention_text}")
                    if f"@{bot_username}" in mention_text:
                        bot_mentioned = True
                        logger.info(f"✅ Бот упомянут через caption_entity")
                        break
        
        # Если бот не упомянут и пользователь не нажал кнопку "Распечатать", игнорируем сообщение
        if not bot_mentioned and not waiting_for_print:
            logger.info(f"❌ Бот не упомянут в сообщении и не ожидается файл, игнорируем. Username для проверки: @{bot_username}")
            return
        
        logger.info(f"Обработка запроса на печать от пользователя {update.effective_user.id}")
        
        user_id = update.effective_user.id
        status_message = await update.message.reply_text("🖨️ Подготовка файла к печати...")
        
        try:
            # Определяем тип файла и получаем его
            file_to_download = None
            file_name = None
            
            if update.message.document:
                file_to_download = update.message.document
                file_name = file_to_download.file_name or f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            elif update.message.photo:
                # Берем фото наибольшего размера
                file_to_download = update.message.photo[-1]
                file_name = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            elif update.message.sticker:
                # Обработка стикеров (конвертируем в изображение)
                file_to_download = update.message.sticker
                file_name = f"sticker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            else:
                await status_message.edit_text("❌ Не удалось определить тип файла для печати.")
                return
            
            # Скачиваем файл
            await status_message.edit_text("📥 Скачиваю файл...")
            file = await file_to_download.get_file()
            
            # Сохраняем во временную директорию
            temp_file = config.PRINT_TEMP_DIR / file_name
            await file.download_to_drive(temp_file)
            
            logger.info(f"Пользователь {user_id} запросил печать файла: {file_name}")
            
            # Отправляем на печать
            await status_message.edit_text("🖨️ Отправляю на печать...")
            success = await printer.print_file(temp_file)
            
            # Сбрасываем флаг ожидания файла после обработки
            context.user_data['waiting_for_print'] = False
            
            if success:
                await status_message.edit_text(
                    f"✅ Файл отправлен на печать!\n\n"
                    f"📄 Файл: {file_name}\n"
                    f"🖨️ Принтер: {config.PRINTER_NAME}\n"
                    f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
                    reply_markup=self._get_main_keyboard()
                )
                logger.info(f"Файл {file_name} успешно отправлен на печать пользователем {user_id}")
            else:
                await status_message.edit_text(
                    "❌ Не удалось отправить файл на печать. Проверьте статус принтера.",
                    reply_markup=self._get_main_keyboard()
                )
                
        except PrinterError as e:
            # Сбрасываем флаг ожидания файла при ошибке
            context.user_data['waiting_for_print'] = False
            await status_message.edit_text(
                f"❌ Ошибка печати: {e}\n\nПроверьте статус принтера командой /status",
                reply_markup=self._get_main_keyboard()
            )
            logger.error(f"Ошибка печати для пользователя {user_id}: {e}")
        except Exception as e:
            # Сбрасываем флаг ожидания файла при ошибке
            context.user_data['waiting_for_print'] = False
            await status_message.edit_text(
                f"❌ Неожиданная ошибка: {e}\n\nПопробуйте еще раз позже.",
                reply_markup=self._get_main_keyboard()
            )
            logger.error(f"Неожиданная ошибка при печати для пользователя {user_id}: {e}")
        finally:
            # Очистка временного файла
            if 'temp_file' in locals() and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный файл {temp_file}: {e}")
    
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