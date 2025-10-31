import csv
import sys
import urllib.request
import tarfile
import gzip
import ssl
import os
import subprocess
import tempfile
import shutil
from io import BytesIO

""" `csv` — чтение и парсинг конфигурации;
    `sys` — завершение программы при ошибках;
    `urllib.request` — загрузка данных по HTTP;
    `tarfile`, gzip, BytesIO — распаковка архивов;
    `os`, `subprocess`, `tempfile`, `shutil` — работа с файловой системой и git;
    `ssl` — корректная работа HTTPS на macOS.
"""

# Для macOS: чтобы работал SSL
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def main():
    # Читаем конфиг(и)
    # config_file = 'config_1.csv'
    config_file = 'config_2.csv'


    config = read_config(config_file)
    
    # Проверяем что всё ок
    validate_config(config)
    
    # Показываем что прочитали
    print_config(config)
    
    # Ищем зависимости
    get_dependencies(config)


def read_config(filename):
    config = {}
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            if header[0] != 'param' or header[1] != 'value':
                print("ОШИБКА: Неправильный заголовок в CSV")
                sys.exit(1)
    
            for row in reader:
                config[row[0]] = row[1]    
    except FileNotFoundError:
        print(f"ОШИБКА: Файл '{filename}' не найден!")
        sys.exit(1)
    except Exception as e:
        print(f"ОШИБКА при чтении файла: {e}")
        sys.exit(1)
    
    return config


def validate_config(config):
    required = ['package_name', 'repository_url', 'repo_mode', 'package_version']
    
    for param in required:
        if param not in config:
            print(f"ОШИБКА: Нет параметра '{param}' в конфиге")
            sys.exit(1)
    
    if config['repo_mode'] not in ['test', 'prod']:
        print(f"ОШИБКА: repo_mode должен быть 'test' или 'prod'")
        sys.exit(1)
    
    if 'ascii_output' in config:
        if config['ascii_output'].lower() not in ['true', 'false']:
            print(f"ОШИБКА: ascii_output должен быть 'true' или 'false'")
            sys.exit(1)


def print_config(config):
    print("=== Конфигурация ===")
    for param, value in config.items():
        print(f"{param} = {value}")
    print()


def check_repo_type(url):
    
    # git
    if url.endswith('.git') or 'github.com' in url or 'gitlab.com' in url:
        return 'git'
    
    # http
    elif url.startswith('http://') or url.startswith('https://'):
        return 'http'
    
    else: return 'unknown'


# HTTP

def download_apkindex_http(repository_url):
    
    if repository_url.endswith('/'):
        repository_url = repository_url[:-1]
    
    # Разные пути туда сюда
    urls_to_try = [
        f"{repository_url}/x86_64/APKINDEX.tar.gz",
        f"{repository_url}/APKINDEX.tar.gz",
        f"{repository_url}/APKINDEX",
    ]
    
    for url in urls_to_try:
        print("Пытаемся скачать APKINDEX: {url}")
        
        try:
            response = urllib.request.urlopen(url, context=ssl_context)
            data = response.read()
            
            # Если это .tar.gz - распаковываем
            if url.endswith('.tar.gz'):
                with gzip.GzipFile(fileobj=BytesIO(data)) as gz:
                    text = gz.read().decode('utf-8', errors='ignore')
            else:
                text = data.decode('utf-8', errors='ignore')
            
            print("Успешно!\n")
            return text
            
        except Exception as e:
            print(f"Не успешно: {e}")
    
    print("ОШИБКА: Не смогли скачать APKINDEX")
    return None


# GIT

def clone_git_repo(git_url):
    
    print(f"Клонируем git репозиторий: {git_url}")
    
    # Создаём временную папку
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Запускаем git clone
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', git_url, temp_dir],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"ОШИБКА git: {result.stderr}")
            return None
        
        print(f"Успешно склонировано в {temp_dir}\n")
        return temp_dir
        
    except FileNotFoundError:
        print("ОШИБКА: Git не установлен")
        return None
    except Exception as e:
        print(f"ОШИБКА: {e}")
        return None


def find_files_in_directory(directory, filename):
    found_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file == filename or file == filename + '.tar.gz':
                full_path = os.path.join(root, file)
                found_files.append(full_path)
    
    return found_files


def read_apkindex_from_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"ОШИБКА чтения файла: {e}")
        return None


def find_apk_files(directory):
    apk_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.apk'):
                full_path = os.path.join(root, file)
                apk_files.append(full_path)
    
    return apk_files


def read_apk_file(apk_path):  
    print(f"Читаем APK файл: {apk_path}")
    
    try:
        # APK файл - это tar.gz архив
        with tarfile.open(apk_path, 'r:gz') as tar:
            
            # Ищем файл .PKGINFO внутри
            for member in tar.getmembers():
                if member.name == '.PKGINFO':
                    # Читаем его
                    file_content = tar.extractfile(member)
                    text = file_content.read().decode('utf-8', errors='ignore')
                    
                    # Парсим .PKGINFO
                    return parse_pkginfo(text)
        
        return None
        
    except Exception as e:
        print(f"ОШИБКА: {e}")
        return None


def parse_pkginfo(text):
    
    pkg_info = {
        'name': None,
        'version': None,
        'depends': ''
    }
    
    dependencies = []
    for line in text.split('\n'):
        line = line.strip()
        
        if line.startswith('pkgname = '):
            pkg_info['name'] = line[10:]
        
        elif line.startswith('pkgver = '):
            pkg_info['version'] = line[9:]
        
        elif line.startswith('depend = '):
            dep = line[9:]
            dependencies.append(dep)
    
    # В строку всё
    if dependencies:
        pkg_info['depends'] = ' '.join(dependencies)
    
    return pkg_info


# ПАРСИНГ APKINDEX

def find_package_in_apkindex(apkindex_text, package_name, package_version):

    # Разделяем на блоки (каждый пакет - отдельный блок)
    blocks = apkindex_text.split('\n\n')
    
    found_packages = []
    
    for block in blocks:
        lines = block.strip().split('\n')
        
        pkg_name = None
        pkg_version = None
        pkg_depends = None
        
        for line in lines:
            if line.startswith('P:'):
                pkg_name = line[2:].strip()
            elif line.startswith('V:'):
                pkg_version = line[2:].strip()
            elif line.startswith('D:'):
                pkg_depends = line[2:].strip()
        
        # Если это нужный пакет
        if pkg_name == package_name:
            pkg_info = {
                'name': pkg_name,
                'version': pkg_version,
                'depends': pkg_depends
            }
            found_packages.append(pkg_info)
    
    if len(found_packages) == 0:
        return None
    
    # Если версия не указана - берём первый
    if not package_version or package_version == '':
        return found_packages[0]
    
    # Если версия указана - ищем подходящую
    for pkg in found_packages:
        if pkg['version'] and pkg['version'].startswith(package_version):
            return pkg
    
    # Версия не найдена
    print(f"Версия {package_version} не найдена. Доступные:")
    for pkg in found_packages:
        print(f"  - {pkg['version']}")
    
    return None


#  ВЫВОД РЕЗУЛЬТАТА 

def print_dependencies(package_info):
    
    name = package_info['name']
    version = package_info['version'] if package_info['version'] else 'unknown'
    depends = package_info['depends']
    
    print(f"\n=== {name}-{version} ===")
    print("Зависимости:")
    
    if not depends or depends == '':
        print("  (нет зависимостей)")
        return
    
    # Разделяем зависимости
    deps_list = depends.split()
    
    for dep in deps_list:
        # Убираем версии
        clean_dep = dep.split('>=')[0].split('=')[0].split('<')[0]
        print(f"  - {clean_dep}")


#  ГЛАВНАЯ ФУНКЦИЯ 

def get_dependencies(config):
    
    package_name = config['package_name']
    package_version = config.get('package_version', '')
    repository_url = config['repository_url']
    
    print(f"Ищем: {package_name}")
    if package_version:
        print(f"Версия: {package_version}")
    print(f"Репозиторий: {repository_url}\n")
    
    # Определяем тип репозитория
    repo_type = check_repo_type(repository_url)
    print(f"Тип репозитория: {repo_type}\n")
    
    package_info = None
    temp_dir = None
    
    try:
        # HTTP
        if repo_type == 'http':
            print("Работаем с HTTP репозиторием\n")
            
            apkindex_text = download_apkindex_http(repository_url)
            if not apkindex_text:
                return
            
            package_info = find_package_in_apkindex(apkindex_text, package_name, package_version)
        
        # GIT
        elif repo_type == 'git':
            print("Работаем с Git репозиторием\n")
            
            # Клонируем
            temp_dir = clone_git_repo(repository_url)
            if not temp_dir:
                return
            
            # Ищем APKINDEX
            apkindex_files = find_files_in_directory(temp_dir, 'APKINDEX')
            
            if apkindex_files:
                print(f"Найден APKINDEX: {apkindex_files[0]}")
                apkindex_text = read_apkindex_from_file(apkindex_files[0])
                if apkindex_text:
                    package_info = find_package_in_apkindex(apkindex_text, package_name, package_version)
            
            else:
                # Если нет APKINDEX - ищем .apk файлы
                print("APKINDEX не найден, ищем .apk файлы...")
                apk_files = find_apk_files(temp_dir)
                
                print(f"Найдено {len(apk_files)} .apk файлов")
                
                for apk_file in apk_files:
                    pkg_info = read_apk_file(apk_file)
                    
                    if pkg_info and pkg_info['name'] == package_name:
                        # Проверяем версию если нужно
                        if not package_version or pkg_info['version'].startswith(package_version):
                            package_info = pkg_info
                            break
        
        else:
            print("ОШИБКА: Неизвестный тип репозитория")
            return
        
        # Выводим результат
        if not package_info:
            print(f"\nПакет '{package_name}' не найден")
            return
        
        print_dependencies(package_info)
    
    finally:
        # Удаляем временную папку если работали с гитом
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    main()