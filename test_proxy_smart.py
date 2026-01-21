
def parse_proxy_smart(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return None, "Empty"
    
    parts = line.split(':')
    
    # 寻找端口的索引
    port_index = -1
    port = None
    
    # 从后往前找，跳过最后两个（假设是 user:pass），但也可能是 port 在最后
    # 策略：从后往前找第一个合法的端口号
    # 但要注意 IPv6 中也可能有数字。
    # 启发式：
    # 1. 如果最后一部分是数字，它很可能是端口（无 auth 模式）
    # 2. 如果倒数第三部分是数字，它很可能是端口（标准 auth 模式）
    # 3. 如果密码包含冒号，端口可能在更前面
    
    # 倒序遍历，限制范围（避免把 IPv6 中间的数字当端口）
    # 通常 auth 不会很长，我们只看最后 5 个部分
    search_limit = min(len(parts), 5)
    found_indices = []
    
    for i in range(len(parts) - 1, len(parts) - 1 - search_limit, -1):
        if i < 0: break
        try:
            val = int(parts[i])
            if 1 <= val <= 65535:
                found_indices.append(i)
        except ValueError:
            continue
            
    if not found_indices:
        return None, "No valid port found"
    
    # found_indices 包含了可能是端口的位置。
    # 我们需要决策哪一个是真正的端口。
    # 规则：
    # 1. 如果最后一个是端口，优先选它（无 Auth 场景），除非我们有证据表明后面是 User/Pass
    # 2. 如果倒数第三个是端口，且后面有两个非空字符串，那可能是标准 Auth
    
    # 让我们尝试一种更贪婪的策略：
    # 认为最靠后的、且后面看起来像 Auth 的是端口。
    # 或者说：端口后面要么是空的，要么是 User:Pass
    
    # Case 1: IP:PORT
    # Case 2: IP:PORT:USER:PASS
    # Case 3: IP:PORT:USER:PASS:WITH:COLONS
    
    # 如果最后一个是端口，且前面部分构成合法 IP（或至少看起来像）
    # 这种策略有一个风险：密码全是数字。例如 pass=1234。
    # IP:PORT:USER:1234
    # 最后一个 1234 是端口吗？不是。
    # 倒数第三个是端口。
    
    # 改进算法：
    # 假设 User:Pass 必定存在。
    # 尝试找到 parts[i] 是端口，使得 parts[i+1:] 可以组成 User:Pass
    # 通常 User:Pass 至少有两部分（除非密码为空）
    
    best_guess = None
    
    for idx in found_indices:
        # idx 是候选端口索引
        suffix_len = len(parts) - 1 - idx
        
        # 如果后面没有东西，那是 IP:PORT 模式
        if suffix_len == 0:
            ip_cand = ":".join(parts[:idx])
            # 简单的 IP 验证：IPv4 有 3 个点，IPv6 有冒号
            if '.' in ip_cand or ':' in ip_cand:
                best_guess = (ip_cand, int(parts[idx]), None, None)
                # 这是一个强候选，但如果原本是 auth 模式且密码是数字，会被误判。
                # 但通常我们优先匹配 Auth 模式。所以继续看前面的候选。
        
        # 如果后面有东西，尝试解析为 User:Pass
        elif suffix_len >= 2:
            # 至少有 User 和 Pass
            user = parts[idx+1]
            password = ":".join(parts[idx+2:]) # 密码可能包含冒号
            ip_cand = ":".join(parts[:idx])
            
            if '.' in ip_cand or ':' in ip_cand:
                # 这是一个 Auth 模式的候选
                # 我们偏向于 Auth 模式，所以一旦找到，直接返回（因为我们是从后往前找的，
                # 但 found_indices 是倒序的，所以第一个找到的是最靠后的数字。
                # 等等，如果密码是数字，found_indices[0] 是密码。
                # 我们应该取索引最小的那个吗？
                # 不，端口应该是在 User/Pass 之前的。
                # 例如 ...:8000:user:1234
                # indices: [-1(1234), -3(8000)]
                # 我们应该选 -3。
                best_guess = (ip_cand, int(parts[idx]), user, password)
                # 这是一个很好的候选。由于我们可能还有更前面的候选（比如 IPv6 里的数字），
                # 我们需要确保 idx 足够靠后。
                # 但 IPv6 里的数字通常不会被 User/Pass 紧跟。
                # 所以这个猜测通常是正确的。
                return best_guess, None

    # 如果循环结束还没返回（只找到了无 Auth 的候选，或者没找到 Auth 候选）
    if best_guess:
        return best_guess, None
        
    return None, "Ambiguous format"

test_lines = [
    "2a00:1838:20:2::1234:8000:user:pass", 
    "2a00:1838:20:2::1234:8000:user:p:a:s:s", # 密码含冒号
    "2a00:1838:20:2::1234:8000",             # 无密码
    "1.2.3.4:8080:user:pass",
    "1.2.3.4:8080:user:1234",                # 密码是数字
    "2a00::1:8000",                          # IPv6 容易混淆
]

print("Testing Smart Parse...")
for line in test_lines:
    res, err = parse_proxy_smart(line)
    print(f"{line} -> {res} | {err}")
