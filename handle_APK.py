def find_apk_files_in_dir(directory, package_name, package_version):
    """Ищет .apk файлы в директории"""
    apk_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.apk'):
                apk_files.append(os.path.join(root, file))
    for apk_file in apk_files:
            info = extract_apk_metadata(apk_file)
            if info and info.get('name') == package_name:
                if not package_version or info.get('version', '').startswith(package_version):
                    return info
                    

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
