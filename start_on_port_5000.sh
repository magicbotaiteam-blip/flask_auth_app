#!/bin/bash
# Start Magic Bot AI on port 5000, freeing the port if needed

echo "================================================"
echo "Starting Magic Bot AI on port 5000"
echo "================================================"

# Check if port 5000 is in use
if lsof -ti:5000 > /dev/null 2>&1; then
    echo "Port 5000 is in use. Attempting to free it..."
    
    # Get the process using port 5000
    PID=$(lsof -ti:5000)
    echo "Process using port 5000: PID $PID"
    
    # Kill the process
    kill -9 $PID 2>/dev/null
    sleep 1
    
    # Check if it's still running
    if lsof -ti:5000 > /dev/null 2>&1; then
        echo "❌ Could not free port 5000. Please check manually."
        echo "Try: lsof -i :5000"
        exit 1
    else
        echo "✅ Port 5000 freed successfully"
    fi
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Start the app
echo ""
echo "Starting Magic Bot AI on http://localhost:5000"
echo "Press Ctrl+C to stop"
echo "================================================"

python run_app.py