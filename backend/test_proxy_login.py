import asyncio
from pyrogram import Client
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)

# 代理配置
proxy = {
    "scheme": "socks5",
    "hostname": "103.246.246.29",
    "port": 24512,
    "username": "whs_qmx",
    "password": "58ganji@123"
}

# Session 配置
# 注意：路径需要是容器内的绝对路径
session_file = "/app/sessions/17652473431.session"
api_id = 2040
api_hash = "b18441a1ff607e10a989891a5462e627"

print(f"Testing connection with proxy: {proxy['hostname']}:{proxy['port']}")

client = Client(
    "17652473431",
    api_id=api_id,
    api_hash=api_hash,
    proxy=proxy,
    workdir="/app/sessions"
)

async def main():
    try:
        print("Connecting...")
        await client.connect()
        print("Connected!")
        
        # 检查是否已授权
        try:
            me = await client.get_me()
            print(f"Logged in as: {me.first_name} ({me.id})")
        except Exception as e:
            print(f"GetMe failed: {e}")
            
        await client.disconnect()
    except Exception as e:
        print(f"Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
