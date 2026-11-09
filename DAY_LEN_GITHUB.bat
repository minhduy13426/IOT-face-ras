@echo off
chcp 65001 > nul
title Day Du An Len GitHub
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0DAY_LEN_GITHUB.ps1"
pause

