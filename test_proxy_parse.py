
def parse_proxy_line(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return None, "Empty or comment"
    
    parts = line.split(':')
    
    ip = None
    port = None
    username = None
    password = None
    
    # 尝试解析 user:pass
    if len(parts) >= 4:
        # 假设最后两部分是 user:pass
        # 倒数第三部分是 port
        try:
            potential_port = int(parts[-3])
            # 如果成功解析为整数，说明这确实是端口
            port = potential_port
            username = parts[-2]
            password = parts[-1]
            # 前面所有部分组合为 IP
            ip = ":".join(parts[:-3])
        except ValueError:
            # 如果倒数第三部分不是整数，可能没有 user:pass，或者是更复杂的 IPv6
            pass
    
    if ip is None:
        # 如果上面没有解析成功，尝试只解析 port
        try:
            potential_port = int(parts[-1])
            port = potential_port
            ip = ":".join(parts[:-1])
        except ValueError:
            # 如果最后一部分不是整数，格式错误
            return None, "Invalid format (cannot parse port)"
    
    # 去除 IP 可能存在的 [] 包裹（针对 IPv6）
    ip = ip.strip('[]')
    
    if not ip or not port:
        return None, "Invalid format"
        
    return (ip, port, username, password), None

# 测试用例
test_lines = [
    "2a00:1838:20:2::1234:8000:user:pass", # Proxy6 标准格式
    "2a00:1838:20:2:1234:8000:user:pass",  # 少一个冒号
    "2a00:1838:20:2::1234:8000",           # 无密码
    "1.2.3.4:8080:user:pass",              # IPv4
    "2a00:1838:20:2::1234:8000:user:pass", # 重复
]

print("Testing parse logic...")
for line in test_lines:
    result, error = parse_proxy_line(line)
    if error:
        print(f"FAILED: {line} -> {error}")
    else:
        print(f"SUCCESS: {line} -> {result}")
