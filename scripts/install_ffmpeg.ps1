Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$TargetDir = Join-Path $RepoRoot "tools\ffmpeg"
$FfmpegExe = Join-Path $TargetDir "ffmpeg.exe"
$FfprobeExe = Join-Path $TargetDir "ffprobe.exe"

# Source: gyan.dev Windows release essentials build, linked from https://ffmpeg.org/download.html
$ArchiveUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("zdbatcher-ffmpeg-" + [System.Guid]::NewGuid().ToString("N"))
$DownloadFile = Join-Path $TempDir "ffmpeg-release-essentials.zip"
$PartialDownloadFile = "$DownloadFile.download"

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "[ZDBatcher] $Message"
}

function Remove-IfExists {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force -Recurse
    }
}

function Download-Archive {
    Write-Step "Downloading FFmpeg release essentials archive..."
    Write-Step "Source: $ArchiveUrl"

    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue

    if ($curl) {
        Write-Step "Using curl.exe with retries."
        & $curl.Source `
            --location `
            --fail `
            --retry 3 `
            --retry-delay 2 `
            --connect-timeout 20 `
            --output $PartialDownloadFile `
            $ArchiveUrl

        if ($LASTEXITCODE -ne 0) {
            throw "curl.exe failed with exit code $LASTEXITCODE."
        }
    }
    else {
        Write-Step "curl.exe was not found. Falling back to Invoke-WebRequest."
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $ArchiveUrl -OutFile $PartialDownloadFile -UseBasicParsing
    }

    if (-not (Test-Path -LiteralPath $PartialDownloadFile)) {
        throw "Download did not create the expected archive file."
    }

    Move-Item -LiteralPath $PartialDownloadFile -Destination $DownloadFile -Force
}

function Extract-Executable {
    param(
        [Parameter(Mandatory = $true)][System.IO.Compression.ZipArchive]$Archive,
        [Parameter(Mandatory = $true)][string]$ExecutableName,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $entry = $Archive.Entries |
        Where-Object {
            $entryPath = $_.FullName -replace "\\", "/"
            $entryPath -match "/bin/$([regex]::Escape($ExecutableName))$"
        } |
        Select-Object -First 1

    if (-not $entry) {
        throw "Could not find $ExecutableName in the downloaded archive."
    }

    $tempDestination = Join-Path $TempDir $ExecutableName
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $tempDestination, $true)
    Move-Item -LiteralPath $tempDestination -Destination $Destination -Force
}

try {
    if ((Test-Path -LiteralPath $FfmpegExe) -and (Test-Path -LiteralPath $FfprobeExe)) {
        Write-Step "FFmpeg is already installed locally."
        Write-Step $FfmpegExe
        Write-Step $FfprobeExe
        exit 0
    }

    Write-Step "Preparing local FFmpeg folder."
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

    Download-Archive

    Write-Step "Extracting ffmpeg.exe and ffprobe.exe only."
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($DownloadFile)

    try {
        Extract-Executable -Archive $archive -ExecutableName "ffmpeg.exe" -Destination $FfmpegExe
        Extract-Executable -Archive $archive -ExecutableName "ffprobe.exe" -Destination $FfprobeExe
    }
    finally {
        if ($archive) {
            $archive.Dispose()
        }
    }

    if (-not (Test-Path -LiteralPath $FfmpegExe)) {
        throw "ffmpeg.exe was not installed."
    }

    if (-not (Test-Path -LiteralPath $FfprobeExe)) {
        throw "ffprobe.exe was not installed."
    }

    Write-Step "FFmpeg installed successfully."
    Write-Step $FfmpegExe
    Write-Step $FfprobeExe
}
catch {
    Write-Error "FFmpeg installation failed. $($_.Exception.Message)"
    Remove-IfExists -Path $PartialDownloadFile
    exit 1
}
finally {
    Remove-IfExists -Path $TempDir
}
