
@echo off
title Updating Macropad Pro...
color 0b

echo Waiting for application to close (PID: 21372)...
timeout /t 2 /nobreak >nul

echo Install started...

:: Source directory (where we extracted)
set "SOURCE=C:\Users\pulak\Desktop\V4_Webview_NodeMCU - Main\Setup Files\temp_update"
:: Destination
set "DEST=C:\Users\pulak\Desktop\V4_Webview_NodeMCU - Main\Setup Files"

echo Source: %SOURCE%
echo Dest: %DEST%

:: Move files
:: Note: In dev mode, we need to be careful. In prod, we just overwrite.
:: GitHub zip extracts to a subfolder usually. We need to find it.
:: For now, we assume UpdateManager flattened it or we copy everything from temp

xcopy "%SOURCE%\*" "%DEST%\" /E /H /Y /C

echo Update applied.
echo Cleaning up...
rmdir /s /q "%SOURCE%"

echo Restarting application...
start "" "C:\Users\pulak\AppData\Local\Programs\Python\Python313\python.exe" "C:\Users\pulak\Desktop\V4_Webview_NodeMCU - Main\Setup Files\run.py"

:: Self-delete script ?? Maybe not needed, good for debug
:: (goto) 2>nul & del "%~f0"
exit
