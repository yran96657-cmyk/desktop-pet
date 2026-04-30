@echo off
chcp 65001 >nul 2>&1
echo Installing build dependencies...
pip install -r requirements-build.txt

echo.
echo Building exe...
pyinstaller desktop_pet.spec --clean

echo.
echo Done! Check dist\desktop_pet.exe
pause
