import os
import sys
import zipfile
import urllib.request
import json

def download_comics_downloader():
    tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools')
    os.makedirs(tools_dir, exist_ok=True)
    
    # Use direct exe download from latest release
    version = "v0.33.9"
    download_url = f"https://github.com/Girbons/comics-downloader/releases/download/{version}/comics-downloader-win-x86-64.exe"
    exe_path = os.path.join(tools_dir, "comics-downloader.exe")
    
    if os.path.exists(exe_path):
        print(f"[INFO] comics-downloader.exe is already installed at: {exe_path}")
        return True
        
    print(f"Downloading comics-downloader {version} from GitHub...")
    try:
        # User-Agent is sometimes required by GitHub
        req = urllib.request.Request(
            download_url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req) as response, open(exe_path, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
            
        if os.path.exists(exe_path):
            print(f"[SUCCESS] comics-downloader.exe successfully installed to: {exe_path}")
            return True
        else:
            print("[ERROR] comics-downloader.exe was not successfully saved.")
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to download or install comics-downloader: {e}")
        return False

if __name__ == "__main__":
    download_comics_downloader()
