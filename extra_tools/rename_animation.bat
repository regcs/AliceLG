@echo off
echo ========================================
echo Animation File Renamer for After Effects
echo ========================================
echo.
echo IMPORTANT: This script needs to run in the folder with your animation files!
echo.
echo Current folder: %CD%
echo.
echo Choose an option:
echo 1. Navigate to your animation folder (recommended)
echo 2. Continue in current folder
echo 3. Exit
echo.
set /p choice=Enter your choice (1, 2, or 3): 

if "%choice%"=="1" goto navigate
if "%choice%"=="2" goto diagnostic
if "%choice%"=="3" goto exit
goto invalid

:navigate
echo.
echo Please drag and drop your animation folder here, then press Enter:
set /p folderPath=
if "%folderPath%"=="" goto navigate

REM Remove quotes if they exist
set folderPath=%folderPath:"=%

REM Change to the specified directory
cd /d "%folderPath%" 2>nul
if errorlevel 1 (
    echo Error: Could not access folder "%folderPath%"
    echo Please check the path and try again.
    pause
    goto navigate
)

echo Changed to: %CD%
echo.

:diagnostic
echo Checking for animation files...
echo.

REM Create diagnostic PowerShell script
echo Write-Host "=== CHECKING CURRENT FOLDER ===" > temp_diagnostic.ps1
echo Write-Host "Current folder: $(Get-Location)" >> temp_diagnostic.ps1
echo $allPngs = Get-ChildItem -Filter "*.png" >> temp_diagnostic.ps1
echo Write-Host "Total PNG files found: $($allPngs.Count)" >> temp_diagnostic.ps1
echo Write-Host "" >> temp_diagnostic.ps1
echo if ($allPngs.Count -gt 0) { >> temp_diagnostic.ps1
echo     Write-Host "First 10 filenames:" >> temp_diagnostic.ps1
echo     $allPngs ^| Select-Object -First 10 ^| ForEach-Object { Write-Host "  $($_.Name)" } >> temp_diagnostic.ps1
echo     Write-Host "" >> temp_diagnostic.ps1
echo } >> temp_diagnostic.ps1
echo Write-Host "=== TESTING ANIMATION PATTERNS ===" >> temp_diagnostic.ps1
echo $pattern1 = Get-ChildItem -Filter "*.png" ^| Where-Object { $_.Name -match "^(.+)_(\d{4})_(\d{2})\.png$" } >> temp_diagnostic.ps1
echo Write-Host "Pattern 1 (name_4digits_2digits): $($pattern1.Count) matches" >> temp_diagnostic.ps1
echo $pattern2 = Get-ChildItem -Filter "*.png" ^| Where-Object { $_.Name -match "^(.+)_(\d+)_(\d+)\.png$" } >> temp_diagnostic.ps1
echo Write-Host "Pattern 2 (name_anydigits_anydigits): $($pattern2.Count) matches" >> temp_diagnostic.ps1
echo $hotelFiles = Get-ChildItem -Filter "Hotel_V8_Bunnik_*.png" >> temp_diagnostic.ps1
echo Write-Host "Hotel_V8_Bunnik files: $($hotelFiles.Count)" >> temp_diagnostic.ps1
echo Write-Host "" >> temp_diagnostic.ps1
echo if ($pattern2.Count -gt 0) { >> temp_diagnostic.ps1
echo     Write-Host "Sample files that match:" >> temp_diagnostic.ps1
echo     $pattern2 ^| Select-Object -First 3 ^| ForEach-Object { >> temp_diagnostic.ps1
echo         Write-Host "  $($_.Name)" >> temp_diagnostic.ps1
echo         if ($_.Name -match "^(.+)_(\d+)_(\d+)\.png$") { >> temp_diagnostic.ps1
echo             $name = $matches[1] >> temp_diagnostic.ps1
echo             $frame = $matches[2] >> temp_diagnostic.ps1
echo             $camera = $matches[3] >> temp_diagnostic.ps1
echo             $newName = $name + "_" + $camera + "_" + $frame + ".png" >> temp_diagnostic.ps1
echo             Write-Host "    Would rename to: $newName" >> temp_diagnostic.ps1
echo         } >> temp_diagnostic.ps1
echo     } >> temp_diagnostic.ps1
echo } elseif ($allPngs.Count -gt 0) { >> temp_diagnostic.ps1
echo     Write-Host "No files match the expected animation pattern." >> temp_diagnostic.ps1
echo     Write-Host "Are you sure these are the right files?" >> temp_diagnostic.ps1
echo } else { >> temp_diagnostic.ps1
echo     Write-Host "No PNG files found in this folder!" >> temp_diagnostic.ps1
echo } >> temp_diagnostic.ps1

powershell -ExecutionPolicy Bypass -File temp_diagnostic.ps1

echo.
if exist temp_diagnostic.ps1 del temp_diagnostic.ps1

echo ========================================
echo.
set /p proceed=Do you want to proceed with renaming? (Y/N): 
if /i "%proceed%"=="Y" goto rename
if /i "%proceed%"=="y" goto rename
goto cleanup

:rename
echo.
echo Starting rename process...

echo $files = Get-ChildItem -Filter "*.png" ^| Where-Object { $_.Name -match "^(.+)_(\d+)_(\d+)\.png$" } > temp_rename.ps1
echo Write-Host "Renaming $($files.Count) files..." >> temp_rename.ps1
echo $count = 0 >> temp_rename.ps1
echo foreach ($file in $files) { >> temp_rename.ps1
echo     if ($file.Name -match "^(.+)_(\d+)_(\d+)\.png$") { >> temp_rename.ps1
echo         $name = $matches[1] >> temp_rename.ps1
echo         $frame = $matches[2] >> temp_rename.ps1
echo         $camera = $matches[3] >> temp_rename.ps1
echo         $newName = $name + "_" + $camera + "_" + $frame + ".png" >> temp_rename.ps1
echo         try { >> temp_rename.ps1
echo             Rename-Item -Path $file.FullName -NewName $newName >> temp_rename.ps1
echo             $count++ >> temp_rename.ps1
echo             if ($count %% 1000 -eq 0) { >> temp_rename.ps1
echo                 Write-Host "Processed $count files..." >> temp_rename.ps1
echo             } >> temp_rename.ps1
echo         } >> temp_rename.ps1
echo         catch { >> temp_rename.ps1
echo             Write-Host "Failed to rename: $($file.Name)" >> temp_rename.ps1
echo         } >> temp_rename.ps1
echo     } >> temp_rename.ps1
echo } >> temp_rename.ps1
echo Write-Host "Successfully renamed $count files!" >> temp_rename.ps1

powershell -ExecutionPolicy Bypass -File temp_rename.ps1

:cleanup
if exist temp_rename.ps1 del temp_rename.ps1
echo.
echo ========================================
echo DONE!
echo ========================================
goto end

:invalid
echo Invalid choice. Please enter 1, 2, or 3.
pause
goto navigate

:exit
echo Exiting...
goto end

:end
echo.
pause