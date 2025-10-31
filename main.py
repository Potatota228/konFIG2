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
from collections import deque
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
    dep_choice_made = ""
    choice = int(input("""Введите номер файла:
                1. config_1
                2. config_2
                3. config_3
                4. config_test
                       """))
    match choice:
        case 1:
            config_file = 'config_1.csv'
        case 2:
            config_file = 'config_2.csv'
        case 3:
            config_file = 'config_3.csv'
        case 4:
            config_file = 'config_test.csv'
            dep_choice = int(input("""Введите номер файла:
                1. test_dep_simple.txt
                2. test_dep_cycle.txt
                3. test_dep_complex.txt
                                   """))
            match dep_choice:
                case 1:
                    dep_choice_made = "test_dep_simple.txt"
                case 2:
                    dep_choice_made = "test_dep_cycle.txt"
                case 3:
                    dep_choice_made = "test_dep_cycle.txt"
        



    config = read_config(config_file, dep_choice_made)
    
    # Проверяем что всё ок
    validate_config(config)
    
    # Показываем что прочитали
    print_config(config)
    
    # Ищем зависимости
    build_dependency_graph(config)


def read_config(filename, dep_choice_made):
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
            if dep_choice_made!= "":
                config["repository_url"] = dep_choice_made
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
    print(" Конфигурация ")
    for param, value in config.items():
        print(f"{param} = {value}")
    print()


def check_repo_type(url, repo_mode):
    #test
    if repo_mode == 'test':
        return 'test'
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
        print(f"Пытаемся скачать APKINDEX: {url}")
        
        try:
            response = urllib.request.urlopen(url, context=ssl_context)
            data = response.read()
            
            # Если это .tar.gz - распаковываем
            if url.endswith('.tar.gz'):
                with gzip.GzipFile(fileobj=BytesIO(data)) as gz:
                    text = gz.read().decode('utf-8', errors='ignore')
            else:
                text = data.decode('utf-8', errors='ignore')
            
            print("Успешно\n")
            return text
            
        except Exception as e:
            print(f"Не успешно: {e}")
    
    print("ОШИБКА: Не смогли скачать APKINDEX")
    return None

#TEST

def read_test_repo(filepath):
    """
    Формат файла:
    A:B C
    B:D
    C:D E
    D:
    E:F
    F:
    """
    
    print(f"Читаем тестовый репозиторий: {filepath}\n")
    
    test_packages = {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                if not line or line.startswith('#'):
                    continue
                
                if ':' not in line:
                    continue
                
                parts = line.split(':')
                package_name = parts[0].strip()
                
                # Зависимости (если есть)
                if len(parts) > 1 and parts[1].strip():
                    depends = parts[1].strip()
                else:
                    depends = ''
                
                test_packages[package_name] = {
                    'name': package_name,
                    'version': '1.0',
                    'depends': depends
                }
        
        print(f"Загружено {len(test_packages)} тестовых пакетов")
        return test_packages
        
    except FileNotFoundError:
        print(f"ОШИБКА: Файл '{filepath}' не найден")
        return None
    except Exception as e:
        print(f"ОШИБКА: {e}")
        return None


def find_package_in_test_repo(test_packages, package_name):
    if package_name in test_packages:
        return test_packages[package_name]
    
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
    
    print(f"\n {name}-{version} ")
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

# РАБОТА С ЗАВИСИМОСТЯМИ

def parse_dependencies(depends_string):
    """Парсит строку зависимостей и возвращает список имён пакетов"""
    
    if not depends_string or depends_string == '':
        return []
    
    deps_list = depends_string.split()
    clean_deps = []
    
    for dep in deps_list:
        # Убираем версии (>=, =, <)
        clean_dep = dep.split('>=')[0].split('=')[0].split('<')[0]
        clean_deps.append(clean_dep)
    
    return clean_deps


def build_graph_bfs(start_package, get_package_func):
    """Строит граф зависимостей используя BFS (Breadth First Search) — “в ширину” (через очередь)
    
    Получает:
        start_package: имя стартового пакета
        get_package_func: функция которая получает инфо о пакете по имени
    
    Выдает:
        graph: словарь {package_name: [list of dependencies]}
        visited: множество всех посещённых пакетов
        cycles: список найденных циклов
    """
    
    print(f"\n Строим граф зависимостей для '{start_package}' \n")
    

    graph = {}
    visited = set()
    in_progress = set()
    cycles = []
    
    # Очередь для BFS: (имя_пакета, путь_до_него)
    queue = deque() #Вот это супер крутая штука, чего только эти ваши питоны не напридумывают
    queue.append((start_package, []))
    
    # BFS
    while len(queue) > 0:
        current_package, path = queue.popleft()
        
        # Если уже обработали - пропускаем
        if current_package in visited:
            continue
        
        # Проверяем цикл
        if current_package in queue :
            cycle_path = path + [current_package]
            cycles.append(cycle_path)
            print(f"ЦИКЛ ОБНАРУЖЕН: {' -> '.join(cycle_path)}")
            continue
        
        # Помечаем что начали обрабатывать
        in_progress.add(current_package)
        
        # Получаем информацию о пакете
        pkg_info = get_package_func(current_package)
        
        if not pkg_info:
            print(f"Пакет '{current_package}' не найден в репозитории")
            graph[current_package] = []
            visited.add(current_package)
            in_progress.remove(current_package)
            continue
        
        # Парсим зависимости
        depends_string = pkg_info.get('depends', '')
        dependencies = parse_dependencies(depends_string)
        
        # Сохраняем в граф
        graph[current_package] = dependencies
        
        if dependencies:
            print(f"{current_package}: {dependencies}")
        else:
            print(f"{current_package}: (нет зависимостей)")
        
        # Добавляем зависимости в очередь
        new_path = path + [current_package]
        for dep in dependencies:
            if dep not in visited:
                queue.append((dep, new_path))
        
        # Помечаем как обработанный
        visited.add(current_package)
        in_progress.remove(current_package)
    
    return graph, visited, cycles


def print_graph(graph, cycles):
    
    print("\n" + "="*50)
    print("ГРАФ ЗАВИСИМОСТЕЙ")
    print("="*50)
    
    for package, deps in graph.items():
        if deps:
            print(f"{package} -> {', '.join(deps)}")
        else:
            print(f"{package} -> (нет зависимостей)")
    
    print("\n" + "="*50)
    print(f"Всего пакетов в графе: {len(graph)}")
    
    if cycles:
        print(f"Найдено циклов: {len(cycles)}")
        print("\nЦиклические зависимости:")
        for i, cycle in enumerate(cycles, 1):
            print(f"  {i}. {' -> '.join(cycle)}")
    else:
        print("Циклических зависимостей не обнаружено ")
    
    print("="*50 + "\n")



#  ГЛАВНАЯ ФУНКЦИЯ 

def build_dependency_graph(config):
    """Главная функция - строит граф зависимостей"""
    
    package_name = config['package_name']
    package_version = config.get('package_version', '')
    repository_url = config['repository_url']
    repo_mode = config['repo_mode']
    
    print(f"Пакет: {package_name}")
    if package_version:
        print(f"Версия: {package_version}")
    print(f"Репозиторий: {repository_url}")
    print(f"Режим: {repo_mode}\n")
    
    # Определяем тип репозитория
    repo_type = check_repo_type(repository_url, repo_mode)
    print(f"Тип репозитория: {repo_type}\n")
    
    temp_dir = None
    test_packages = None
    apkindex_text = None
    
    try:
        #  ТЕСТОВЫЙ РЕЖИМ 
        if repo_type == 'test':
            print(" ТЕСТОВЫЙ РЕЖИМ \n")
            
            test_packages = read_test_repo(repository_url)
            if not test_packages:
                return
            
            def get_package_test(pkg_name):
                return find_package_in_test_repo(test_packages, pkg_name)
            
            graph, visited, cycles = build_graph_bfs(package_name, get_package_test)
            print_graph(graph, cycles)
        
        #  HTTP РЕПОЗИТОРИЙ 
        elif repo_type == 'http':
            print(" HTTP РЕПОЗИТОРИЙ \n")
            
            apkindex_text = download_apkindex_http(repository_url)
            if not apkindex_text:
                return
            
            # Функция для получения пакета из APKINDEX
            def get_package_http(pkg_name):
                return find_package_in_apkindex(apkindex_text, pkg_name, '')
            
            # Строим граф
            graph, visited, cycles = build_graph_bfs(package_name, get_package_http)
            print_graph(graph, cycles)
        
        #  GIT РЕПОЗИТОРИЙ 
        elif repo_type == 'git':
            print(" GIT РЕПОЗИТОРИЙ \n")
            temp_dir = clone_git_repo(repository_url)
            if not temp_dir:
                return
            
            # Ищем APKINDEX
            apkindex_files = find_files_in_directory(temp_dir, 'APKINDEX')
            
            if apkindex_files:
                print(f"Найден APKINDEX: {apkindex_files[0]}\n")
                apkindex_text = read_apkindex_from_file(apkindex_files[0])
                
                if apkindex_text:
                    def get_package_git(pkg_name):
                        return find_package_in_apkindex(apkindex_text, pkg_name, '')
                    
                    graph, visited, cycles = build_graph_bfs(package_name, get_package_git)
                    print_graph(graph, cycles)
            else:
                print("APKINDEX не найден — ищем .apk файлы...\n")
                apk_files = find_apk_files(temp_dir)
                if not apk_files:
                    print(".apk файлы не найдены, нечего анализировать.")
                    return
    
                print(f"Найдено .apk файлов: {len(apk_files)}\n")
                
                # Собираем пакеты
                all_packages = {}
                for apk in apk_files:
                    info = read_apk_file(apk)
                    if info and info['name']:
                        all_packages[info['name']] = info
                
                if not all_packages:
                    print("⚠️ Не удалось извлечь информацию из .apk файлов.")
                    return
                
                print(f" Собрано {len(all_packages)} пакетов из .apk\n")
                
                # Функция получения пакета из собранных данных
                def get_package_from_apk(pkg_name):
                    return all_packages.get(pkg_name, None)
                
                # Строим граф зависимостей
                graph, visited, cycles = build_graph_bfs(package_name, get_package_from_apk)
                print_graph(graph, cycles)
                    
        else:
            print("ОШИБКА: Неизвестный тип репозитория")
            return
                
    finally:
        # Удаляем временную папку если создавали
        if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)

if __name__ == '__main__':
    main()