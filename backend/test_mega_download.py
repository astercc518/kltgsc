from mega import Mega
import os

m = Mega().login()
url = "https://mega.nz/file/uK5yGBRa#tIdc7jbPnispMH3sKL87eWHCNYWTy45ftHKAsQVBUSE"
download_dir = "test_download_dir"
os.makedirs(download_dir, exist_ok=True)

print(f"Downloading {url} to {download_dir}...")
try:
    filename = m.download_url(url, download_dir)
    print(f"Returned filename: {filename}")
    
    if os.path.exists(filename):
        size = os.path.getsize(filename)
        print(f"File exists. Size: {size} bytes")
        if size < 100:
             print("File content:")
             with open(filename, 'rb') as f:
                 print(f.read())
    else:
        print("File does not exist at returned path")

except Exception as e:
    print(f"Error: {e}")
