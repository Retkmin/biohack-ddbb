# 🐳 SAM Infrastructure — Docker Installation Script
# Este script ayuda a automatizar la instalación de Docker Desktop usando winget.

Write-Host "--- SAM Infrastructure Setup ---" -ForegroundColor Cyan

# 1. Verificar WSL2 (Prerrequisito)
Write-Host "[1/3] Verificando WSL2..." -ForegroundColor Yellow
$wslStatus = wsl --status
if ($null -eq $wslStatus) {
    Write-Host "❌ WSL no detectado. Es necesario habilitar la plataforma de máquina virtual en Windows." -ForegroundColor Red
    Write-Host "Ejecuta: 'wsl --install' en una terminal como administrador y reinicia." -ForegroundColor White
    exit
}
Write-Host "✅ WSL detectado." -ForegroundColor Green

# 2. Instalar Docker Desktop vía winget
Write-Host "[2/3] Buscando Docker Desktop en winget..." -ForegroundColor Yellow
$dockerCheck = winget list --id Docker.DockerDesktop -e
if ($dockerCheck -match "Docker Desktop") {
    Write-Host "✅ Docker Desktop ya parece estar instalado." -ForegroundColor Green
} else {
    Write-Host "🚀 Iniciando instalación de Docker Desktop..." -ForegroundColor Cyan
    Write-Host "⚠️ Se abrirá una ventana de confirmación de Windows (UAC). Acéptala." -ForegroundColor White
    winget install Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Instalación completada con éxito." -ForegroundColor Green
        Write-Host "⚠️ REINICIO REQUERIDO: Debes reiniciar tu PC para que Docker se inicialice correctamente." -ForegroundColor Red
    } else {
        Write-Host "❌ Error durante la instalación. Revisa si winget está actualizado." -ForegroundColor Red
    }
}

# 3. Finalización
Write-Host "[3/3] Configuración finalizada." -ForegroundColor Cyan
Write-Host "Una vez instalado y reiniciado, podrás levantar el sistema con:" -ForegroundColor White
Write-Host "  cd repos/biohack-ddbb" -ForegroundColor Gray
Write-Host "  docker-compose -f docker-compose.db.yml up -d" -ForegroundColor Gray
