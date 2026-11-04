param(
    [Parameter(Mandatory = $true)][string]$Ndk,
    [string]$Aar = ""
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Aar) { $Aar = Join-Path $repo 'app\libs\sherpa-onnx-1.12.20.aar' }
$expectedAar = '771fda6a4abf845a6f84f48e05e887fdf159671beb88cbc9aae327806511c1c8'
if ((Get-FileHash -LiteralPath $Aar -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedAar) {
    throw 'Pinned no-TTS AAR SHA-256 mismatch'
}
$revision = '5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f'
$base = Join-Path $repo '.local\native-runtime'
$source = Join-Path $base 'sherpa-onnx'
New-Item -ItemType Directory -Force -Path $base | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $source '.git'))) {
    & git clone --depth 1 --branch v1.12.20 https://github.com/k2-fsa/sherpa-onnx.git $source
    if ($LASTEXITCODE) { throw 'sherpa-onnx clone failed' }
}
if ((& git -C $source rev-parse HEAD).Trim() -ne $revision) { throw 'sherpa-onnx source revision mismatch' }
& python (Join-Path $PSScriptRoot 'patch_sherpa_no_tts_c_api.py') $source
if ($LASTEXITCODE) { throw 'no-TTS source patch failed' }

$gitRoot = Split-Path (Split-Path (Get-Command git).Source -Parent) -Parent
$sedDir = Join-Path $gitRoot 'usr\bin'
if (-not (Test-Path -LiteralPath (Join-Path $sedDir 'sed.exe'))) { throw 'Git for Windows sed.exe is required by upstream OpenFST CMake patch' }
$oldPath = $env:PATH
$env:PATH = "$sedDir;$oldPath"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($Aar)
try {
    foreach ($abi in @('arm64-v8a', 'x86_64')) {
        $short = if ($abi -eq 'arm64-v8a') { 'arm64' } else { 'x86_64' }
        $runtimeDir = Join-Path $base "onnx-$short"
        New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
        $entry = $archive.GetEntry("jni/$abi/libonnxruntime.so")
        if (-not $entry) { throw "Missing ONNX Runtime for $abi" }
        $runtimeLib = Join-Path $runtimeDir 'libonnxruntime.so'
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $runtimeLib, $true)
        $env:SHERPA_ONNXRUNTIME_LIB_DIR = $runtimeDir.Replace('\', '/')
        $env:SHERPA_ONNXRUNTIME_INCLUDE_DIR = (Join-Path $repo 'app\src\main\cpp\third_party\onnxruntime').Replace('\', '/')
        $build = Join-Path $base "build-$short"
        $args = @(
            '-S', $source, '-B', $build, '-G', 'Ninja', '-Wno-deprecated', '-Wno-dev',
            "-DCMAKE_TOOLCHAIN_FILE=$($Ndk.Replace('\', '/'))/build/cmake/android.toolchain.cmake",
            "-DANDROID_ABI=$abi", '-DANDROID_PLATFORM=android-26', '-DCMAKE_BUILD_TYPE=Release',
            '-DBUILD_SHARED_LIBS=ON', '-DSHERPA_ONNX_ENABLE_TTS=OFF',
            '-DSHERPA_ONNX_ENABLE_SPEAKER_DIARIZATION=ON', '-DSHERPA_ONNX_ENABLE_C_API=ON',
            '-DSHERPA_ONNX_ENABLE_JNI=OFF', '-DSHERPA_ONNX_ENABLE_BINARY=OFF',
            '-DSHERPA_ONNX_ENABLE_PORTAUDIO=OFF', '-DSHERPA_ONNX_ENABLE_TESTS=OFF',
            '-DSHERPA_ONNX_ENABLE_CHECK=OFF', '-DSHERPA_ONNX_LINK_LIBSTDCPP_STATICALLY=ON',
            '-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384'
        )
        & cmake @args
        if ($LASTEXITCODE) { throw "CMake configure failed for $abi" }
        & cmake --build $build --target sherpa-onnx-c-api --parallel 4
        if ($LASTEXITCODE) { throw "C++ build failed for $abi" }
        $output = Join-Path $base "probe-jni\$abi\libsherpa-onnx-c-api.so"
        New-Item -ItemType Directory -Force -Path (Split-Path $output -Parent) | Out-Null
        $strip = Join-Path $Ndk 'toolchains\llvm\prebuilt\windows-x86_64\bin\llvm-strip.exe'
        & $strip -o $output (Join-Path $build 'lib\libsherpa-onnx-c-api.so')
        if ($LASTEXITCODE) { throw "Strip failed for $abi" }
        $nm = Join-Path $Ndk 'toolchains\llvm\prebuilt\windows-x86_64\bin\llvm-nm.exe'
        $symbols = & $nm -D --defined-only $output
        if ($LASTEXITCODE -or ($symbols | Select-String 'SherpaOnnx.*Tts')) { throw "TTS export or symbol inspection failure for $abi" }
        if (-not ($symbols | Select-String 'SherpaOnnxCreateOfflineRecognizer')) { throw "ASR export missing for $abi" }
        $readelf = Join-Path $Ndk 'toolchains\llvm\prebuilt\windows-x86_64\bin\llvm-readelf.exe'
        $loads = & $readelf -l $output | Select-String 'LOAD'
        if ($LASTEXITCODE -or $loads.Count -lt 2 -or ($loads | Where-Object { $_.Line -notmatch '0x4000\s*$' })) {
            throw "16 KB ELF load alignment failed for $abi"
        }
        Write-Output "$abi $((Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash)"
    }
} finally {
    $archive.Dispose()
    $env:PATH = $oldPath
    Remove-Item Env:SHERPA_ONNXRUNTIME_LIB_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:SHERPA_ONNXRUNTIME_INCLUDE_DIR -ErrorAction SilentlyContinue
}
