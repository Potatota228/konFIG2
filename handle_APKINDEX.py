
def find_apkindex_in_dir(directory, package_name, package_version):
    """Ищет APKINDEX файлы в директории"""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file == 'APKINDEX' or file == 'APKINDEX.tar.gz':
                print("Найден APKINDEX")  
                try:
                    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    return parse_apkindex(content, package_name, package_version)
                except Exception as e:
                    print(f"ОШИБКА при чтении APKINDEX: {e}")
                    return None
                
def fetch_apkindex(placement):
    apkindex_url = f"{placement}/x86_64/APKINDEX.tar.gz"
    
    print(f"Загружаем APKINDEX из: {apkindex_url}")
    
    try:
        with urllib.request.urlopen(apkindex_url) as response:
            compressed_data = response.read()
        
        #Разархивируем
        with gzip.GzipFile(fileobj=BytesIO(compressed_data)) as gz:
            content = gz.read().decode('utf-8', errors='ignore')
            return parse_apkindex(content, package_name, package_version)
            
    except Exception as e:
        print(f"ОШИБКА при чтении APKINDEX: {e}")
        return None


def parse_apkindex(content, package_name, package_version): #В итоге получится словарь
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
    print(f"Пакет '{package_name}' не найден в репозитории")
    return None