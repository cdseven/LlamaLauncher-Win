@echo off
setlocal enabledelayedexpansion

:: Set the source folder (where the script is located)
set "SOURCE=%~dp0"

:: Get the name of the folder containing the script
set "SCRIPT_DIR=%SOURCE:~0,-1%"
for %%F in ("%SCRIPT_DIR%") do set "FOLDER_NAME=%%~nxF"

:: Set the base target folder name in the parent directory
set "BASE_TARGET=%SOURCE%..\%FOLDER_NAME%"

:: Initialize counter
set "COUNTER=1"

:: Create a temporary exclude file (use %TEMP% which is usually a short path)
set "EXCLUDE_FILE=%TEMP%\exclude_list.txt"
echo \bin\> "%EXCLUDE_FILE%"
echo \models\>> "%EXCLUDE_FILE%"

:: Show exclude file for debugging
echo Exclude patterns:
type "%EXCLUDE_FILE%"
echo.

:: Find a unique folder name by incrementing suffix
:loop
set "TARGET=%BASE_TARGET%_%COUNTER%"
if exist "%TARGET%" (
    set /A COUNTER+=1
    goto loop
)

:: Create the unique target folder
mkdir "%TARGET%"

:: Copy all files and subfolders using xcopy, excluding specified folders
:: Note: /EXCLUDE: must NOT have quotes around the filename
xcopy "%SOURCE%" "%TARGET%" /E /I /Q /EXCLUDE:%EXCLUDE_FILE%

:: Capture the result using delayed expansion
set "XCOPY_RESULT=!ERRORLEVEL!"

:: Clean up the exclude file
del "%EXCLUDE_FILE%" 2>nul

:: Check result
if !XCOPY_RESULT! == 0 (
    echo Copy completed successfully to: %TARGET%
) else (
    echo Copy failed with error code: !XCOPY_RESULT!
)

endlocal
pause
