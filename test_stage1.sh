#!/bin/bash

# Stage 1 验收测试脚本
# 用于自动化测试 Stage 1 的各项功能

echo "=========================================="
echo "Stage 1 验收测试"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数器
PASSED=0
FAILED=0

# 测试函数
test_endpoint() {
    local name=$1
    local url=$2
    local expected_status=$3
    
    echo -n "测试: $name ... "
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    
    if [ "$status_code" == "$expected_status" ]; then
        echo -e "${GREEN}✓ 通过${NC} (状态码: $status_code)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ 失败${NC} (期望: $expected_status, 实际: $status_code)"
        ((FAILED++))
        return 1
    fi
}

test_json_response() {
    local name=$1
    local url=$2
    local expected_key=$3
    
    echo -n "测试: $name ... "
    response=$(curl -s "$url")
    
    # 检查是否是有效的JSON
    if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
        # 如果是数组，检查是否为空数组或包含expected_key
        # 如果是对象，检查是否包含expected_key
        if echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if (isinstance(data, list) and len(data) == 0) or (isinstance(data, dict) and '$expected_key' in data) or '$expected_key' in str(data) else 1)" 2>/dev/null; then
            echo -e "${GREEN}✓ 通过${NC}"
            echo "  响应: $response" | head -c 100
            echo ""
            ((PASSED++))
            return 0
        else
            echo -e "${RED}✗ 失败${NC}"
            echo "  响应: $response"
            ((FAILED++))
            return 1
        fi
    else
        echo -e "${RED}✗ 失败 - 无效的JSON${NC}"
        echo "  响应: $response"
        ((FAILED++))
        return 1
    fi
}

# 1. 后端服务测试
echo "1. 后端服务测试"
echo "----------------------------------------"
test_endpoint "后端健康检查接口" "http://localhost:8000/api/v1/health" "200"
test_json_response "健康检查返回JSON" "http://localhost:8000/api/v1/health" "status"
test_endpoint "Swagger UI 文档" "http://localhost:8000/docs" "200"
test_endpoint "API 根路径" "http://localhost:8000/api/v1/" "200"
test_json_response "API 根路径返回JSON" "http://localhost:8000/api/v1/" "message"
echo ""

# 2. 数据库测试
echo "2. 数据库连接测试"
echo "----------------------------------------"
if [ -f "/var/tgsc/backend/tgsc.db" ]; then
    echo -e "${GREEN}✓ 数据库文件存在${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ 数据库文件不存在${NC}"
    ((FAILED++))
fi

test_endpoint "账号列表接口" "http://localhost:8000/api/v1/accounts/" "200"
test_json_response "账号列表返回JSON数组" "http://localhost:8000/api/v1/accounts/" "[]"
echo ""

# 3. CORS 测试
echo "3. CORS 配置测试"
echo "----------------------------------------"
cors_headers=$(curl -s -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: GET" -X OPTIONS http://localhost:8000/api/v1/health -I 2>&1 | grep -i "access-control-allow-origin")

if echo "$cors_headers" | grep -q "localhost:3000"; then
    echo -e "${GREEN}✓ CORS 配置正确${NC}"
    echo "  $cors_headers"
    ((PASSED++))
else
    echo -e "${RED}✗ CORS 配置错误${NC}"
    ((FAILED++))
fi
echo ""

# 4. 前端服务测试
echo "4. 前端服务测试"
echo "----------------------------------------"
test_endpoint "前端页面" "http://localhost:3000" "200"
test_endpoint "前端代理健康检查" "http://localhost:3000/api/v1/health" "200"
test_json_response "前端代理返回JSON" "http://localhost:3000/api/v1/health" "status"
echo ""

# 5. 前后端集成测试
echo "5. 前后端集成测试"
echo "----------------------------------------"
backend_health=$(curl -s http://localhost:8000/api/v1/health)
frontend_proxy=$(curl -s http://localhost:3000/api/v1/health)

if [ "$backend_health" == "$frontend_proxy" ]; then
    echo -e "${GREEN}✓ 前后端集成正常${NC}"
    echo "  后端响应: $backend_health"
    echo "  前端代理响应: $frontend_proxy"
    ((PASSED++))
else
    echo -e "${RED}✗ 前后端集成异常${NC}"
    echo "  后端响应: $backend_health"
    echo "  前端代理响应: $frontend_proxy"
    ((FAILED++))
fi
echo ""

# 总结
echo "=========================================="
echo "测试总结"
echo "=========================================="
echo -e "${GREEN}通过: $PASSED${NC}"
echo -e "${RED}失败: $FAILED${NC}"
echo "总计: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！Stage 1 验收成功！${NC}"
    exit 0
else
    echo -e "${RED}✗ 部分测试失败，请检查上述错误${NC}"
    exit 1
fi
