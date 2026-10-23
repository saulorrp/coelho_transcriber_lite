@echo off
rem Coelho Transcriber Lite, command line. Needs Python 3.12 with PyQt6, httpx and assemblyai.
py -3.12 "%~dp0coelho_cli.py" %*
exit /b %ERRORLEVEL%
