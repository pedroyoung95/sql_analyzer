@echo off
setlocal
python -m pip install -r requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed --name "SQL조건분석기" sql_analyze_app/main.py
echo.
echo Build complete: dist\SQL조건분석기.exe
pause
