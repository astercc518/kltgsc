#!/bin/bash

# Stage 1 Web 端真实环境验收测试脚本
# 按照 TASKS.md 中的验收标准进行测试

echo "=========================================="
echo "Stage 1 Web 端真实环境验收测试"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 测试计数器
PASSED=0
FAILED=0
WARNINGS=0

# 测试函数
test_check() {
    local name=$1
    local command=$2
    local expected=$3
    
    echo -n "测试: $name ... "
    result=$(eval "$command" 2>&1)
    
    if echo "$result" | grep -q "$expected"; then
        echo -e "${GREEN}✓ 通过${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ 失败${NC}"
        echo "  实际结果: $result"
        ((FAILED++))
        return 1
    fi
}

test_status_code() {
    local name=$1
    local url=$2
    local expected=$3
    
    echo -n "测试: $name ... "
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>&1)
    
    if [ "$status_code" == "$expected" ]; then
        echo -e "${GREEN}✓ 通过${NC} (状态码: $status_code)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ 失败${NC} (期望: $expected, 实际: $status_code)"
        ((FAILED++))
        return 1
    fi
}

test_json_contains() {
    local name=$1
    local url=$2
    local key=$3
    
    echo -n "测试: $name ... "
    response=$(curl -s "$url" 2>&1)
    
    if echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if '$key' in str(data) else 1)" 2>/dev/null; then
        echo -e "${GREEN}✓ 通过${NC}"
        echo "  响应: $response" | head -c 150
        echo ""
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ 失败${NC}"
        echo "  响应: $response"
        ((FAILED++))
        return 1
    fi
}

# ==========================================
# 1.1 后端基础设置验收
# ==========================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}1.1 后端基础设置验收${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

echo "1.1.1 后端服务启动测试"
echo "----------------------------------------"
test_status_code "访问 Swagger UI" "http://localhost:8000/docs" "200"
test_status_code "访问健康检查接口" "http://localhost:8000/api/v1/health" "200"
test_json_contains "健康检查返回正确JSON" "http://localhost:8000/api/v1/health" "status"
test_json_contains "健康检查包含 message" "http://localhost:8000/api/v1/health" "message"
echo ""

echo "1.1.2 数据库连接测试"
echo "----------------------------------------"
if [ -f "/var/tgsc/backend/tgsc.db" ]; then
    echo -e "${GREEN}✓ 数据库文件存在${NC} (/var/tgsc/backend/tgsc.db)"
    ((PASSED++))
else
    echo -e "${RED}✗ 数据库文件不存在${NC}"
    ((FAILED++))
fi

test_status_code "账号列表接口（数据库操作）" "http://localhost:8000/api/v1/accounts/" "200"
test_json_contains "账号列表返回JSON数组" "http://localhost:8000/api/v1/accounts/" "[]"
echo ""

echo "1.1.3 CORS 配置测试"
echo "----------------------------------------"
cors_test=$(curl -s -H "Origin: http://localhost:3000" \
    -H "Access-Control-Request-Method: GET" \
    -X OPTIONS \
    http://localhost:8000/api/v1/health -I 2>&1 | grep -i "access-control-allow-origin")

if echo "$cors_test" | grep -q "localhost:3000"; then
    echo -e "${GREEN}✓ CORS 配置正确${NC}"
    echo "  $cors_test"
    ((PASSED++))
else
    echo -e "${RED}✗ CORS 配置错误${NC}"
    echo "  响应: $cors_test"
    ((FAILED++))
fi

# 测试实际请求的 CORS 头
cors_actual=$(curl -s -H "Origin: http://localhost:3000" \
    http://localhost:8000/api/v1/health -I 2>&1 | grep -i "access-control-allow-origin")

if echo "$cors_actual" | grep -q "localhost:3000"; then
    echo -e "${GREEN}✓ 实际请求 CORS 头正确${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ CORS 头可能未在 GET 请求中返回（这是正常的）${NC}"
    ((WARNINGS++))
fi
echo ""

# ==========================================
# 1.2 前端基础设置验收
# ==========================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}1.2 前端基础设置验收${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

echo "1.2.1 前端服务启动测试"
echo "----------------------------------------"
test_status_code "访问前端页面" "http://localhost:3000" "200"

# 检查页面内容
frontend_content=$(curl -s http://localhost:3000 | grep -i "tgsc\|react\|vite" | head -1)
if [ -n "$frontend_content" ]; then
    echo -e "${GREEN}✓ 前端页面内容正常${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ 无法验证页面内容（可能需要 JavaScript 渲染）${NC}"
    ((WARNINGS++))
fi
echo ""

echo "1.2.2 API 代理测试"
echo "----------------------------------------"
test_status_code "前端代理健康检查" "http://localhost:3000/api/v1/health" "200"
test_json_contains "前端代理返回正确JSON" "http://localhost:3000/api/v1/health" "status"

# 验证前端代理返回与后端一致
backend_response=$(curl -s http://localhost:8000/api/v1/health)
frontend_proxy_response=$(curl -s http://localhost:3000/api/v1/health)

if [ "$backend_response" == "$frontend_proxy_response" ]; then
    echo -e "${GREEN}✓ 前端代理响应与后端一致${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ 前端代理响应与后端不一致${NC}"
    echo "  后端: $backend_response"
    echo "  前端代理: $frontend_proxy_response"
    ((FAILED++))
fi
echo ""

# ==========================================
# 1.3 前后端集成测试验收
# ==========================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}1.3 前后端集成测试验收${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

echo "1.3.1 正常流程测试"
echo "----------------------------------------"
# 验证健康检查接口可访问
health_response=$(curl -s http://localhost:8000/api/v1/health)
if echo "$health_response" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}✓ 后端健康检查接口正常${NC}"
    echo "  响应: $health_response"
    ((PASSED++))
else
    echo -e "${RED}✗ 后端健康检查接口异常${NC}"
    ((FAILED++))
fi

# 验证前端能通过代理访问
frontend_health=$(curl -s http://localhost:3000/api/v1/health)
if echo "$frontend_health" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}✓ 前端能通过代理访问后端${NC}"
    echo "  响应: $frontend_health"
    ((PASSED++))
else
    echo -e "${RED}✗ 前端无法通过代理访问后端${NC}"
    ((FAILED++))
fi
echo ""

echo "1.3.2 错误处理测试（模拟后端关闭）"
echo "----------------------------------------"
echo -e "${YELLOW}⚠ 注意：此测试需要手动停止后端服务${NC}"
echo "  测试步骤："
echo "  1. 停止后端: docker-compose stop backend"
echo "  2. 刷新前端页面"
echo "  3. 检查是否显示友好错误提示"
echo "  4. 重启后端: docker-compose start backend"
echo ""
((WARNINGS++))

# ==========================================
# Stage 1 整体验收清单
# ==========================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}Stage 1 整体验收清单${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

checklist_items=(
    "后端服务正常启动，Swagger UI 可访问"
    "前端服务正常启动，页面正常显示"
    "前端能成功调用后端健康检查接口"
    "前后端通过 Docker Compose 能同时启动"
    "浏览器控制台无错误（需手动检查）"
)

for item in "${checklist_items[@]}"; do
    echo -e "  [ ] $item"
done
echo ""

# ==========================================
# 测试总结
# ==========================================
echo "=========================================="
echo "测试总结"
echo "=========================================="
echo -e "${GREEN}通过: $PASSED${NC}"
echo -e "${RED}失败: $FAILED${NC}"
echo -e "${YELLOW}警告: $WARNINGS${NC}"
echo "总计测试: $((PASSED + FAILED + WARNINGS))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有自动化测试通过！${NC}"
    echo ""
    echo "下一步："
    echo "1. 在浏览器中打开 http://localhost:3000"
    echo "2. 检查 Dashboard 页面是否显示后端状态"
    echo "3. 检查浏览器控制台（F12）是否有错误"
    echo "4. 测试侧边栏菜单切换功能"
    echo "5. 访问 http://localhost:8000/docs 查看 Swagger UI"
    exit 0
else
    echo -e "${RED}✗ 部分测试失败，请检查上述错误${NC}"
    exit 1
fi
