@echo off
REM install.bat
REM One-click installer for artvee-scraper on Windows

echo ========================================
echo Welcome to the artvee-scraper Installer
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not added to PATH.
    echo Please install Python 3.8 or higher from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check if Git is installed
git --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Git is not installed or not added to PATH.
    echo Please install Git from https://git-scm.com/downloads
    pause
    exit /b 1
)

REM Create Virtual Environment
echo Creating Python virtual environment...
python -m venv venv
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to create virtual environment.
    pause
    exit /b 1
)

REM Activate Virtual Environment
echo Activating virtual environment...
call venv\Scripts\activate
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to upgrade pip.
    pause
    exit /b 1
)

REM Install Dependencies
echo Installing dependencies...
pip install -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to install dependencies.
    pause
    exit /b 1
)

REM Install the Package
echo Installing artvee-scraper package...
pip install -e .
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to install the artvee-scraper package.
    pause
    exit /b 1
)

REM Deactivate Virtual Environment
echo Deactivating virtual environment...
deactivate

echo.
echo Installation completed successfully!
echo You can now use the artvee-scraper by activating the virtual environment:
echo.
echo     venv\Scripts\activate
	echo.
echo And then running commands like:
echo.
echo     artvee-scraper --help
echo.
echo Press any key to exit...
pause >nul
