from pyrogram import Client
import os

session_file = "/app/sessions/16802203458.session"
api_id = 6
api_hash = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

print(f"Testing session: {session_file}")
print(f"File size: {os.path.getsize(session_file)} bytes")

client = Client(
    "test_session",
    api_id=api_id,
    api_hash=api_hash,
    session_string=None,
    workdir="/app/sessions", 
)

# 我们直接指定 session 文件路径的方式有点 tricky，Pyrogram 根据 name 生成路径
# 如果 name 是 16802203458，它会找 16802203458.session
# 让我们用正确的 name

client_direct = Client(
    "16802203458",
    api_id=api_id,
    api_hash=api_hash,
    workdir="/app/sessions",
)

try:
    print("Connecting...")
    client_direct.start()
    me = client_direct.get_me()
    print(f"Success! User: {me.first_name} ({me.id})")
    client_direct.stop()
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Error: {e}")
