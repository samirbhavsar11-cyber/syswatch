#!/bin/bash

echo ""
echo "  🚀 SysWatch"
echo "  ─────────────────────────────────"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  ✗ Python 3 is required. Install it first."
    exit 1
fi

# Install deps if needed
echo "  → Checking dependencies..."
pip3 install -r requirements.txt -q --break-system-packages 2>/dev/null || pip3 install -r requirements.txt -q

echo "  → Starting server..."
echo ""
echo "  ✓ Dashboard available at: http://localhost:5000"
echo "  ✓ Press Ctrl+C to stop"
echo ""

python3 app.py
