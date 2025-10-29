import tempfile
import sys
from handle_APKINDEX import *
from handle_APK import *
def in_git(repository_url, package_name, package_version):
    temp_dir = tempfile.mkdtemp()
    if not clone_git_repo(repository_url, temp_dir):
        return None
    print ("Ищем APKINDEX файлы...")
    trying = find_apkindex_in_dir(temp_dir, package_name, package_version)
    if trying != None:
        return trying
    else:
        print("Ищем .apk файлы...")
        return find_apk_files_in_dir(temp_dir, package_name, package_version)
            
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