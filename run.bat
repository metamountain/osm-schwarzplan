@echo off
rem OSM Schwarzplan launcher.
rem   - Double-click to open the app, or
rem   - Drag an .osm file onto this file to load it immediately.
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (py "%~dp0osm_schwarzplan.py" %*) || (python "%~dp0osm_schwarzplan.py" %*)
if errorlevel 1 pause
