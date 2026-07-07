@echo off
cd /d "C:\Users\huawei\Desktop\tesvik-asistani"
python -m app.scrapers.run_all >> "C:\Users\huawei\Desktop\tesvik-asistani\data\scraper_log.txt" 2>&1
