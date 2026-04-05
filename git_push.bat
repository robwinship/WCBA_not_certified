@echo off
cd /d "%~dp0"

git add -A

set /p COMMIT_MSG=Enter commit message (or press Enter for default): 
if "%COMMIT_MSG%"=="" set COMMIT_MSG=Update latest files

git commit -m "%COMMIT_MSG%"

echo.
echo Pulling remote changes...
git pull --rebase origin main
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Pull/rebase failed. Please resolve conflicts manually.
    pause
    exit /b 1
)

echo.
echo Pushing to remote...
git push origin main

echo.
pause
