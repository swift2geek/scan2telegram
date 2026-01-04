"""
Модуль для работы с принтером HP Color LaserJet Pro MFP M177fw
"""
import subprocess
import logging
import tempfile
import os
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
import asyncio
import config

logger = logging.getLogger(__name__)

class PrinterError(Exception):
    """Исключение для ошибок принтера"""
    pass

class Printer:
    def __init__(self):
        self.printer_name = config.PRINTER_NAME
        self.temp_dir = Path(config.PRINT_TEMP_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    async def print_file(self, file_path: Path, printer_name: Optional[str] = None) -> bool:
        """
        Печать файла
        
        Args:
            file_path: Путь к файлу для печати
            printer_name: Имя принтера (если None, используется из конфига)
        
        Returns:
            True если печать успешна, False в противном случае
        """
        if not file_path.exists():
            raise PrinterError(f"Файл не найден: {file_path}")
        
        printer = printer_name or self.printer_name
        
        # Проверка доступности принтера
        if not await self._check_printer_status(printer):
            raise PrinterError(f"Принтер {printer} недоступен")
        
        # Проверка размера файла
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > config.MAX_FILE_SIZE_MB:
            raise PrinterError(f"Файл слишком большой: {file_size_mb:.2f}MB (максимум {config.MAX_FILE_SIZE_MB}MB)")
        
        try:
            # Подготовка файла для печати (конвертация при необходимости)
            print_file = await self._prepare_file_for_printing(file_path)
            
            # Отправка на печать
            logger.info(f"Отправка файла {print_file} на принтер {printer}")
            result = await self._send_to_printer(print_file, printer)
            
            # Очистка временного файла, если он был создан
            if print_file != file_path and print_file.exists():
                try:
                    print_file.unlink()
                    logger.debug(f"Временный файл {print_file} удален")
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный файл {print_file}: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка печати файла {file_path}: {e}")
            raise PrinterError(f"Не удалось распечатать файл: {e}")
    
    async def _check_printer_status(self, printer_name: str) -> bool:
        """Проверка доступности принтера"""
        try:
            logger.info(f"Проверка доступности принтера: {printer_name}")
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    lambda: subprocess.run(
                        ['/usr/bin/lpstat', '-p', printer_name],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                )
            
            logger.info(f"lpstat вернул код: {result.returncode}, stdout: {result.stdout[:100]}, stderr: {result.stderr[:100] if result.stderr else 'None'}")
            
            if result.returncode == 0:
                # Проверяем, что принтер не отключен
                output_lower = result.stdout.lower()
                if 'disabled' in output_lower:
                    logger.warning(f"Принтер {printer_name} отключен")
                    return False
                if 'offline' in output_lower:
                    logger.warning(f"Принтер {printer_name} оффлайн")
                    return False
                logger.info(f"Принтер {printer_name} доступен")
                return True
            else:
                error_msg = result.stderr.strip() if result.stderr else "Неизвестная ошибка"
                logger.error(f"Принтер {printer_name} не найден или недоступен: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка проверки принтера {printer_name}: {e}", exc_info=True)
            return False
    
    async def _prepare_file_for_printing(self, file_path: Path) -> Path:
        """
        Подготовка файла для печати
        Конвертирует файл в поддерживаемый формат при необходимости
        """
        suffix = file_path.suffix.lower()
        
        # Файлы, которые можно печатать напрямую
        if suffix in ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif']:
            return file_path
        
        # Документы Word - конвертируем в PDF через pandoc
        if suffix in ['.docx', '.doc']:
            return await self._convert_docx_to_pdf(file_path)
        
        # Текстовые файлы - конвертируем в PDF
        if suffix in ['.txt', '.text', '.log']:
            return await self._convert_text_to_pdf(file_path)
        
        # Другие форматы - попытка печати как есть
        logger.warning(f"Неизвестный формат файла {suffix}, попытка печати как есть")
        return file_path
    
    async def _convert_text_to_pdf(self, file_path: Path) -> Path:
        """Конвертация текстового файла в PDF"""
        try:
            # Используем enscript для конвертации текста в PostScript, затем ps2pdf
            output_pdf = self.temp_dir / f"{file_path.stem}_print.pdf"
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                # Попытка использовать enscript
                result = await loop.run_in_executor(
                    executor,
                    lambda: subprocess.run(
                        ['which', 'enscript'],
                        capture_output=True,
                        text=True
                    )
                )
                
                if result.returncode == 0:
                    # Конвертация через enscript -> ps2pdf
                    ps_file = self.temp_dir / f"{file_path.stem}_print.ps"
                    
                    # enscript: текст -> PostScript
                    result = await loop.run_in_executor(
                        executor,
                        lambda: subprocess.run(
                            ['enscript', '-p', str(ps_file), str(file_path)],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                    )
                    
                    if result.returncode == 0 and ps_file.exists():
                        # ps2pdf: PostScript -> PDF
                        result = await loop.run_in_executor(
                            executor,
                            lambda: subprocess.run(
                                ['ps2pdf', str(ps_file), str(output_pdf)],
                                capture_output=True,
                                text=True,
                                timeout=30
                            )
                        )
                        
                        # Удаляем временный PS файл
                        if ps_file.exists():
                            ps_file.unlink()
                        
                        if result.returncode == 0 and output_pdf.exists():
                            logger.info(f"Текстовый файл конвертирован в PDF: {output_pdf}")
                            return output_pdf
                
                # Если enscript недоступен, пробуем через a2ps или просто печатаем как есть
                logger.warning("enscript недоступен, пробуем a2ps")
                result = await loop.run_in_executor(
                    executor,
                    lambda: subprocess.run(
                        ['which', 'a2ps'],
                        capture_output=True,
                        text=True
                    )
                )
                
                if result.returncode == 0:
                    # a2ps: текст -> PostScript -> PDF
                    ps_file = self.temp_dir / f"{file_path.stem}_print.ps"
                    result = await loop.run_in_executor(
                        executor,
                        lambda: subprocess.run(
                            ['a2ps', '-o', str(ps_file), str(file_path)],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                    )
                    
                    if result.returncode == 0 and ps_file.exists():
                        result = await loop.run_in_executor(
                            executor,
                            lambda: subprocess.run(
                                ['ps2pdf', str(ps_file), str(output_pdf)],
                                capture_output=True,
                                text=True,
                                timeout=30
                            )
                        )
                        
                        if ps_file.exists():
                            ps_file.unlink()
                        
                        if result.returncode == 0 and output_pdf.exists():
                            logger.info(f"Текстовый файл конвертирован в PDF: {output_pdf}")
                            return output_pdf
                
                # Если ничего не помогло, возвращаем исходный файл
                logger.warning("Не удалось конвертировать текст в PDF, печатаем как есть")
                return file_path
                
        except Exception as e:
            logger.error(f"Ошибка конвертации текста в PDF: {e}")
            # Если конвертация не удалась, возвращаем исходный файл
            return file_path
    
    async def _convert_docx_to_pdf(self, file_path: Path) -> Path:
        """Конвертация DOCX/DOC в PDF через LibreOffice"""
        try:
            output_pdf = self.temp_dir / f"{file_path.stem}_print.pdf"
            
            logger.info(f"Конвертирую DOCX файл {file_path} в PDF через LibreOffice")
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                # LibreOffice конвертирует в директорию, поэтому нужно указать выходную директорию
                output_dir = output_pdf.parent
                
                # Устанавливаем PATH для поиска LibreOffice
                env = os.environ.copy()
                env['PATH'] = '/usr/bin:/usr/local/bin:/bin:' + env.get('PATH', '')
                env['HOME'] = str(self.temp_dir)  # Устанавливаем HOME для LibreOffice
                
                result = await loop.run_in_executor(
                    executor,
                    lambda: subprocess.run(
                        [
                            '/usr/bin/libreoffice',
                            '--headless',
                            '--convert-to', 'pdf',
                            '--outdir', str(output_dir),
                            str(file_path)
                        ],
                        capture_output=True,
                        text=True,
                        timeout=120,
                        env=env
                    )
                )
            
            # LibreOffice создает файл с тем же именем, но расширением .pdf
            expected_pdf = output_dir / f"{file_path.stem}.pdf"
            
            if result.returncode == 0 and expected_pdf.exists():
                # Переименовываем в нужное имя, если нужно
                if expected_pdf != output_pdf:
                    expected_pdf.rename(output_pdf)
                logger.info(f"DOCX файл конвертирован в PDF: {output_pdf}")
                return output_pdf
            else:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                logger.error(f"Ошибка конвертации DOCX в PDF: {error_msg}")
                raise PrinterError(f"Не удалось конвертировать DOCX в PDF: {error_msg}")
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут при конвертации DOCX в PDF")
            raise PrinterError("Таймаут при конвертации DOCX в PDF")
        except FileNotFoundError:
            raise PrinterError("Утилита 'libreoffice' не найдена. Установите её: sudo apt install libreoffice")
        except Exception as e:
            logger.error(f"Ошибка конвертации DOCX в PDF: {e}")
            raise PrinterError(f"Не удалось конвертировать DOCX в PDF: {e}")
    
    async def _send_to_printer(self, file_path: Path, printer_name: str) -> bool:
        """Отправка файла на принтер через lp"""
        try:
            # Определяем тип файла для правильных опций печати
            suffix = file_path.suffix.lower()
            lp_options = []
            
            # Для PDF файлов добавляем опции для правильной печати
            if suffix == '.pdf':
                lp_options = ['-o', 'media=A4', '-o', 'fit-to-page']
                logger.info(f"Печать PDF файла с опциями: {lp_options}")
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                # Формируем команду lp с опциями
                lp_command = ['/usr/bin/lp', '-d', printer_name] + lp_options + [str(file_path)]
                logger.info(f"Выполняю команду: {' '.join(lp_command)}")
                
                result = await loop.run_in_executor(
                    executor,
                    lambda: subprocess.run(
                        lp_command,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                )
            
            if result.returncode == 0:
                job_id = result.stdout.strip().split()[-1] if result.stdout.strip() else "unknown"
                logger.info(f"Файл отправлен на печать. Job ID: {job_id}")
                return True
            else:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                logger.error(f"Ошибка отправки на печать: {error_msg}")
                raise PrinterError(f"Ошибка CUPS: {error_msg}")
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут при отправке на печать")
            raise PrinterError("Таймаут при отправке на печать")
        except Exception as e:
            logger.error(f"Ошибка при отправке на печать: {e}")
            raise PrinterError(f"Ошибка при отправке на печать: {e}")
    
    async def get_printer_status(self) -> dict:
        """Получение статуса принтера"""
        if not self.printer_name:
            return {
                "status": "error",
                "name": "Не указан",
                "message": "Имя принтера не указано в конфигурации"
            }
        
        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    lambda: subprocess.run(
                        ['/usr/bin/lpstat', '-p', self.printer_name, '-l'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                )
            
            if result.returncode == 0:
                status_text = result.stdout
                is_enabled = 'enabled' in status_text.lower()
                is_idle = 'idle' in status_text.lower()
                is_disabled = 'disabled' in status_text.lower()
                is_offline = 'offline' in status_text.lower()
                
                # Определяем статус
                if is_disabled:
                    status = "error"
                    message = "Принтер отключен"
                elif is_offline:
                    status = "error"
                    message = "Принтер оффлайн"
                elif is_enabled and is_idle:
                    status = "ready"
                    message = "Принтер готов к работе"
                else:
                    status = "busy"
                    message = "Принтер занят (есть задания в очереди)"
                
                return {
                    "status": status,
                    "enabled": is_enabled,
                    "idle": is_idle,
                    "name": self.printer_name,
                    "message": message
                }
            else:
                error_msg = result.stderr.strip() if result.stderr else "Неизвестная ошибка"
                return {
                    "status": "error",
                    "name": self.printer_name,
                    "message": f"Принтер недоступен: {error_msg}"
                }
                
        except subprocess.TimeoutExpired:
            logger.error(f"Таймаут при проверке статуса принтера {self.printer_name}")
            return {
                "status": "error",
                "name": self.printer_name,
                "message": "Таймаут при проверке статуса принтера"
            }
        except Exception as e:
            logger.error(f"Ошибка получения статуса принтера: {e}")
            return {
                "status": "error",
                "name": self.printer_name,
                "message": f"Ошибка проверки статуса: {str(e)}"
            }

# Глобальный экземпляр принтера
printer = Printer()

