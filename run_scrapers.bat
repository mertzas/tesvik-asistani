@echo off
REM Tum veri kaynaklarini tazeler (TUIK makro, hal fiyatlari, tesvik programlari).
REM
REM ONEMLI: Bu dosya SABIT YOL KULLANMAZ. Onceki hali
REM "cd /d C:\Users\huawei\Desktop\tesvik-asistani" yaziyordu; proje klasoru
REM tasindiginda zamanlanmis gorev sessizce olmustu ve veriler aylarca
REM tazelenmedi (olcum 2026-09-26: makro veri 77 gunluk). %~dp0 bu .bat
REM dosyasinin bulundugu dizindir, yani klasor nereye tasinirsa tasinsin calisir.
REM
REM Klasoru tasidiktan sonra zamanlanmis gorevi yeni yola yonlendirmeyi
REM unutmayin (gorev .bat'in YOLUNU tutar):
REM   schtasks /change /tn TesvikAsistaniScraper /tr "<yeni yol>\run_scrapers.bat"

cd /d "%~dp0"

if not exist "data" mkdir "data"

echo. >> "data\scraper_log.txt"
echo ===== %DATE% %TIME% ===== >> "data\scraper_log.txt"

python -m scripts.tum_verileri_guncelle >> "data\scraper_log.txt" 2>&1
set SONUC=%ERRORLEVEL%

if %SONUC% NEQ 0 (
    echo BASARISIZ: en az bir kaynak guncellenemedi ^(cikis kodu %SONUC%^) >> "data\scraper_log.txt"
) else (
    echo Tum kaynaklar guncellendi. >> "data\scraper_log.txt"
)

exit /b %SONUC%
