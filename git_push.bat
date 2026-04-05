@echo off
cd /d "%~dp0"

git add -A

set /p COMMIT_MSG=Enter commit message (or press Enter for default): 
if "%COMMIT_MSG%"=="" set COMMIT_MSG=Update latest files

git commit -m "%COMMIT_MSG%"
git push origin main

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Push failed. Trying 'master' branch...
    git push origin master
)

echo.
pause
