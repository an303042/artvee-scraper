#!/bin/bash
# install.sh
# One-click installer for artvee-scraper on Unix/Linux/macOS

echo "========================================"
echo "Welcome to the artvee-scraper Installer"
echo "========================================"
echo

# Function to display error and exit
function error_exit {
    echo "Error: $1"
    exit 1
}

# Check if Python is installed
if ! command -v python3 &>/dev/null; then
    error_exit "Python is not installed. Please install Python 3.8 or higher."
fi

# Check if Git is installed
if ! command -v git &>/dev/null; then
    error_exit "Git is not installed. Please install Git."
fi

# Create Virtual Environment
echo "Creating Python virtual environment..."
python3 -m venv venv || error_exit "Failed to create virtual environment."

# Activate Virtual Environment
echo "Activating virtual environment..."
source venv/bin/activate || error_exit "Failed to activate virtual environment."

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip || error_exit "Failed to upgrade pip."

# Install Dependencies
echo "Installing dependencies..."
pip install -r requirements.txt || error_exit "Failed to install dependencies."

# Install the Package
echo "Installing artvee-scraper package..."
pip install -e . || error_exit "Failed to install the artvee-scraper package."

# Deactivate Virtual Environment
echo "Deactivating virtual environment..."
deactivate

echo
echo "Installation completed successfully!"
echo "To use the artvee-scraper, navigate to the project directory and activate the virtual environment:"
echo
echo "    source venv/bin/activate"
echo
echo "Then, you can run commands like:"
echo
echo "    artvee-scraper --help"
echo
echo "Installation script has finished."
