$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BuildCacheVolume = "suika-elika-buildozer-cache"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required to build the Android APK on Windows."
}

$DockerArguments = @(
    "run",
    "--rm",
    "--workdir",
    "/home/user/hostcwd",
    "--volume",
    "${BuildCacheVolume}:/home/user/.buildozer",
    "--volume",
    "${ProjectRoot}:/home/user/hostcwd",
    "kivy/buildozer:latest",
    "android",
    "debug"
)

& docker @DockerArguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$Apk = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot "dist\android") -Filter "*.apk" -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $Apk) {
    throw "Buildozer completed without producing an APK in dist/android."
}

Write-Output "Android APK: $($Apk.FullName)"
