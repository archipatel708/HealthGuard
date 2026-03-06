@echo off
cd /d "%~dp0"
echo Starting Disease Predictor...
echo Open http://127.0.0.1:5000 in your browser
venv\Scripts\python app.py
pause
