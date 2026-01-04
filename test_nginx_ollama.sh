#!/bin/bash
# Test script for nginx-ollama configuration

echo "============================================================"
echo "Nginx-Ollama Configuration Test"
echo "============================================================"
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check nginx status
echo "Test 1: Checking nginx status..."
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}[OK]${NC} Nginx is running"
else
    echo -e "${RED}[ERROR]${NC} Nginx is not running"
    echo "   Run: sudo systemctl start nginx"
    exit 1
fi
echo

# Test 2: Check nginx configuration
echo "Test 2: Testing nginx configuration..."
if sudo nginx -t 2>&1 | grep -q "successful"; then
    echo -e "${GREEN}[OK]${NC} Nginx configuration is valid"
else
    echo -e "${RED}[ERROR]${NC} Nginx configuration has errors:"
    sudo nginx -t
    exit 1
fi
echo

# Test 3: Check if port 11435 is listening
echo "Test 3: Checking if port 11435 is listening..."
if sudo netstat -tlnp | grep -q ":11435"; then
    echo -e "${GREEN}[OK]${NC} Port 11435 is listening"
    sudo netstat -tlnp | grep ":11435"
else
    echo -e "${YELLOW}[WARNING]${NC} Port 11435 is not listening"
    echo "   Make sure nginx config is loaded"
fi
echo

# Test 4: Check Ollama container
echo "Test 4: Checking Ollama container..."
if docker ps | grep -q ollama; then
    echo -e "${GREEN}[OK]${NC} Ollama container is running"
    docker ps | grep ollama
else
    echo -e "${RED}[ERROR]${NC} Ollama container is not running"
    exit 1
fi
echo

# Test 5: Test direct connection to Ollama (localhost)
echo "Test 5: Testing direct connection to Ollama (localhost:11434)..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo -e "${GREEN}[OK]${NC} Ollama is accessible on localhost:11434"
    MODEL_COUNT=$(curl -s http://localhost:11434/api/tags | jq '.models | length' 2>/dev/null || echo "?")
    echo "   Found $MODEL_COUNT model(s)"
else
    echo -e "${RED}[ERROR]${NC} Cannot connect to Ollama on localhost:11434"
    exit 1
fi
echo

# Test 6: Test through nginx (localhost)
echo "Test 6: Testing through nginx (localhost:11435)..."
if curl -s http://localhost:11435/api/tags > /dev/null; then
    echo -e "${GREEN}[OK]${NC} Nginx proxy is working on localhost:11435"
    MODEL_COUNT=$(curl -s http://localhost:11435/api/tags | jq '.models | length' 2>/dev/null || echo "?")
    echo "   Found $MODEL_COUNT model(s)"
else
    echo -e "${RED}[ERROR]${NC} Cannot connect through nginx on localhost:11435"
    echo "   Check nginx error log: sudo tail -20 /var/log/nginx/error.log"
    exit 1
fi
echo

# Test 7: Test from external IP (if accessible)
EXTERNAL_IP=$(hostname -I | awk '{print $1}')
echo "Test 7: Testing from external IP ($EXTERNAL_IP:11435)..."
if curl -s --max-time 5 http://$EXTERNAL_IP:11435/api/tags > /dev/null; then
    echo -e "${GREEN}[OK]${NC} Nginx is accessible from external IP"
else
    echo -e "${YELLOW}[WARNING]${NC} Cannot connect from external IP"
    echo "   This might be normal if testing from outside the network"
fi
echo

echo "============================================================"
echo -e "${GREEN}All local tests passed!${NC}"
echo "============================================================"
echo
echo "Next steps:"
echo "1. Test from external network: curl http://37.255.205.140:11435/api/tags"
echo "2. Check nginx logs: sudo tail -f /var/log/nginx/error.log"
echo "3. Check nginx access logs: sudo tail -f /var/log/nginx/access.log"

