from mega import Mega
import os

m = Mega().login()
url = "https://mega.nz/file/uK5yGBRa#tIdc7jbPnispMH3sKL87eWHCNYWTy45ftHKAsQVBUSE"
download_dir = "test_download_dir"
os.makedirs(download_dir, exist_ok=True)

print(f"Downloading to {download_dir}...")
filename = m.download_url(url, download_dir)
print(f"Returned filename: {filename}")
print(f"Is absolute: {os.path.isabs(filename)}")
print(f"File exists at returned path: {os.path.exists(filename)}")
print(f"File exists at joined path: {os.path.exists(os.path.join(download_dir, filename))}")
