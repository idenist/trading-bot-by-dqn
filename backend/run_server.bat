@echo off
REM This batch file activates the virtual environment and starts the Uvicorn server.

REM Set the name of your virtual environment directory here.
SET VENV_DIR=.\.venv

ECHO Looking for virtual environment in %VENV_DIR%...

REM Check if the activation script exists.
IF NOT EXIST "%VENV_DIR%\Scripts\activate.bat" (
    ECHO Virtual environment not found in '%VENV_DIR%'.
    ECHO To create a virtual enviornment, run `python -m venv .venv`.
    PAUSE
    EXIT /B 1
)

ECHO Activating virtual environment...
CALL %VENV_DIR%\Scripts\activate.bat

ECHO Starting Uvicorn server...
ECHO Command: uvicorn server:app --host 0.0.0.0 --reload
ECHO You can stop the server by pressing CTRL+C.

start "Uvicorn Server" uvicorn server:app --host 0.0.0.0 --reload
