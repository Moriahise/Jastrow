@echo off
chcp 65001 >nul 2>&1
title Jastrow Dictionary - Sefaria Style Version

echo.
echo ================================================================
echo    JASTROW DICTIONARY - Sefaria Style Version
echo    Mit Sefaria API, OpenAI API, eigenem Woerterbuch
echo ================================================================
echo.

REM ================================================================
REM ORDNERSTRUKTUR PRUEFEN/ERSTELLEN
REM ================================================================
echo [1/5] Pruefe Ordnerstruktur...

if not exist "dictionaries" (
    echo       Erstelle dictionaries/ Ordner...
    mkdir dictionaries
)

if not exist "sources" (
    echo       Erstelle sources/ Ordner...
    mkdir sources
)

if not exist "sefaria_cache" (
    echo       Erstelle sefaria_cache/ Ordner...
    mkdir sefaria_cache
)

echo       [OK] Ordnerstruktur vorhanden

REM ================================================================
REM PYTHON PRUEFEN
REM ================================================================
echo.
echo [2/5] Pruefe Python-Installation...

where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo    FEHLER: Python ist nicht installiert!
    echo    Bitte installiere Python von: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo       [OK] Python %PYVER%

REM ================================================================
REM PAKETE PRUEFEN
REM ================================================================
echo.
echo [3/5] Pruefe Python-Pakete...

python -c "import pystray, PIL, pyperclip" >nul 2>&1
if errorlevel 1 (
    echo       Installiere fehlende Pakete...
    pip install pystray pillow pyperclip --quiet --disable-pip-version-check
    echo       [OK] Pakete installiert
) else (
    echo       [OK] Alle Pakete vorhanden
)

REM ================================================================
REM WOERTERBUECHER PRUEFEN
REM ================================================================
echo.
echo [4/5] Pruefe Woerterbuch-Dateien...

set DICT_COUNT=0
for %%f in (dictionaries\merged_dict_*.json) do set /a DICT_COUNT+=1
for %%f in (merged_dict_*.json) do set /a DICT_COUNT+=1

if %DICT_COUNT% GTR 0 (
    echo       [OK] %DICT_COUNT% Woerterbuch-Datei^(en^) gefunden
) else (
    echo       [--] Keine Woerterbuecher - nur Sefaria API
)

REM ================================================================
REM QUELLDATEIEN ZAEHLEN
REM ================================================================
echo.
echo [5/5] Pruefe Quelldateien...

set SRC_COUNT=0
for /r sources %%f in (*.txt) do set /a SRC_COUNT+=1

if %SRC_COUNT% GTR 0 (
    echo       [OK] %SRC_COUNT% Quelldatei^(en^) in sources/
) else (
    echo       [--] Keine TXT-Dateien in sources/
)

REM ================================================================
REM KONFIGURATION ANZEIGEN
REM ================================================================
echo.
echo ================================================================
echo    KONFIGURATION
echo ================================================================
echo.

if exist "config.json" (
    echo    [OK] config.json vorhanden
) else (
    echo    [--] config.json wird beim Start erstellt
)

if exist "query_history.json" (
    echo    [OK] query_history.json vorhanden
) else (
    echo    [--] query_history.json wird beim Start erstellt
)

if exist "user_dictionary.json" (
    echo    [OK] user_dictionary.json vorhanden
) else (
    echo    [--] user_dictionary.json wird beim Start erstellt
)

REM ================================================================
REM STARTEN
REM ================================================================
echo.
echo ================================================================
echo    Starte Jastrow Dictionary...
echo ================================================================
echo.
echo    FEATURES:
echo    ---------
echo    - Sefaria-Style Ausgabe (weisser Hintergrund)
echo    - Sefaria API Integration
echo    - OpenAI API Uebersetzung (DE/EN)
echo    - Eigenes Woerterbuch erstellen
echo    - Dauerhafte Abfrage-Speicherung
echo    - Strg+C Clipboard-Monitoring (IMMER AKTIV)
echo.
echo    BENUTZUNG:
echo    ----------
echo    1. Hebraeischen Text markieren
echo    2. Strg+C druecken
echo    3. Sefaria-Style Fenster erscheint!
echo.
echo    BUTTONS IM FENSTER:
echo    -------------------
echo    - API Uebersetzen: OpenAI Uebersetzung (DE/EN)
echo    - + Woerterbuch: Eigenen Eintrag hinzufuegen
echo    - Sefaria oeffnen: Auf Sefaria.org suchen
echo    - Aktualisieren: Sefaria-Daten neu laden
echo.
echo ================================================================
echo.

python jastrow_manual.py

if errorlevel 1 (
    echo.
    echo [FEHLER] Programm beendet mit Fehler
    pause
)
