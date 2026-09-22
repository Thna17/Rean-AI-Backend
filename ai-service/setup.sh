#!/bin/bash
# ReanAI AI Service Quick Start Script

echo "Starting ReanAI AI Service Setup..."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env from example..."
    cp .env.example .env
    echo "Please edit .env with your configuration and API keys."
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment with python3.11..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Setup complete!"
echo ""
echo "To start the AI service on port 8001:"
echo "  uvicorn api.main:app --reload --port 8001"
echo ""
