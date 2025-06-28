#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы сканера
Для диагностики проблем с HP Color LaserJet Pro MFP M177fw
"""

import sys
import logging
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import sane
from scanner import HPScanner, ScannerError

# Настройка логирования для тестов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_sane_initialization():
    """Тест инициализации SANE"""
    print("🔍 Тестирование SANE...")
    
    try:
        sane.init()
        print("✅ SANE успешно инициализирован")
        
        devices = sane.get_devices()
        print(f"📱 Найдено устройств: {len(devices)}")
        
        for i, device in enumerate(devices):
            print(f"  {i+1}. {device[0]} - {device[1]} ({device[2]})")
        
        if not devices:
            print("❌ Устройства сканирования не найдены")
            return False
        
        sane.exit()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка SANE: {e}")
        return False

async def test_hp_scanner():
    """Тест HP сканера"""
    print("\n🖨️ Тестирование HP сканера...")
    
    try:
        scanner = HPScanner()
        await scanner.initialize()
        print("✅ HP сканер успешно инициализирован")
        
        # Получение статуса
        status = await scanner.get_scanner_status()
        print(f"📊 Статус сканера: {status}")
        
        scanner.cleanup()
        return True
        
    except ScannerError as e:
        print(f"❌ Ошибка HP сканера: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

async def test_scan_operation():
    """Тест операции сканирования"""
    print("\n📄 Тестирование операции сканирования...")
    print("⚠️  Убедитесь, что в сканере есть документ!")
    
    input("Нажмите Enter когда будете готовы продолжить...")
    
    try:
        scanner = HPScanner()
        await scanner.initialize()
        
        print("🔄 Начинаю сканирование...")
        scan_file = await scanner.scan_document()
        
        if scan_file and scan_file.exists():
            file_size = scan_file.stat().st_size / 1024  # KB
            print(f"✅ Документ отсканирован: {scan_file}")
            print(f"📁 Размер файла: {file_size:.1f} KB")
            
            # Проверка, что файл действительно содержит изображение
            try:
                from PIL import Image
                img = Image.open(scan_file)
                width, height = img.size
                print(f"🖼️  Разрешение: {width}x{height}")
                img.close()
            except Exception as e:
                print(f"⚠️  Не удалось проанализировать изображение: {e}")
            
            return True
        else:
            print("❌ Файл сканирования не создан")
            return False
            
    except ScannerError as e:
        print(f"❌ Ошибка сканирования: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False
    finally:
        try:
            scanner.cleanup()
        except:
            pass

def check_system_dependencies():
    """Проверка системных зависимостей"""
    print("🔧 Проверка системных зависимостей...")
    
    dependencies = {
        'sane': 'python-sane',
        'PIL': 'Pillow',
        'telegram': 'python-telegram-bot'
    }
    
    missing = []
    
    for module, package in dependencies.items():
        try:
            __import__(module)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - не найден")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Установите недостающие пакеты:")
        print(f"pip install {' '.join(missing)}")
        return False
    
    return True

def check_scanner_permissions():
    """Проверка прав доступа к сканеру"""
    print("\n🔐 Проверка прав доступа...")
    
    import os
    import grp
    
    try:
        # Проверка групп пользователя
        groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]
        print(f"👤 Текущий пользователь: {os.getenv('USER')}")
        print(f"👥 Группы: {', '.join(groups)}")
        
        required_groups = ['scanner', 'lp']
        missing_groups = [g for g in required_groups if g not in groups]
        
        if missing_groups:
            print(f"⚠️  Отсутствующие группы: {', '.join(missing_groups)}")
            print("Выполните: sudo usermod -a -G scanner,lp $USER")
            print("Затем перелогиньтесь или выполните: newgrp scanner")
            return False
        else:
            print("✅ Права доступа в порядке")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка проверки прав: {e}")
        return False

async def main():
    """Главная функция тестирования"""
    print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ СКАНИРОВАНИЯ")
    print("=" * 50)
    
    tests = [
        ("Системные зависимости", check_system_dependencies),
        ("Права доступа", check_scanner_permissions),
        ("Инициализация SANE", test_sane_initialization),
        ("HP сканер", test_hp_scanner),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}...")
        print("-" * 30)
        
        if asyncio.iscoroutinefunction(test_func):
            result = await test_func()
        else:
            result = test_func()
        
        results.append((test_name, result))
    
    # Дополнительный тест сканирования (опционально)
    print(f"\n📋 Тест сканирования...")
    print("-" * 30)
    
    if all(result for _, result in results):
        while True:
            choice = input("Провести тест сканирования? (y/n): ").lower()
            if choice == 'y':
                scan_result = await test_scan_operation()
                results.append(("Сканирование", scan_result))
                break
            elif choice == 'n':
                break
    
    # Сводка результатов
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print("=" * 50)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name:<25} {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система готова к работе.")
    else:
        print("⚠️  ЕСТЬ ПРОБЛЕМЫ. Исправьте ошибки перед запуском бота.")
    
    print("=" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1) 