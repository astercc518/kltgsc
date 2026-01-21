from faker import Faker
import random

import requests
import time

fake = Faker()

class ProfileGenerator:
    @staticmethod
    def generate_name():
        return {
            "first_name": fake.first_name(),
            "last_name": fake.last_name()
        }
    
    @staticmethod
    def generate_about():
        # 生成一些简单的英文简介，或者使用 Faker 的 text
        # 为了更真实，可以混合一些 emoji
        sentences = [
            "Hello world! 🌍",
            "Just a Telegram user.",
            "Crypto enthusiast 🚀",
            "Digital Nomad 💻",
            "Living the life.",
            "Contact me for business.",
            "Available.",
            "Busy building dreams.",
            "Music lover 🎵",
            "Traveler ✈️"
        ]
        return random.choice(sentences)

    @staticmethod
    def generate_username(first_name=None, last_name=None):
        """生成随机用户名"""
        base = ""
        if first_name:
            base += first_name.lower()
        if last_name:
            base += last_name.lower()
        
        if not base:
            base = fake.user_name()
            
        # 移除空格和非字母数字
        import re
        base = re.sub(r'[^a-z0-9]', '', base)
        
        # 添加随机数字后缀以保证唯一性
        suffix = random.randint(100, 99999)
        return f"{base}{suffix}"

    @staticmethod
    def generate_password():
        """生成强密码"""
        return fake.password(length=12, special_chars=True, digits=True, upper_case=True, lower_case=True)

    @staticmethod
    def download_random_avatar(save_path: str) -> bool:
        """
        下载随机头像到指定路径
        尝试多个源
        """
        sources = [
            "https://thispersondoesnotexist.com/", # AI 生成人脸
            "https://loremflickr.com/640/640/face", # 随机人脸
            "https://loremflickr.com/640/640/portrait", # 随机肖像
            "https://picsum.photos/640/640" # 随机图片(备选)
        ]
        
        for url in sources:
            try:
                # 添加时间戳避免缓存
                if "?" in url:
                    final_url = f"{url}&t={int(time.time())}"
                else:
                    final_url = f"{url}?t={int(time.time())}"
                    
                response = requests.get(final_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code == 200:
                    with open(save_path, "wb") as f:
                        f.write(response.content)
                    return True
            except Exception as e:
                print(f"Failed to download from {url}: {e}")
                continue
                
        return False
