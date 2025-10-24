import csv
import sys
import urllib.request
import gzip
from io import BytesIO

def main():
    config_file = 'config_1.csv'
    # config_file = 'config_2.csv'
    # config_file = 'config_3.csv'
    # config_file = 'config_4.csv'
    

    config = read_config(config_file)
    validate_config(config)
    print_config(config)
    
    get_dependencies(config)

def read_config(filename):
    config = {}
    
    try:
        with open(filename, 'r', encoding='utf-8') as f: #r значит для чтения
            reader = csv.reader(f)
            header = next(reader)
            
            if len(header) != 2 or header[0] != 'param' or header[1] != 'value':
                raise ValueError("Некорректный формат CSV. Ожидается 'param,value'")
            
            for row in reader:
                if len(row) != 2:
                    raise ValueError(f"Некорректная строка в CSV: {row}")
                config[row[0]] = row[1]
                
    except FileNotFoundError: #Ловим исключения
        print(f"ОШИБКА: Файл '{filename}' не найден!")
        sys.exit(1)
    except ValueError as e:
        print(f"ОШИБКА: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ОШИБКА при чтении файла: {e}")
        sys.exit(1)
    
    return config

#Проверяем не написаны ли какие-нибудь глупости
def validate_config(config):
    required_params = ['package_name', 'repository_url', 'repo_mode', 'package_version']
    #repo_mode - режим работы с репозиторием. prod Для реальных и test для хихихаха
    
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


def fetch_apkindex(repository_url):
    apkindex_url = f"{repository_url}/x86_64/APKINDEX.tar.gz"
    
    print(f"Загружаем APKINDEX из: {apkindex_url}")
    
    try:
        with urllib.request.urlopen(apkindex_url) as response:
            compressed_data = response.read()
        
        #Разархивируем
        with gzip.GzipFile(fileobj=BytesIO(compressed_data)) as gz:
            content = gz.read().decode('utf-8', errors='ignore')
            return content
            
    except Exception as e:
        print(f"ОШИБКА при загрузке APKINDEX: {e}")
        return None


def parse_apkindex(content, package_name, package_version=None): #В итоге получится словарь
    packages = content.split('\n\n')
    found_packages = []
    
    for package_block in packages:
        lines = package_block.strip().split('\n')
        pkg_info = {}
        
        """ P:  имя пакета (Package)
            V:  версия (Version)
            D:  зависимости (Dependencies)"""
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
    package_version = config.get('package_version')  # Может быть None
    repository_url = config['repository_url']
    
    print(f"=== Поиск зависимостей для пакета '{package_name}' ===")
    if package_version:
        print(f"Требуемая версия: {package_version}\n")
    else:
        print("Версия не указана, будет использована любая доступная\n")
    
    apkindex_content = fetch_apkindex(repository_url)
    
    if not apkindex_content:
        print("Не удалось загрузить APKINDEX")
        return
    
    pkg_info = parse_apkindex(apkindex_content, package_name, package_version)
    
    if not pkg_info:
        print(f"Пакет '{package_name}' не найден в репозитории")
        return
    
    version = pkg_info.get('version', 'unknown')
    depends = pkg_info.get('depends', '')
    
    print(f"\n{package_name}-{version} depends on:")
    
    if depends:
        deps_list = depends.split()
        for dep in deps_list:
            clean_dep = dep.split('>=')[0].split('=')[0].split('<')[0]
            print(f"  - {clean_dep}")
    else:
        print("  (нет зависимостей)")



if __name__ == '__main__':
    main()