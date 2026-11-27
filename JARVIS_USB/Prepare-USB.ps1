# JARVIS USB preparation - Windows PowerShell 5.1 and PowerShell 7+
# Save this file in the main JARVIS_USB folder, beside app.py and requirements.txt.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'Continue'

function Write-Stage([string]$Message) {
    Write-Host "`n[ JARVIS USB ] $Message" -ForegroundColor Cyan
}
function Get-Prop($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    $p = $Object.PSObject.Properties[$Name]
    if ($null -ne $p) { return $p.Value }
    return $null
}
function Test-ProjectRoot([string]$Folder) {
    if ([string]::IsNullOrWhiteSpace($Folder)) { return $false }
    if (-not (Test-Path -LiteralPath $Folder -PathType Container)) { return $false }
    return ((Test-Path -LiteralPath (Join-Path $Folder 'app.py') -PathType Leaf) -or
            ((Test-Path -LiteralPath (Join-Path $Folder 'core') -PathType Container) -and
             (Test-Path -LiteralPath (Join-Path $Folder 'requirements.txt') -PathType Leaf)))
}
function Find-ProjectRoot {
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) { $candidates += $PSScriptRoot }
    if (-not [string]::IsNullOrWhiteSpace($PSCommandPath)) { $candidates += (Split-Path -Parent $PSCommandPath) }
    try { $candidates += (Get-Location).ProviderPath } catch {}
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-ProjectRoot $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    throw "Project folder not found. Put this script in the main JARVIS_USB folder beside app.py, then run Setup-USB.bat."
}

$logPath = $null
$tempPath = $null
$failed = $false
try {
    Write-Host 'JARVIS USB PREPARATION' -ForegroundColor Cyan
    Write-Host 'This script will not format the drive or delete unrelated files.'
    Write-Stage 'Locating project folder…'
    $root = Find-ProjectRoot
    Write-Host "Project folder: $root" -ForegroundColor Green

    $logDir = Join-Path $root 'Logs'
    if (-not (Test-Path -LiteralPath $logDir -PathType Container)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $logPath = Join-Path $logDir ('usb-setup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
    Start-Transcript -Path $logPath -Force | Out-Null

    $modelsDir = Join-Path $root 'Models'
    if (-not (Test-Path -LiteralPath $modelsDir -PathType Container)) { New-Item -ItemType Directory -Path $modelsDir -Force | Out-Null }

    Write-Stage 'Checking system memory…'
    $modelName = 'qwen2.5-1.5b-instruct-q4_k_m.gguf'
    try {
        $sys = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
        $ram = [int64]$sys.TotalPhysicalMemory
        if ($ram -gt 0 -and $ram -lt 8GB) { $modelName = 'qwen2.5-1.5b-instruct-q2_k.gguf' }
        Write-Host ("Detected RAM: {0:N1} GB. Selected model: {1}" -f ($ram / 1GB), $modelName)
    } catch {
        Write-Warning 'Could not detect RAM. Selecting the Q4 model.'
    }

    $destination = Join-Path $modelsDir $modelName
    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        Write-Host "Model already exists; leaving it unchanged: $destination" -ForegroundColor Green
    } else {
        Write-Stage 'Checking USB free space and model download information…'
        $driveRoot = [IO.Path]::GetPathRoot($root)
        if ([string]::IsNullOrWhiteSpace($driveRoot)) { throw "Could not identify the drive containing $root" }
        $drive = [IO.DriveInfo]::new($driveRoot)
        if (-not $drive.IsReady) { throw "Drive is not ready: $driveRoot" }
        $free = [int64]$drive.AvailableFreeSpace
        Write-Host ("Available space on {0}: {1:N2} GB" -f $driveRoot, ($free / 1GB))

        try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
        $api = 'https://huggingface.co/api/models/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/main?recursive=false'
        Write-Host 'Contacting Hugging Face to verify the selected model size…'
        $listing = Invoke-RestMethod -Uri $api -Method Get -UseBasicParsing -TimeoutSec 60
        $entry = $null
        foreach ($item in $listing) {
            if ((Get-Prop $item 'path') -eq $modelName) { $entry = $item; break }
        }
        $sizeRaw = Get-Prop $entry 'size'
        if ($null -eq $sizeRaw) { throw "The model file '$modelName' was not found in the repository listing. No download was started." }
        $expected = [int64]$sizeRaw
        if ($expected -le 0) { throw 'The model listing returned an invalid file size. No download was started.' }
        $reserve = 3GB
        if ($free -lt ($expected + $reserve)) {
            throw ("Not enough free USB space. Model: {0:N2} GB; free: {1:N2} GB; required reserve: 3 GB. Nothing was downloaded." -f ($expected/1GB), ($free/1GB))
        }
        Write-Host ("Model size: {0:N2} GB" -f ($expected / 1GB))
        Write-Host 'Starting download. Keep this window open; progress should appear below.' -ForegroundColor Yellow
        $url = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/$modelName`?download=true"
        $tempPath = Join-Path $modelsDir ($modelName + '.partial-download')
        if (Test-Path -LiteralPath $tempPath) { Remove-Item -LiteralPath $tempPath -Force }
        Invoke-WebRequest -Uri $url -OutFile $tempPath -UseBasicParsing -TimeoutSec 0
        $actual = [int64](Get-Item -LiteralPath $tempPath).Length
        if ($actual -ne $expected) { throw "Download verification failed: expected $expected bytes but received $actual bytes. The partial file will be removed." }
        if (Test-Path -LiteralPath $destination) { throw 'The destination file appeared during download; it was not overwritten.' }
        Move-Item -LiteralPath $tempPath -Destination $destination
        $tempPath = $null
        Write-Host 'Model download completed and file size verified.' -ForegroundColor Green
    }

    Write-Stage 'Preparation checks complete.'
    Write-Host "Project: $root"
    Write-Host 'Next: put Piper voice files in Voice\Piper and the Wikipedia ZIM archive in Knowledge\Wikipedia.'
    Write-Host 'No drive formatting or unrelated-file deletion was performed.' -ForegroundColor Green
} catch {
    $failed = $true
    Write-Host "`nJARVIS USB preparation failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    if ($_.InvocationInfo -and $_.InvocationInfo.PositionMessage) { Write-Host $_.InvocationInfo.PositionMessage -ForegroundColor DarkGray }
    if ($tempPath -and (Test-Path -LiteralPath $tempPath -PathType Leaf)) {
        try { Remove-Item -LiteralPath $tempPath -Force; Write-Host 'Removed incomplete temporary download.' -ForegroundColor Yellow } catch { Write-Warning 'Could not remove partial download.' }
    }
} finally {
    try { Stop-Transcript | Out-Null } catch {}
}

if ($failed) { Write-Host "`nA diagnostic log, if created, is in the JARVIS_USB\Logs folder." -ForegroundColor Yellow }
Write-Host "`nPress Enter to close this window…" -ForegroundColor Gray
try { [void](Read-Host) } catch {}
if ($failed) { exit 1 } else { exit 0 }
