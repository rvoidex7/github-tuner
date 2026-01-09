@echo off
:: Bu scriptin olduğu klasörü al
set "SCRIPT_DIR=%~dp0"

:: 'src' klasörünü Python'ın arama yoluna (PYTHONPATH) ekle
:: Bu satır 'ModuleNotFoundError' hatasını çözer:
set "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"

:: .env dosyasındaki ayarları yükle
if exist .env (
    for /f "tokens=1* delims==" %%a in ('type .env') do (
        set "%%a=%%b"
    )
)

:: Programı başlat
python -m tuner.cli %*
