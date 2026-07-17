@echo off
REM Wrapper para o Task Scheduler chamar o scraper via Git Bash.
"C:\Program Files\Git\usr\bin\bash.exe" -lc "cd '/c/Users/Maikeo/MSM_Imports_Mercado_Livre/msm_pro/scripts/competitor_scraper' && bash run.sh >> scraper.log 2>&1"
