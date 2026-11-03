param([switch]$SampleOnly, [switch]$Repair)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if ([IO.Path]::GetPathRoot($projectRoot) -ne 'D:\') {
    throw 'Serena generation must stay on D: as requested by the user.'
}
Set-Location -LiteralPath $projectRoot
$cacheRoot = Join-Path $projectRoot '.speech-cache'
$cacheDirs = @{
    TEMP='tmp'; TMP='tmp'; TMPDIR='tmp'; PIP_CACHE_DIR='pip'
    HF_HOME='huggingface'; TORCH_HOME='torch'; XDG_CACHE_HOME='xdg'
    NUMBA_CACHE_DIR='numba'; MPLCONFIGDIR='matplotlib'; GRADIO_TEMP_DIR='gradio'
    CUDA_CACHE_PATH='cuda'; TORCH_EXTENSIONS_DIR='extensions'; TRITON_CACHE_DIR='triton'
    TORCHINDUCTOR_CACHE_DIR='inductor'; PYTORCH_KERNEL_CACHE_PATH='kernels'
}
foreach ($item in $cacheDirs.GetEnumerator()) {
    $directory = Join-Path $cacheRoot $item.Value
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    [Environment]::SetEnvironmentVariable($item.Key, $directory, 'Process')
}
$env:HF_HUB_DISABLE_XET = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$pythonPath = Join-Path $projectRoot '.tts-venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & "$projectRoot/.venv/Scripts/python.exe" -m venv "$projectRoot/.tts-venv"
    if ($LASTEXITCODE -ne 0) { throw 'Could not create speech environment' }
}
$torchWheel = Join-Path $cacheRoot 'wheels/torch-2.6.0+cu124-cp312-cp312-win_amd64.whl'
$audioWheel = Join-Path $cacheRoot 'wheels/torchaudio-2.6.0+cu124-cp312-cp312-win_amd64.whl'
$environmentReady = $false
if (-not $Repair) {
    & $pythonPath -c "import torch, torchaudio, soundfile; from qwen_tts import Qwen3TTSModel; assert torch.__version__ == '2.6.0+cu124'; assert torch.cuda.is_available()"
    if ($LASTEXITCODE -eq 0) {
        & $pythonPath -m pip check
        $environmentReady = ($LASTEXITCODE -eq 0)
    }
}
if ($environmentReady) {
    Write-Host 'Speech environment is ready; reusing local installation.'
} elseif ((Test-Path -LiteralPath $torchWheel) -and (Test-Path -LiteralPath $audioWheel)) {
    # Force reinstall repairs an interrupted installation; wheels and pip cache stay on D:.
    & $pythonPath -m pip install --force-reinstall $torchWheel $audioWheel -r "$projectRoot/jiandong_ai/scripts/requirements-serena.txt" --index-url https://pypi.org/simple --timeout 30 --retries 1 --progress-bar off
    if ($LASTEXITCODE -ne 0) { throw 'Could not restore local speech environment' }
} else {
    & $pythonPath -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
    if ($LASTEXITCODE -ne 0) { throw 'Could not install CUDA dependencies' }
    & $pythonPath -m pip install -r "$projectRoot/jiandong_ai/scripts/requirements-serena.txt"
    if ($LASTEXITCODE -ne 0) { throw 'Could not install Qwen TTS' }
}
if ($SampleOnly) {
    & $pythonPath -u -m jiandong_ai.scripts.generate_serena_prompts --limit 3
} else {
    & $pythonPath -u -m jiandong_ai.scripts.generate_serena_prompts
}
if ($LASTEXITCODE -ne 0) { throw 'Serena generation failed' }
