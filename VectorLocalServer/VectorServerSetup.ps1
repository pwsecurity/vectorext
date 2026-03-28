# ============================================================
# Vector AI Local Server — Windows Installer
# ============================================================
# This script:
#   1. Checks if Python is installed (installs if missing)
#   2. Downloads server files from GitHub
#   3. Installs pip packages
#   4. Creates a Desktop shortcut
#   5. Configures Windows Firewall
# ============================================================
# Run with: powershell -Command "irm https://raw.githubusercontent.com/pwsecurity/vectorext/main/VectorLocalServer/VectorServerSetup.ps1 | iex"
# ============================================================

Add-Type -AssemblyName PresentationFramework
$msgTitle = "Vector AI Server Setup"
$installDir = "C:\VectorAI\Server"
$githubBase = "https://raw.githubusercontent.com/pwsecurity/vectorext/main/VectorLocalServer"

# ============================================================
# STEP 0: Self-Elevation (Run as Admin)
# ============================================================
if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host ""
    Write-Host "  ========================================" -ForegroundColor Yellow
    Write-Host "    Requesting Administrator privileges..." -ForegroundColor Yellow
    Write-Host "  ========================================" -ForegroundColor Yellow
    Write-Host ""
    
    # Re-run this script as admin
    $scriptContent = (New-Object Net.WebClient).DownloadString("$githubBase/VectorServerSetup.ps1")
    $tempScript = "$env:TEMP\VectorServerSetup_temp.ps1"
    $scriptContent | Out-File -FilePath $tempScript -Encoding utf8
    Start-Process powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$tempScript`"" -Verb RunAs
    exit
}

Clear-Host
Write-Host ""
Write-Host "  ==========================================" -ForegroundColor Cyan
Write-Host "    VECTOR AI LOCAL SERVER — INSTALLER" -ForegroundColor Cyan
Write-Host "  ==========================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# STEP 1: Check Python
# ============================================================
Write-Host "  [1/6] Checking Python installation..." -ForegroundColor Yellow

$pythonCmd = $null
$pythonVersion = $null

# Try 'python' first
try {
    $ver = & python --version 2>&1
    if ($ver -match "Python (\d+\.\d+)") {
        $pythonVersion = $Matches[1]
        $major = [int]($pythonVersion.Split('.')[0])
        $minor = [int]($pythonVersion.Split('.')[1])
        if ($major -ge 3 -and $minor -ge 8) {
            $pythonCmd = "python"
            Write-Host "        Found: $ver" -ForegroundColor Green
        }
    }
} catch {}

# Try 'python3' if 'python' failed
if (-not $pythonCmd) {
    try {
        $ver = & python3 --version 2>&1
        if ($ver -match "Python (\d+\.\d+)") {
            $pythonVersion = $Matches[1]
            $major = [int]($pythonVersion.Split('.')[0])
            $minor = [int]($pythonVersion.Split('.')[1])
            if ($major -ge 3 -and $minor -ge 8) {
                $pythonCmd = "python3"
                Write-Host "        Found: $ver" -ForegroundColor Green
            }
        }
    } catch {}
}

# Try common install locations
if (-not $pythonCmd) {
    $commonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe"
    )
    foreach ($p in $commonPaths) {
        if (Test-Path $p) {
            $pythonCmd = $p
            Write-Host "        Found at: $p" -ForegroundColor Green
            break
        }
    }
}

# Python not found — install it
if (-not $pythonCmd) {
    Write-Host "        Python not found. Installing Python 3.12..." -ForegroundColor Red
    Write-Host ""
    
    $pythonUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
    $pythonInstaller = "$env:TEMP\python_installer.exe"
    
    Write-Host "        Downloading Python installer..." -ForegroundColor Yellow
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        (New-Object Net.WebClient).DownloadFile($pythonUrl, $pythonInstaller)
    } catch {
        Write-Host "        ERROR: Failed to download Python." -ForegroundColor Red
        Write-Host "        Please install Python 3.8+ manually from https://python.org" -ForegroundColor Red
        Write-Host ""
        Read-Host "        Press Enter to exit"
        exit 1
    }
    
    Write-Host "        Installing Python (this may take 1-2 minutes)..." -ForegroundColor Yellow
    $installArgs = "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_test=0"
    $proc = Start-Process $pythonInstaller -ArgumentList $installArgs -Wait -PassThru
    
    if ($proc.ExitCode -ne 0) {
        Write-Host "        ERROR: Python installation failed (Exit code: $($proc.ExitCode))." -ForegroundColor Red
        Write-Host "        Please install Python 3.8+ manually from https://python.org" -ForegroundColor Red
        Write-Host ""
        Read-Host "        Press Enter to exit"
        exit 1
    }
    
    # Clean up installer
    Remove-Item $pythonInstaller -ErrorAction SilentlyContinue
    
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    
    # Verify
    try {
        $ver = & python --version 2>&1
        $pythonCmd = "python"
        Write-Host "        Python installed successfully: $ver" -ForegroundColor Green
    } catch {
        # Try common path
        $pythonCmd = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
        if (!(Test-Path $pythonCmd)) {
            $pythonCmd = "C:\Program Files\Python312\python.exe"
        }
        if (!(Test-Path $pythonCmd)) {
            Write-Host "        ERROR: Python installed but not found in PATH." -ForegroundColor Red
            Write-Host "        Please restart your computer and run this installer again." -ForegroundColor Red
            Write-Host ""
            Read-Host "        Press Enter to exit"
            exit 1
        }
        Write-Host "        Python installed at: $pythonCmd" -ForegroundColor Green
    }
}

Write-Host ""

# ============================================================
# STEP 2: Create Install Directory
# ============================================================
Write-Host "  [2/6] Creating install directory..." -ForegroundColor Yellow

if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    Write-Host "        Created: $installDir" -ForegroundColor Green
} else {
    Write-Host "        Already exists: $installDir" -ForegroundColor Green
}
Write-Host ""

# ============================================================
# STEP 3: Download Server Files from GitHub
# ============================================================
Write-Host "  [3/6] Downloading server files from GitHub..." -ForegroundColor Yellow

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$files = @(
    @{Name = "server_local.py";        Url = "$githubBase/server_local.py"},
    @{Name = "requirements_local.txt"; Url = "$githubBase/requirements_local.txt"},
    @{Name = "start_vector.bat";       Url = "$githubBase/start_vector.bat"}
)

foreach ($file in $files) {
    $dest = "$installDir\$($file.Name)"
    Write-Host "        Downloading $($file.Name)..." -ForegroundColor Gray
    try {
        (New-Object Net.WebClient).DownloadFile($file.Url, $dest)
        Write-Host "        OK: $($file.Name)" -ForegroundColor Green
    } catch {
        Write-Host "        ERROR: Failed to download $($file.Name)" -ForegroundColor Red
        Write-Host "        URL: $($file.Url)" -ForegroundColor Red
        Write-Host "        Error: $_" -ForegroundColor Red
        Write-Host ""
        Read-Host "        Press Enter to exit"
        exit 1
    }
}
Write-Host ""

# ============================================================
# STEP 4: Install Python Packages
# ============================================================
Write-Host "  [4/6] Installing Python packages..." -ForegroundColor Yellow
Write-Host "        (This may take 1-2 minutes on first install)" -ForegroundColor Gray
Write-Host ""

$pipResult = Start-Process $pythonCmd -ArgumentList "-m pip install -r `"$installDir\requirements_local.txt`" --quiet" -Wait -NoNewWindow -PassThru

if ($pipResult.ExitCode -ne 0) {
    Write-Host "        WARNING: Some packages may have failed." -ForegroundColor Yellow
    Write-Host "        Trying again with --user flag..." -ForegroundColor Yellow
    Start-Process $pythonCmd -ArgumentList "-m pip install -r `"$installDir\requirements_local.txt`" --user --quiet" -Wait -NoNewWindow
}

Write-Host "        Packages installed." -ForegroundColor Green
Write-Host ""

# ============================================================
# STEP 5: Create Desktop Shortcut
# ============================================================
Write-Host "  [5/6] Creating Desktop shortcut..." -ForegroundColor Yellow

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = "$desktopPath\Vector Server.lnk"

try {
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($shortcutPath)
    $Shortcut.TargetPath = "$installDir\start_vector.bat"
    $Shortcut.WorkingDirectory = $installDir
    $Shortcut.Description = "Start Vector AI Local Server"
    $Shortcut.IconLocation = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe,0"
    $Shortcut.Save()
    Write-Host "        Shortcut created on Desktop!" -ForegroundColor Green
} catch {
    Write-Host "        WARNING: Could not create shortcut automatically." -ForegroundColor Yellow
    Write-Host "        You can manually create a shortcut to: $installDir\start_vector.bat" -ForegroundColor Yellow
}
Write-Host ""

# ============================================================
# STEP 6: Windows Firewall
# ============================================================
Write-Host "  [6/6] Configuring Windows Firewall..." -ForegroundColor Yellow

try {
    netsh advfirewall firewall delete rule name="Vector AI Server" 2>&1 | Out-Null
    netsh advfirewall firewall add rule name="Vector AI Server" dir=in action=allow protocol=TCP localport=5002 2>&1 | Out-Null
    Write-Host "        Firewall rule added for port 5002." -ForegroundColor Green
} catch {
    Write-Host "        WARNING: Could not add firewall rule. Server may still work." -ForegroundColor Yellow
}
Write-Host ""

# ============================================================
# DONE!
# ============================================================
Write-Host ""
Write-Host "  ==========================================" -ForegroundColor Green
Write-Host "    INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "  ==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  HOW TO USE:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Double-click 'Vector Server' on your Desktop" -ForegroundColor White
Write-Host "  2. Wait for the server to start (you will see a message)" -ForegroundColor White
Write-Host "  3. Open Chrome and use the Vector extension" -ForegroundColor White
Write-Host "  4. The extension will auto-detect your local server" -ForegroundColor White
Write-Host ""
Write-Host "  TO STOP:" -ForegroundColor Cyan
Write-Host "  Just close the black terminal window, or shut down your PC." -ForegroundColor White
Write-Host ""
Write-Host "  FILES INSTALLED TO:" -ForegroundColor Cyan
Write-Host "  $installDir" -ForegroundColor White
Write-Host ""
Write-Host "  ==========================================" -ForegroundColor Green
Write-Host ""

# Show popup
[System.Windows.MessageBox]::Show(
    "Vector AI Server installed successfully!`n`n" +
    "HOW TO USE:`n" +
    "1. Double-click 'Vector Server' on your Desktop`n" +
    "2. Open Chrome and use the Vector extension`n" +
    "3. Close the terminal window to stop the server`n`n" +
    "Files installed to: $installDir",
    $msgTitle, "OK", "Information"
) | Out-Null

Read-Host "  Press Enter to close this window"
