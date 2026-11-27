param(
    [ValidateSet('Intelligent','Balanced','Speed','All')]
    [string]$Mode = 'Balanced'
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelDir = Join-Path $root 'Models'
New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
$catalog = @{
    Intelligent = @{ File='Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf'; Url='https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf?download=true'; Minimum=4500000000 }
    Balanced = @{ File='gemma-3-4b-it-Q4_K_M.gguf'; Url='https://huggingface.co/tensorblock/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q4_K_M.gguf?download=true'; Minimum=2200000000 }
    Speed = @{ File='SmolLM2-1.7B-Instruct-Q4_K_M.gguf'; Url='https://huggingface.co/bartowski/SmolLM2-1.7B-Instruct-GGUF/resolve/main/SmolLM2-1.7B-Instruct-Q4_K_M.gguf?download=true'; Minimum=850000000 }
}
$selected = if ($Mode -eq 'All') { @('Intelligent','Balanced','Speed') } else { @($Mode) }
foreach ($name in $selected) {
    $item = $catalog[$name]
    $target = Join-Path $modelDir $item.File
    $temp = Join-Path $modelDir ($item.File + '.download')
    Write-Host "Downloading $name model: $($item.File)" -ForegroundColor Cyan
    if (Test-Path -LiteralPath $target) {
        if ((Get-Item -LiteralPath $target).Length -ge $item.Minimum) {
            Write-Host "Existing model file passes approximate size check: $target" -ForegroundColor Yellow
            continue
        }
        $backup = $target + '.incomplete-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
        Move-Item -LiteralPath $target -Destination $backup
        Write-Host "Preserved incomplete file as $backup" -ForegroundColor Yellow
    }
    try {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
        Invoke-WebRequest -Uri $item.Url -OutFile $temp
        $size = (Get-Item -LiteralPath $temp).Length
        if ($size -lt $item.Minimum) { throw "Downloaded file too small ($size bytes); likely incomplete or an error response." }
        Move-Item -LiteralPath $temp -Destination $target
        Write-Host "$name model downloaded. Approximate size check passed; SHA-256 has not been checked." -ForegroundColor Green
    } catch {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
        throw
    }
}
Write-Host 'Model download operation finished. Restart JARVIS and select the required mode.' -ForegroundColor Green
