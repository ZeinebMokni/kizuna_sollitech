$ErrorActionPreference = "Stop"

$ports = @(
    Get-CimInstance Win32_SerialPort -ErrorAction SilentlyContinue |
        Where-Object { $_.DeviceID } |
        ForEach-Object { $_.DeviceID }
)

if ($ports.Count -eq 0) {
    Write-Host "No serial COM port was detected." -ForegroundColor Red
    Write-Host "Connect the ESP32, install its USB-UART driver, then re-run:"
    Write-Host "  python -m platformio device list"
    exit 1
}

if ($ports.Count -gt 1) {
    Write-Host "Multiple COM ports were detected:" -ForegroundColor Yellow
    $ports | ForEach-Object { Write-Host "  $_" }
    Write-Host "Run explicitly:"
    Write-Host "  python -m platformio run --target upload --upload-port COMn"
    exit 2
}

$port = $ports[0]
Write-Host "Uploading to $port..."
python -m platformio run --target upload --upload-port $port
