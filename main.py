import csv
import sys
import urllib.request
import gzip
import tarfile
import os
import subprocess
import tempfile
import ssl
from io import BytesIO
from pathlib import Path

# Для macOS: обход проверки SSL
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

def main():
    # config_file = 'config_1.csv'
    config_file = 'config_2.csv'
    config = read_config(config_file)
    validate_config(config)
    print_config(config)
    
    get_dependencies(config)

def read_config(filename):
    config = {}
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            if len(header) != 2 or header[0] != 'param' or header[1] != 'value':
                raise ValueError("Некорректный формат CSV. Ожидается 'param,value'")
            
            for row in reader:
                if len(row) != 2:
                    raise ValueError(f"Некорректная строка в CSV: {row}")
                config[row[0]] = row[1]
                
    except FileNotFoundError:
        print(f"ОШИБКА: Файл '{filename}' не найден!")
        sys.exit(1)
    except ValueError as e:
        print(f"ОШИБКА: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ОШИБКА при чтении файла: {e}")
        sys.exit(1)
    
    return config

def validate_config(config):
    required_params = ['package_name', 'repository_url', 'repo_mode', 'package_version']
    
    for param in required_params:
        if param not in config:
            print(f"ОШИБКА: Отсутствует обязательный параметр '{param}'")
            sys.exit(1)
    
    if config['repo_mode'] not in ['test', 'prod']:
        print(f"ОШИБКА: Неподдерживаемое значение repo_mode='{config['repo_mode']}'. Допустимые значения: 'test', 'prod'")
        sys.exit(1)
    
    if 'ascii_output' in config:
        if config['ascii_output'].lower() not in ['true', 'false']:
            print(f"ОШИБКА: Некорректное значение ascii_output='{config['ascii_output']}'. Допустимые значения: 'true', 'false'")
            sys.exit(1)

def print_config(config):
    print("Конфигурация")
    for param, value in config.items():
        print(f"{param} = {value}")
    print()

def detect_repo_type(repository_url):
    """Определяет тип репозитория"""
    if repository_url.endswith('.git') or 'github.com' in repository_url or 'gitlab.com' in repository_url:
        return 'git'
    elif repository_url.startswith('file://') or os.path.exists(repository_url):
        return 'local'
    elif repository_url.startswith('http://') or repository_url.startswith('https://'):
        return 'http'
    else:
        return 'unknown'

def clone_git_repo(repo_url, temp_dir):
    """Клонирует git-репозиторий во временную директорию"""
    print(f"Клонирование git-репозитория: {repo_url}")
    try:
        subprocess.run(['git', 'clone', '--depth', '1', repo_url, temp_dir], 
                      check=True, capture_output=True, text=True)
        return temp_dir
    except subprocess.CalledProcessError as e:
        print(f"ОШИБКА при клонировании репозитория: {e.stderr}")
        return None
    except FileNotFoundError:
        print("ОШИБКА: Git не установлен в системе")
        return None

def find_apkindex_in_dir(directory):
    """Ищет APKINDEX файлы в директории"""
    apkindex_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file == 'APKINDEX' or file == 'APKINDEX.tar.gz':
                apkindex_files.append(os.path.join(root, file))
    return apkindex_files

def find_apk_files_in_dir(directory):
    """Ищет .apk файлы в директории"""
    apk_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.apk'):
                apk_files.append(os.path.join(root, file))
    return apk_files

def extract_apk_metadata(apk_path):
    """Извлекает метаданные из .apk файла"""
    print(f"Анализ APK-файла: {apk_path}")
    try:
        with tarfile.open(apk_path, 'r:gz') as tar:
            # Ищем .PKGINFO файл
            for member in tar.getmembers():
                if member.name == '.PKGINFO':
                    content = tar.extractfile(member).read().decode('utf-8', errors='ignore')
                    return parse_pkginfo(content)
        return None
    except Exception as e:
        print(f"ОШИБКА при чтении APK: {e}")
        return None

def parse_pkginfo(content):
    """Парсит содержимое .PKGINFO файла"""
    pkg_info = {}
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('pkgname = '):
            pkg_info['name'] = line[10:]
        elif line.startswith('pkgver = '):
            pkg_info['version'] = line[9:]
        elif line.startswith('depend = '):
            if 'depends' not in pkg_info:
                pkg_info['depends'] = []
            pkg_info['depends'].append(line[9:])
    
    # Преобразуем список зависимостей в строку
    if 'depends' in pkg_info:
        pkg_info['depends'] = ' '.join(pkg_info['depends'])
    
    return pkg_info

def fetch_apkindex(repository_url):
    """Загружает APKINDEX из HTTP-репозитория Alpine"""
    # Пробуем разные варианты путей
    possible_paths = [
        f"{repository_url}/x86_64/APKINDEX.tar.gz",
        f"{repository_url}/APKINDEX.tar.gz",
        f"{repository_url}/APKINDEX",
    ]
    
    for apkindex_url in possible_paths:
        print(f"Пробуем загрузить: {apkindex_url}")
        try:
            with urllib.request.urlopen(apkindex_url, context=ssl_context) as response:
                data = response.read()
            
            # Если это .tar.gz, разархивируем
            if apkindex_url.endswith('.tar.gz'):
                with gzip.GzipFile(fileobj=BytesIO(data)) as gz:
                    content = gz.read().decode('utf-8', errors='ignore')
            else:
                content = data.decode('utf-8', errors='ignore')
            
            print(f"Успешно загружено из: {apkindex_url}\n")
            return content
            
        except Exception as e:
            print(f"  Не удалось: {e}")
            continue
    
    print("ОШИБКА: Не удалось найти APKINDEX ни по одному из путей")
    return None

def parse_apkindex(content, package_name, package_version=None):
    """Парсит содержимое APKINDEX"""
    packages = content.split('\n\n')
    found_packages = []
    
    for package_block in packages:
        lines = package_block.strip().split('\n')
        pkg_info = {}
        
        for line in lines:
            if line.startswith('P:'):
                pkg_info['name'] = line[2:].strip()
            elif line.startswith('V:'):
                pkg_info['version'] = line[2:].strip()
            elif line.startswith('D:'):
                pkg_info['depends'] = line[2:].strip()
        
        if pkg_info.get('name') == package_name:
            found_packages.append(pkg_info)
    
    if package_version and found_packages:
        for pkg in found_packages:
            if pkg.get('version', '').startswith(package_version):
                return pkg
        print(f"ВНИМАНИЕ: Версия {package_version} не найдена, доступные версии:")
        for pkg in found_packages:
            print(f"  - {pkg.get('version')}")
        return None
    
    return found_packages[0] if found_packages else None

def get_dependencies(config):
    package_name = config['package_name']
    package_version = config.get('package_version')
    repository_url = config['repository_url']
    
    print(f"Поиск зависимостей для пакета '{package_name}'")
    if package_version:
        print(f"Требуемая версия: {package_version}\n")
    else:
        print("Версия не указана, будет использована любая доступная\n")
    
    repo_type = detect_repo_type(repository_url)
    print(f"Тип репозитория: {repo_type}\n")
    
    pkg_info = None
    temp_dir = None
    
    try:
        if repo_type == 'git':
            # Клонируем git-репозиторий
            temp_dir = tempfile.mkdtemp()
            if not clone_git_repo(repository_url, temp_dir):
                return
            
            # Ищем APKINDEX
            apkindex_files = find_apkindex_in_dir(temp_dir)
            if apkindex_files:
                print(f"Найден APKINDEX: {apkindex_files[0]}")
                with open(apkindex_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                pkg_info = parse_apkindex(content, package_name, package_version)
            else:
                # Если нет APKINDEX, ищем .apk файлы
                print("APKINDEX не найден, ищем .apk файлы...")
                apk_files = find_apk_files_in_dir(temp_dir)
                for apk_file in apk_files:
                    info = extract_apk_metadata(apk_file)
                    if info and info.get('name') == package_name:
                        if not package_version or info.get('version', '').startswith(package_version):
                            pkg_info = info
                            break
        
        elif repo_type == 'local':
            # Работаем с локальной директорией
            local_path = repository_url.replace('file://', '')
            
            apkindex_files = find_apkindex_in_dir(local_path)
            if apkindex_files:
                with open(apkindex_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                pkg_info = parse_apkindex(content, package_name, package_version)
            else:
                apk_files = find_apk_files_in_dir(local_path)
                for apk_file in apk_files:
                    info = extract_apk_metadata(apk_file)
                    if info and info.get('name') == package_name:
                        if not package_version or info.get('version', '').startswith(package_version):
                            pkg_info = info
                            break
        
        elif repo_type == 'http':
            # Работаем с HTTP-репозиторием
            apkindex_content = fetch_apkindex(repository_url)
            if apkindex_content:
                pkg_info = parse_apkindex(apkindex_content, package_name, package_version)
        
        else:
            print(f"ОШИБКА: Неподдерживаемый тип репозитория")
            return
        
        if not pkg_info:
            print(f"Пакет '{package_name}' не найден в репозитории")
            return
        
        version = pkg_info.get('version', 'unknown')
        depends = pkg_info.get('depends', '')
        
        print(f"\n{package_name}-{version} зависит от:")
        
        if depends:
            deps_list = depends.split() if isinstance(depends, str) else depends
            for dep in deps_list:
                clean_dep = dep.split('>=')[0].split('=')[0].split('<')[0]
                print(f"  - {clean_dep}")
        else:
            print("  (нет зависимостей)")
    
    finally:
        # Удаляем временную директорию
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)

if __name__ == '__main__':
    main()