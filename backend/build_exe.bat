@echo off
set VERSION=1.0.0
for /f "skip=1 tokens=1" %%i in ('wmic os get localdatetime') do if not defined TODAY set TODAY=%%i
set TODAY=%TODAY:~0,4%%TODAY:~4,2%%TODAY:~6,2%
set OUTPUT_NAME=NXAuthManager_%VERSION%_%TODAY%
pyinstaller app.py --name %OUTPUT_NAME% --onefile --noconsole --add-data "..\frontend\dist;frontend\dist" --icon "favicon.ico"
