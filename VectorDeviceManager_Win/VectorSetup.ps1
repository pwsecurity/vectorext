# Vector Device Manager - PowerShell Pro Installer
# Version: V19 (Fixed File-Locking Bug)

Add-Type -AssemblyName PresentationFramework
$msgTitle = "Vector AI Setup"

# 1. Self-Elevation (Run as Admin)
if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

function Show-Popup($msg, $icon = "Information") {
    [System.Windows.MessageBox]::Show($msg, $msgTitle, "OK", $icon)
}

Write-Host "Starting Vector Pro Setup..." -ForegroundColor Cyan

# 2. Setup Directories
$installDir = "$env:LOCALAPPDATA\VectorAI"
$exePath = "$installDir\vector_bridge.exe"
$csPath = "$installDir\bridge.cs"

if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir | Out-Null
}

# 3. CRITICAL: Stop existing process BEFORE compilation to unlock the file
Write-Host "Unlocking system files..." -ForegroundColor Gray
Stop-Process -Name "vector_bridge" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# 4. Create Bridge Source
Write-Host "Step 1: Deploying Security Core..." -ForegroundColor Yellow
$source = @"
using System;
using System.Net;
using System.Text;
using System.Management;
using System.Threading;

class VectorBridge {
    static void Main() {
        HttpListener listener = new HttpListener();
        int startPort = 5003;
        int endPort = 5050;
        int activePort = -1;
        for (int p = startPort; p <= endPort; p++) {
            try {
                listener = new HttpListener();
                listener.Prefixes.Add("http://127.0.0.1:" + p + "/");
                listener.Prefixes.Add("http://localhost:" + p + "/");
                listener.Start();
                activePort = p;
                break;
            } catch { listener.Close(); }
        }
        if (activePort == -1) return;
        while (true) {
            try {
                HttpListenerContext context = listener.GetContext();
                HttpListenerRequest request = context.Request;
                HttpListenerResponse response = context.Response;
                response.Headers.Add("Access-Control-Allow-Origin", "*");
                response.Headers.Add("Access-Control-Allow-Methods", "GET, OPTIONS");
                response.Headers.Add("Access-Control-Allow-Headers", "*");
                if (request.HttpMethod == "OPTIONS") {
                    response.StatusCode = 204;
                } else {
                    string uuid = "";
                    try {
                        ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT SerialNumber FROM Win32_BIOS");
                        foreach (ManagementObject obj in searcher.Get()) uuid = obj["SerialNumber"].ToString();
                    } catch { uuid = "WIN-ID-" + Guid.NewGuid().ToString().Substring(0,8); }
                    string json = "{\"success\":true,\"device_id\":\"" + uuid + "\"}";
                    byte[] buffer = Encoding.UTF8.GetBytes(json);
                    response.ContentType = "application/json";
                    response.ContentLength64 = buffer.Length;
                    response.OutputStream.Write(buffer, 0, buffer.Length);
                }
                response.Close();
            } catch { }
        }
    }
}
"@

$source | Out-File -FilePath $csPath -Encoding utf8

# 5. Compile
Write-Host "Step 2: Compiling Hyper-Bridge..." -ForegroundColor Yellow
$csc = (Get-ChildItem "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" -ErrorAction SilentlyContinue).FullName
if (!$csc) {
    $csc = (Get-ChildItem "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe" -ErrorAction SilentlyContinue).FullName
}

if (!$csc) {
    Show-Popup "ERROR: .NET Framework 4.5 not found. Please install it to continue." "Error"
    exit
}

# Run Compilation
$compileResult = Start-Process $csc -ArgumentList "/out:`"$exePath`" /target:winexe `"$csPath`" /reference:System.Management.dll" -Wait -NoNewWindow -PassThru

if ($compileResult.ExitCode -ne 0) {
    Show-Popup "CRITICAL: Compilation failed. Security software may be blocking the process." "Error"
    exit
}

# 6. Firewall & Start
Write-Host "Step 3: Configuring Firewall..." -ForegroundColor Yellow
netsh advfirewall firewall delete rule name="Vector Hyper-Bridge" | Out-Null
netsh advfirewall firewall add rule name="Vector Hyper-Bridge" dir=in action=allow protocol=TCP localport=5003-5050 | Out-Null

Write-Host "Step 4: Activating Stealth Mode..." -ForegroundColor Yellow
Start-Process $exePath

# 7. Verify
Start-Sleep -Seconds 2
if (Get-Process -Name "vector_bridge" -ErrorAction SilentlyContinue) {
    Show-Popup "✅ VECTOR IS ARMED!`n`n1. Reload your Chrome Extension.`n2. The login block is now removed." "Information"
} else {
    Show-Popup "❌ FAILED: The bridge was blocked by your Antivirus. Please add an exclusion for `"$installDir`"." "Warning"
}
