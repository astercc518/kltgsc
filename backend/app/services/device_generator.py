import random

class DeviceGenerator:
    """
    生成随机设备指纹信息
    模拟真实的 Android 设备参数
    """
    
    # 扩展的 Android 设备型号列表
    MODELS = [
        # Samsung
        "Samsung Galaxy S24 Ultra", "Samsung Galaxy S24+", "Samsung Galaxy S24",
        "Samsung Galaxy S23 Ultra", "Samsung Galaxy S23", "Samsung Galaxy S22 Ultra",
        "Samsung Galaxy A54", "Samsung Galaxy A34", "Samsung Galaxy Z Fold5",
        "Samsung Galaxy Z Flip5",
        
        # Google
        "Google Pixel 8 Pro", "Google Pixel 8", "Google Pixel 7a",
        "Google Pixel 7 Pro", "Google Pixel 6a", "Google Pixel 6 Pro",
        
        # Xiaomi / Redmi / POCO
        "Xiaomi 14 Ultra", "Xiaomi 14", "Xiaomi 13 Pro", "Xiaomi 13T Pro",
        "Xiaomi Redmi Note 13 Pro+", "Xiaomi Redmi Note 12", 
        "Xiaomi POCO F5 Pro", "Xiaomi POCO X6 Pro",
        
        # OnePlus
        "OnePlus 12", "OnePlus 11", "OnePlus Nord 3", "OnePlus Open",
        
        # Oppo / Vivo
        "Oppo Find X7 Ultra", "Oppo Find X6 Pro", "Oppo Reno11 Pro",
        "Vivo X100 Pro", "Vivo X90 Pro", "Vivo V29",
        
        # Other
        "Sony Xperia 1 V", "Motorola Edge 40 Pro", "Nothing Phone (2)",
        "Asus Zenfone 10", "Honor Magic6 Pro"
    ]
    
    # Android 系统版本
    SYSTEM_VERSIONS = [
        "Android 14", "Android 13", "Android 12", "Android 11"
    ]
    
    # Telegram 应用版本 (更新至较新版本)
    APP_VERSIONS = [
        "10.9.1", "10.8.1", "10.7.3", 
        "10.6.1", "10.5.0", "10.4.3", 
        "10.3.2", "10.2.9"
    ]
    
    @classmethod
    def generate(cls):
        """生成一套随机的设备参数"""
        return {
            "device_model": random.choice(cls.MODELS),
            "system_version": random.choice(cls.SYSTEM_VERSIONS),
            "app_version": random.choice(cls.APP_VERSIONS)
        }
