@echo off
chcp 65001 >nul
title Texas Hold'em Poker Game
cd /d "%~dp0"
python play_poker.py
pause
