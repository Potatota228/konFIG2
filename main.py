import csv
import sys
import urllib.request
import gzip
from io import BytesIO
from handle_config import *
from in_git import *

def main():
    config_file = 'config_1.csv'
    # config_file = 'config_2.csv'
    # config_file = 'config_3.csv'
    # config_file = 'config_4.csv'
    
    config = read_config(config_file)
    validate_config(config)
    print_config(config)

    package_name = config['package_name']
    package_version = config.get('package_version')  # Может быть None
    repository_url = config['repository_url']
    
    print(f" Поиск зависимостей для пакета '{package_name}'")
    if package_version:
        print(f"Требуемая версия: {package_version}\n")
    else:
        print("Версия не указана, будет использована любая доступная\n")

    if repository_url.endswith('.git') or 'github.com' in repository_url or 'gitlab.com' in repository_url:
        pkg = in_git(repository_url, package_name, package_version)
    elif repository_url.startswith('file://') or os.path.exists(repository_url):
        return 'local'
    elif repository_url.startswith('http://') or repository_url.startswith('https://'):
        return 'http'


    if pkg != None:
        print(pkg.get("name") + "-" + pkg.get("version"))
        if pkg.get("depends") != None :
            print("dependencies:"  + pkg.get("depends"))
            
    


if __name__ == '__main__':
    main()