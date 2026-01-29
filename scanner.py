"""
Модуль для работы со сканером HP Color LaserJet Pro MFP M177fw
"""
import sane
import asyncio
import aiofiles
from pathlib import Path
from PIL import Image
import logging
import tempfile
from datetime import datetime
from typing import Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor
import config

logger = logging.getLogger(__name__)

class ScannerError(Exception):
    """Исключение для ошибок сканера"""
    pass

class HPScanner:
    def __init__(self):
        self.device = None
        self.is_initialized = False
        
    async def initialize(self):
        """Инициализация сканера"""
        try:
            # Инициализация SANE
            sane.init()
            logger.info("SANE инициализирован")
            
            # Получение списка устройств
            devices = sane.get_devices()
            logger.info(f"Найдены устройства: {devices}")
            
            # Поиск HP принтера
            hp_device = None
            for device in devices:
                device_name = device[0]
                if 'hp' in device_name.lower() and 'm177' in device_name.lower():
                    hp_device = device_name
                    break
                elif config.SCANNER_DEVICE and device_name == config.SCANNER_DEVICE:
                    hp_device = device_name
                    break
            
            if not hp_device and devices:
                # Берем первое доступное устройство
                hp_device = devices[0][0]
                logger.warning(f"HP M177fw не найден, используем: {hp_device}")
            
            if not hp_device:
                raise ScannerError("Сканер не найден")
            
            # Открытие устройства
            self.device = sane.open(hp_device)
            logger.info(f"Сканер открыт: {hp_device}")
            
            # Настройка параметров сканирования
            await self._configure_scanner()
            
            self.is_initialized = True
            logger.info("Сканер успешно инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации сканера: {e}")
            raise ScannerError(f"Не удалось инициализировать сканер: {e}")
    
    async def _configure_scanner(self):
        """Настройка параметров сканера"""
        try:
            # Установка разрешения
            if hasattr(self.device, 'resolution'):
                self.device.resolution = config.SCAN_DPI
                logger.info(f"Установлено разрешение: {config.SCAN_DPI} DPI")
            
            # Установка режима сканирования
            if hasattr(self.device, 'mode'):
                self.device.mode = config.SCAN_MODE
                logger.info(f"Установлен режим: {config.SCAN_MODE}")
            
            # Для HP M177fw лучше использовать значения по умолчанию
            # Попробуем установить только начальные координаты
            try:
                if hasattr(self.device, 'tl_x'):
                    self.device.tl_x = 0
                if hasattr(self.device, 'tl_y'):
                    self.device.tl_y = 0
                logger.info("Установлены координаты начала сканирования")
            except Exception as coord_error:
                logger.warning(f"Не удалось установить координаты: {coord_error}")
            
            logger.info("Параметры сканера настроены")
            
        except Exception as e:
            logger.error(f"Ошибка настройки сканера: {e}")
            raise ScannerError(f"Не удалось настроить сканер: {e}")

    def _source_display_label(self, sane_value: str) -> str:
        """Маппинг значения SANE source на подпись для кнопки."""
        v = sane_value.lower().strip()
        if v in ('flatbed', 'планшет'):
            return "Планшет (под крышкой)"
        if v in ('adf', 'document feeder', 'feeder', 'автоподача', 'фидер'):
            return "Автоподача (фидер)"
        if 'flatbed' in v or 'планшет' in v:
            return "Планшет (под крышкой)"
        if 'feeder' in v or 'adf' in v or 'document' in v:
            return "Автоподача (фидер)"
        return sane_value

    def _get_scan_sources_sync(self) -> List[Tuple[str, str]]:
        """Синхронное получение списка источников сканирования из SANE (вызывать из executor)."""
        if not self.device:
            return []
        try:
            optlist = getattr(self.device, 'optlist', None) or []
            source_opt_name = None
            for name in ('source', 'scan-source', 'source-name'):
                if name in optlist:
                    source_opt_name = name
                    break
            if not source_opt_name:
                logger.debug("Опция выбора источника не найдена в optlist: %s", optlist)
                return []
            opt = self.device.opt.get(source_opt_name)
            if opt is None:
                return []
            constraint = getattr(opt, 'constraint', None)
            if not constraint or not isinstance(constraint, (list, tuple)):
                return []
            result = []
            for val in constraint:
                if isinstance(val, str) and val.strip():
                    label = self._source_display_label(val)
                    result.append((val, label))
            return result
        except Exception as e:
            logger.warning("Не удалось получить источники сканирования: %s", e)
            return []

    async def get_scan_sources(self) -> List[Tuple[str, str]]:
        """Список доступных источников сканирования: [(sane_value, display_label), ...]."""
        if not self.is_initialized:
            await self.initialize()
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, self._get_scan_sources_sync)
    
    async def scan_document(self, source: Optional[str] = None) -> Optional[Path]:
        """Сканирование документа. source — значение SANE для выбора источника (планшет/фидер)."""
        if not self.is_initialized:
            await self.initialize()
        
        try:
            if source:
                try:
                    optlist = getattr(self.device, 'optlist', None) or []
                    for name in ('source', 'scan-source', 'source-name'):
                        if name not in optlist:
                            continue
                        attr = name.replace('-', '_')
                        if hasattr(self.device, attr):
                            setattr(self.device, attr, source)
                            logger.info("Установлен источник сканирования: %s", source)
                            break
                except Exception as e:
                    logger.warning("Не удалось установить источник сканирования %s: %s", source, e)
            
            logger.info("Начало сканирования...")
            
            # Выполнение сканирования (совместимость с Python 3.7)
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                scan_data = await loop.run_in_executor(executor, self.device.scan)
            
            if not scan_data:
                raise ScannerError("Не удалось получить данные сканирования")
            
            logger.info(f"Тип данных сканирования: {type(scan_data)}")
            
            # Обработка разных типов данных от SANE
            if isinstance(scan_data, Image.Image):
                # Если уже PIL Image
                image = scan_data
                logger.info("Получен PIL Image напрямую")
            elif hasattr(scan_data, 'save'):
                # Если это PIL-подобный объект
                image = scan_data
                logger.info("Получен PIL-подобный объект")
            else:
                try:
                    # Попытка создать PIL Image из массива
                    import numpy as np
                    if isinstance(scan_data, np.ndarray):
                        image = Image.fromarray(scan_data)
                        logger.info("Создан PIL Image из numpy array")
                    else:
                        # Попытка конвертации в массив
                        scan_array = np.array(scan_data)
                        image = Image.fromarray(scan_array)
                        logger.info("Создан PIL Image через numpy.array()")
                except Exception as conv_error:
                    logger.error(f"Ошибка конвертации данных: {conv_error}")
                    # Последняя попытка - сохранить как есть
                    if hasattr(scan_data, 'mode') and hasattr(scan_data, 'size'):
                        image = scan_data
                        logger.info("Используем данные как есть")
                    else:
                        raise ScannerError(f"Неподдерживаемый тип данных сканирования: {type(scan_data)}")
            
            # Генерация имени файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"scan_{timestamp}.{config.SCAN_FORMAT.lower()}"
            filepath = config.SCAN_DIR / filename
            
            # Сохранение файла (совместимость с Python 3.7)
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(executor, lambda: image.save(filepath, config.SCAN_FORMAT))
            
            # Проверка размера файла
            file_size_mb = filepath.stat().st_size / (1024 * 1024)
            if file_size_mb > config.MAX_FILE_SIZE_MB:
                logger.warning(f"Файл больше {config.MAX_FILE_SIZE_MB}MB, сжимаем...")
                await self._compress_image(filepath)
            
            logger.info(f"Документ отсканирован: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Ошибка сканирования: {e}")
            raise ScannerError(f"Не удалось отсканировать документ: {e}")
    
    async def _compress_image(self, filepath: Path):
        """Сжатие изображения если оно слишком большое"""
        try:
            image = Image.open(filepath)
            
            # Уменьшение качества для JPEG
            if config.SCAN_FORMAT.upper() == 'JPEG':
                image.save(filepath, 'JPEG', quality=70, optimize=True)
            else:
                # Для PNG - уменьшение размера
                width, height = image.size
                new_size = (int(width * 0.8), int(height * 0.8))
                # Совместимость со старыми версиями Pillow
                try:
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
                except AttributeError:
                    image = image.resize(new_size, Image.LANCZOS)
                image.save(filepath, config.SCAN_FORMAT)
            
            logger.info(f"Изображение сжато: {filepath}")
            
        except Exception as e:
            logger.error(f"Ошибка сжатия изображения: {e}")
    
    async def get_scanner_status(self) -> dict:
        """Получение статуса сканера"""
        try:
            if not self.is_initialized:
                return {"status": "not_initialized", "message": "Сканер не инициализирован"}
            
            # Базовая информация о сканере
            status = {
                "status": "ready",
                "message": "Сканер готов к работе",
                "device": str(self.device) if self.device else "Неизвестно",
                "dpi": config.SCAN_DPI,
                "mode": config.SCAN_MODE,
                "format": config.SCAN_FORMAT
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Ошибка получения статуса: {e}")
            return {"status": "error", "message": f"Ошибка: {e}"}
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if self.device:
                self.device.close()
                logger.info("Устройство сканера закрыто")
            
            sane.exit()
            logger.info("SANE завершен")
            
        except Exception as e:
            logger.error(f"Ошибка при очистке ресурсов: {e}")

# Глобальный экземпляр сканера
scanner = HPScanner() 