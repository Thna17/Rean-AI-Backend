#!/bin/bash
# Ollama Optimization Script for ReanAI local development

echo "🚀 ReanAI - Ollama Optimization Script"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Functions to print colored output
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

echo "📋 Analyzing system resources..."
echo ""

# Detect hardware
CPU_CORES=$(sysctl -n hw.physicalcpu 2>/dev/null || nproc --all 2>/dev/null || echo "4")
LOGICAL_CORES=$(sysctl -n hw.logicalcpu 2>/dev/null || nproc 2>/dev/null || echo "4")
RAM_GB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1024/1024/1024}' || echo "8")

echo "Current Hardware:"
echo "  CPU: ${CPU_CORES} cores / ${LOGICAL_CORES} threads"
echo "  RAM: ${RAM_GB} GB"
echo ""

# Check current model
echo "📦 Installed models:"
ollama list 2>/dev/null || echo "Ollama is not running or not in PATH"
echo ""

# Menu options
echo "Select optimization mode:"
echo ""
echo "1. 🎯 STREAMING MODE (Recommended for local dev)"
echo "   → Keep current model, enable streaming"
echo "   → Low perceived latency"
echo ""
echo "2. ⚡ FAST MODEL (Phi-3 Mini)"
echo "   → Download 2.3GB model"
echo "   → Fast inference (~3-5s)"
echo ""
echo "3. 🚄 ULTRA FAST (Gemma2 2B)"
echo "   → Download 1.6GB model"
echo "   → Very fast inference (~2-4s)"
echo ""
echo "0. ❌ Exit"
echo ""

read -p "Enter choice (0-3): " choice

case $choice in
    1)
        echo ""
        print_warning "Configuring STREAMING MODE..."
        cd "$(dirname "$0")/.."
        if ! grep -q "OLLAMA_STREAM" .env 2>/dev/null; then
            echo "" >> .env
            echo "# Streaming optimization" >> .env
            echo "OLLAMA_STREAM=true" >> .env
            echo "OLLAMA_NUM_CTX=4096" >> .env
            echo "OLLAMA_NUM_THREAD=${CPU_CORES}" >> .env
            echo "OLLAMA_TIMEOUT=15" >> .env
        fi
        print_success "Configuration updated!"
        ;;
    2)
        echo ""
        print_warning "Downloading Phi-3 Mini (2.3GB)..."
        ollama pull phi-3:mini
        if [ $? -eq 0 ]; then
            print_success "Downloaded!"
            echo "Update .env with: OLLAMA_MODEL=phi-3:mini"
        else
            print_error "Download failed"
        fi
        ;;
    3)
        echo ""
        print_warning "Downloading Gemma2 2B (1.6GB)..."
        ollama pull gemma2:2b
        if [ $? -eq 0 ]; then
            print_success "Downloaded!"
            echo "Update .env with: OLLAMA_MODEL=gemma2:2b"
        else
            print_error "Download failed"
        fi
        ;;
    0)
        echo "Exiting."
        exit 0
        ;;
    *)
        print_error "Invalid choice"
        exit 1
        ;;
esac

echo ""
print_success "Done! Restart AI service to apply changes if needed."
