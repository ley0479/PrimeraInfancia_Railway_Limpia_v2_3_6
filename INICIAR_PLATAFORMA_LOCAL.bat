@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

title Primera Infancia - Inicio local unificado

echo ============================================================
echo   PRIMERA INFANCIA v2.4.2 - INICIO LOCAL UNIFICADO
echo ============================================================
echo.

REM Puede ejecutarse desde la raiz del proyecto o desde scripts_windows.
set "ROOT=%~dp0"
if not exist "%ROOT%backend\" if exist "%~dp0..\backend\" set "ROOT=%~dp0..\"
for %%I in ("%ROOT%.") do set "ROOT=%%~fI"
set "ROOT=%ROOT%\"

set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"
set "DATA_DIR=%ROOT%data"
set "RUNTIME_DIR=%ROOT%.runtime_windows"
set "BACKEND_PORT=5000"
set "LOCAL_URL=http://127.0.0.1:%BACKEND_PORT%"
set "LOCAL_FRONTEND=%LOCAL_URL%/frontend/index.html"

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>&1
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%" >nul 2>&1

if not exist "%BACKEND_DIR%\app.py" (
  echo [ERROR] No se encontro backend\app.py en:
  echo %BACKEND_DIR%
  echo.
  echo Coloca este .bat en la raiz del proyecto, al mismo nivel de backend y frontend.
  if not defined PI_NO_PAUSE pause
  exit /b 1
)

if not exist "%FRONTEND_DIR%\index.html" (
  echo [ERROR] No se encontro frontend\index.html en:
  echo %FRONTEND_DIR%
  echo.
  if not defined PI_NO_PAUSE pause
  exit /b 1
)

echo Proyecto detectado:
echo %ROOT%
echo.

REM Huella estable de esta copia. Evita publicar por túnel otro backend viejo
REM que esté usando el mismo puerto 5000 desde una carpeta diferente.
set "PI_PROJECT_ROOT_FOR_HASH=%ROOT%"
set "PROJECT_INSTANCE_ID="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$root=[IO.Path]::GetFullPath($env:PI_PROJECT_ROOT_FOR_HASH).TrimEnd([char[]]'\/').ToLowerInvariant(); $sha=[Security.Cryptography.SHA256]::Create(); try { $bytes=[Text.Encoding]::UTF8.GetBytes($root); ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').Substring(0,16).ToLowerInvariant() } finally { $sha.Dispose() }" 2^>nul`) do set "PROJECT_INSTANCE_ID=%%I"
set "PI_PROJECT_ROOT_FOR_HASH="
if not defined PROJECT_INSTANCE_ID (
  echo [ERROR] No se pudo calcular la huella de esta copia del proyecto.
  if not defined PI_NO_PAUSE pause
  exit /b 1
)
>"%RUNTIME_DIR%\project_instance_id.txt" echo %PROJECT_INSTANCE_ID%
echo Instancia del proyecto: %PROJECT_INSTANCE_ID%
echo.

for /f %%L in ('powershell -NoProfile -Command "$p=(Resolve-Path '%ROOT%').Path; $p.Length" 2^>nul') do set "ROOT_LEN=%%L"
if defined ROOT_LEN (
  if !ROOT_LEN! GTR 80 (
    echo [AVISO] La ruta del proyecto es larga ^(!ROOT_LEN! caracteres^).
    echo         Si pip falla con lxml o rutas largas, mueve el proyecto a C:\PI\.
    echo.
  )
)

echo [1/7] Detectando Python recomendado...
set "PY_CMD="
set "PY_LABEL="

py -3.12 --version >nul 2>&1
if not errorlevel 1 (
  set "PY_CMD=py -3.12"
  set "PY_LABEL=Python 3.12"
)

if not defined PY_CMD (
  py -3.11 --version >nul 2>&1
  if not errorlevel 1 (
    set "PY_CMD=py -3.11"
    set "PY_LABEL=Python 3.11"
  )
)

if not defined PY_CMD (
  py -3.10 --version >nul 2>&1
  if not errorlevel 1 (
    set "PY_CMD=py -3.10"
    set "PY_LABEL=Python 3.10"
  )
)

if not defined PY_CMD (
  python --version >"%RUNTIME_DIR%\python_version_detectada.txt" 2>&1
  if not errorlevel 1 (
    set "PY_CMD=python"
    set "PY_LABEL=python disponible en PATH"
  )
)

if not defined PY_CMD (
  echo [ERROR] No se encontro Python.
  echo Instala Python 3.11 o 3.12 y vuelve a ejecutar este script.
  if not defined PI_NO_PAUSE pause
  exit /b 1
)

%PY_CMD% --version >"%RUNTIME_DIR%\python_version_detectada.txt" 2>&1
set /p PY_VERSION_TEXT=<"%RUNTIME_DIR%\python_version_detectada.txt"
echo Usando: %PY_LABEL% - %PY_VERSION_TEXT%
echo %PY_VERSION_TEXT% | findstr /C:"3.13" >nul
if not errorlevel 1 if not "%PI_ALLOW_PY313%"=="1" (
  echo.
  echo [ERROR] Se detecto Python 3.13. Para esta plataforma usa Python 3.11 o 3.12.
  echo         Esto evita fallos de instalacion con dependencias como lxml.
  echo         Si entiendes el riesgo, ejecuta con PI_ALLOW_PY313=1.
  if not defined PI_NO_PAUSE pause
  exit /b 1
)

cd /d "%BACKEND_DIR%"

echo.
echo [2/7] Preparando entorno virtual...
set "RECREATE_VENV=0"
if exist ".venv\Scripts\python.exe" (
  for /f "tokens=2" %%V in ('".venv\Scripts\python.exe" --version 2^>^&1') do set "VENV_VERSION=%%V"
  echo Entorno virtual existente: Python !VENV_VERSION!
  echo !VENV_VERSION! | findstr /B /C:"3.13" >nul
  if not errorlevel 1 set "RECREATE_VENV=1"
) else (
  set "RECREATE_VENV=1"
)

if "%RECREATE_VENV%"=="1" (
  if exist ".venv" (
    echo Eliminando entorno virtual anterior...
    rmdir /S /Q ".venv"
  )
  echo Creando entorno virtual...
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo.
    echo [ERROR] No se pudo crear el entorno virtual.
    echo Recomendado: instalar Python 3.11 o 3.12 y ubicar el proyecto en C:\PI\.
    if not defined PI_NO_PAUSE pause
    exit /b 1
  )
) else (
  echo Entorno virtual valido detectado.
)

set "VENV_PY=%BACKEND_DIR%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [ERROR] No existe el Python del entorno virtual:
  echo %VENV_PY%
  if not defined PI_NO_PAUSE pause
  exit /b 1
)

set "REQ_FILE="
if exist "%BACKEND_DIR%\requirements-production.txt" set "REQ_FILE=%BACKEND_DIR%\requirements-production.txt"
if not defined REQ_FILE if exist "%BACKEND_DIR%\requirements.txt" set "REQ_FILE=%BACKEND_DIR%\requirements.txt"

if defined REQ_FILE (
  echo.
  echo [3/7] Instalando/verificando dependencias...
  "%VENV_PY%" -m pip install --upgrade pip setuptools wheel
  if errorlevel 1 goto :pip_error
  if not exist "%BACKEND_DIR%\.venv\.deps_ok" (
    "%VENV_PY%" -m pip install --prefer-binary --no-cache-dir -r "%REQ_FILE%"
    if errorlevel 1 goto :pip_error
    echo Dependencias instaladas el %DATE% %TIME% > "%BACKEND_DIR%\.venv\.deps_ok"
  ) else (
    echo Dependencias ya instaladas. Para reinstalar, borra backend\.venv\.deps_ok.
  )
) else (
  echo [AVISO] No se encontro requirements-production.txt ni requirements.txt.
)

if not exist "%DATA_DIR%\uploads" mkdir "%DATA_DIR%\uploads" >nul 2>&1
if not exist "%DATA_DIR%\archivos_actualizados" mkdir "%DATA_DIR%\archivos_actualizados" >nul 2>&1
if not exist "%DATA_DIR%\templates_originales" mkdir "%DATA_DIR%\templates_originales" >nul 2>&1
if not exist "%DATA_DIR%\logs" mkdir "%DATA_DIR%\logs" >nul 2>&1
if not exist "%DATA_DIR%\backups" mkdir "%DATA_DIR%\backups" >nul 2>&1
if not exist "%DATA_DIR%\storage" mkdir "%DATA_DIR%\storage" >nul 2>&1
if not exist "%DATA_DIR%\documentos_institucionales" mkdir "%DATA_DIR%\documentos_institucionales" >nul 2>&1
if not exist "%DATA_DIR%\cuentas_cobro_plantillas" mkdir "%DATA_DIR%\cuentas_cobro_plantillas" >nul 2>&1

set "DATA_DIR_URL=%DATA_DIR:\=/%"
if "%PI_TUNNEL_MODE%"=="1" (
  set "SERVER_MODE=TUNEL_ONLINE"
  set "PUBLIC_TUNNEL_MODE=true"
  set "EXPECTED_TUNNEL_MODE=true"
) else (
  set "SERVER_MODE=LOCAL"
  set "PUBLIC_TUNNEL_MODE=false"
  set "EXPECTED_TUNNEL_MODE=false"
)

REM Variables locales controladas. No modifican .env ni la base original.
set "APP_ENV=development"
set "FLASK_ENV=development"
set "APP_VERSION=2.4.2-tunel-login-logging-corregido"
set "FLASK_HOST=127.0.0.1"
set "FLASK_PORT=%BACKEND_PORT%"
set "PORT=%BACKEND_PORT%"
set "FRONTEND_PORT=5000"
set "DATA_DIR=%DATA_DIR%"
set "DATABASE_PATH=%DATA_DIR%\database.sqlite3"
set "DATABASE_URL=sqlite:///%DATA_DIR_URL%/database.sqlite3"
set "UPLOAD_FOLDER=%DATA_DIR%\uploads"
set "OUTPUT_FOLDER=%DATA_DIR%\archivos_actualizados"
set "TEMPLATES_FOLDER=%DATA_DIR%\templates_originales"
set "LOG_FOLDER=%DATA_DIR%\logs"
set "BACKUPS_FOLDER=%DATA_DIR%\backups"
set "LOCAL_STORAGE_PATH=%DATA_DIR%\storage"
set "DOCUMENTOS_FOLDER=%DATA_DIR%\documentos_institucionales"
set "CUENTAS_COBRO_FOLDER=%DATA_DIR%\cuentas_cobro_plantillas"
set "FRONTEND_ORIGIN=%LOCAL_URL%"
set "PUBLIC_APP_URL=%LOCAL_URL%"
set "FORCE_HTTPS=false"
set "SESSION_COOKIE_SAMESITE=Lax"
if "%PI_TUNNEL_MODE%"=="1" (
  REM Frontend y API usan el mismo dominio HTTPS; no se abre CORS a terceros.
  set "ALLOWED_ORIGINS="
  set "SESSION_COOKIE_SECURE=true"
  set "TRUSTED_PROXY_COUNT=1"
) else (
  set "ALLOWED_ORIGINS=http://127.0.0.1:5000,http://localhost:5000"
  set "SESSION_COOKIE_SECURE=false"
  set "TRUSTED_PROXY_COUNT=0"
)
set "SINGLE_TENANT_MODE=false"
set "ALLOW_EXPERIMENTAL_MULTI_TENANT=true"
set "MULTI_TENANT_STRICT=true"
set "TENANT_STORAGE_ISOLATION=true"
set "MULTI_TENANT_SCHEMA_VERSION=3"
set "ALLOW_LEGACY_QUERY_TOKENS=false"
set "ALLOW_PASSWORD_RESET_TOKEN_RESPONSE=false"
if "%PI_TUNNEL_MODE%"=="1" (
  set "ALLOW_LOCAL_RECOVERY_CODE=false"
) else (
  set "ALLOW_LOCAL_RECOVERY_CODE=true"
)

REM Secretos locales persistentes y aleatorios. Se guardan fuera de Git.
set "LOCAL_SECRET_FILE=%RUNTIME_DIR%\local_secret_key.txt"
set "LOCAL_JWT_SECRET_FILE=%RUNTIME_DIR%\local_jwt_secret_key.txt"
if not exist "%LOCAL_SECRET_FILE%" (
  "%VENV_PY%" -c "import secrets; print(secrets.token_urlsafe(64))" > "%LOCAL_SECRET_FILE%"
)
if not exist "%LOCAL_JWT_SECRET_FILE%" (
  "%VENV_PY%" -c "import secrets; print(secrets.token_urlsafe(64))" > "%LOCAL_JWT_SECRET_FILE%"
)
set "SECRET_KEY="
set "JWT_SECRET_KEY="
set /p SECRET_KEY=<"%LOCAL_SECRET_FILE%"
set /p JWT_SECRET_KEY=<"%LOCAL_JWT_SECRET_FILE%"
if not defined SECRET_KEY (
  echo [ERROR] No se pudo generar SECRET_KEY local.
  if not defined PI_NO_PAUSE pause
  exit /b 1
)
if not defined JWT_SECRET_KEY (
  echo [ERROR] No se pudo generar JWT_SECRET_KEY local.
  if not defined PI_NO_PAUSE pause
  exit /b 1
)
if "%SECRET_KEY%"=="%JWT_SECRET_KEY%" (
  del /Q "%LOCAL_JWT_SECRET_FILE%" >nul 2>&1
  "%VENV_PY%" -c "import secrets; print(secrets.token_urlsafe(64))" > "%LOCAL_JWT_SECRET_FILE%"
  set "JWT_SECRET_KEY="
  set /p JWT_SECRET_KEY=<"%LOCAL_JWT_SECRET_FILE%"
)

REM El administrador solo se crea cuando data\database.sqlite3 no existe.
set "INITIAL_ADMIN_USERNAME=admin.local"
set "INITIAL_ADMIN_EMAIL=admin.local@primera-infancia.local"
set "INITIAL_ADMIN_NAME=Administrador Local"
set "INITIAL_ADMIN_FORCE_PASSWORD_CHANGE=true"
set "INITIAL_FOUNDATION_NAME=Entorno local de pruebas"
set "NEW_LOCAL_DATABASE=0"
if not exist "%DATABASE_PATH%" set "NEW_LOCAL_DATABASE=1"
set "BOOTSTRAP_PASS_FILE=%RUNTIME_DIR%\_bootstrap_password.tmp"
"%VENV_PY%" -c "import secrets,string; r=secrets.SystemRandom(); a=string.ascii_letters+string.digits+'@#_-'; p=[r.choice(string.ascii_uppercase),r.choice(string.ascii_lowercase),r.choice(string.digits),r.choice('@#_-')]+[r.choice(a) for _ in range(24)]; r.shuffle(p); print(''.join(p))" > "%BOOTSTRAP_PASS_FILE%"
set "INITIAL_ADMIN_PASSWORD="
set /p INITIAL_ADMIN_PASSWORD=<"%BOOTSTRAP_PASS_FILE%"
if not defined INITIAL_ADMIN_PASSWORD (
  echo [ERROR] No se pudo generar la contraseña inicial local.
  if not defined PI_NO_PAUSE pause
  exit /b 1
)
set "LOCAL_CREDENTIALS_FILE=%RUNTIME_DIR%\CREDENCIALES_INICIALES_LOCAL.txt"
if "%NEW_LOCAL_DATABASE%"=="1" (
  (
    echo PRIMERA INFANCIA - CREDENCIALES INICIALES LOCALES
    echo =================================================
    echo Usuario: %INITIAL_ADMIN_USERNAME%
    echo Correo:  %INITIAL_ADMIN_EMAIL%
    echo Clave:   %INITIAL_ADMIN_PASSWORD%
    echo.
    echo Cambia esta clave en el primer ingreso y elimina este archivo.
    echo No reutilices estas credenciales en Railway ni en un tunel compartido.
  ) > "%LOCAL_CREDENTIALS_FILE%"
)
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo.
echo [4/7] Inicializando datos locales si hace falta...
"%VENV_PY%" init_hosting.py
if errorlevel 1 (
  echo.
  echo [ERROR] Fallo la inicializacion local.
  echo Revisa la ventana anterior y data\logs. backend\logs no es la carpeta operativa.
  if not defined PI_NO_PAUSE pause
  exit /b 1
)

echo.
echo [5/7] Verificando puerto %BACKEND_PORT%...
set "BACKEND_BUSY=0"
for /f "tokens=5" %%A in ('netstat -ano ^| findstr /R /C:":%BACKEND_PORT% .*LISTENING"') do (
  set "BACKEND_BUSY=1"
  set "BACKEND_PID=%%A"
)

if "%BACKEND_BUSY%"=="1" (
  powershell -NoProfile -Command "$ErrorActionPreference='Stop'; try { $r=Invoke-RestMethod -Uri '%LOCAL_URL%/api/health' -TimeoutSec 3; if ([string]$r.project_instance_id -eq '%PROJECT_INSTANCE_ID%' -and [string]$r.public_tunnel_mode -eq '%EXPECTED_TUNNEL_MODE%') { exit 0 }; if ([string]$r.status -eq 'ok') { exit 2 }; exit 1 } catch { exit 1 }" >nul 2>&1
  set "HEALTH_RESULT=!ERRORLEVEL!"
  if "!HEALTH_RESULT!"=="0" (
    echo Esta misma copia de la plataforma ya esta corriendo en %LOCAL_URL%.
    goto :open_browser
  )
  if "!HEALTH_RESULT!"=="2" (
    echo [AVISO] El puerto %BACKEND_PORT% pertenece a otra copia o a otro modo de Primera Infancia.
    echo         PID: !BACKEND_PID!
    echo         Copia solicitada: %PROJECT_INSTANCE_ID% - modo tunel=%EXPECTED_TUNNEL_MODE%
    echo         Debe cerrarse para no publicar una base o unas credenciales equivocadas.
  ) else (
    echo [AVISO] El puerto %BACKEND_PORT% esta ocupado por PID !BACKEND_PID! y no responde como esta copia.
  )
  choice /C SN /N /M "Deseas cerrar ese proceso y arrancar esta copia? [S/N]: "
  if errorlevel 2 (
    echo Operacion cancelada.
    if not defined PI_NO_PAUSE pause
    exit /b 1
  )
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr /R /C:":%BACKEND_PORT% .*LISTENING"') do taskkill /PID %%A /F >nul 2>&1
  timeout /t 2 /nobreak >nul
)

echo.
echo [6/7] Creando comando temporal de backend...
set "RUN_BACKEND_CMD=%RUNTIME_DIR%\_run_backend_unificado.cmd"
(
  echo @echo off
  echo chcp 65001 ^>nul
  echo title Primera Infancia - Backend + Frontend unificado
  echo cd /d "%BACKEND_DIR%"
  echo set "APP_ENV=%APP_ENV%"
  echo set "FLASK_ENV=%FLASK_ENV%"
  echo set "APP_VERSION=%APP_VERSION%"
  echo set "SERVER_MODE=%SERVER_MODE%"
  echo set "PUBLIC_TUNNEL_MODE=%PUBLIC_TUNNEL_MODE%"
  echo set "PROJECT_INSTANCE_ID=%PROJECT_INSTANCE_ID%"
  echo set "FLASK_HOST=%FLASK_HOST%"
  echo set "FLASK_PORT=%FLASK_PORT%"
  echo set "PORT=%PORT%"
  echo set "FRONTEND_PORT=%FRONTEND_PORT%"
  echo set "DATA_DIR=%DATA_DIR%"
  echo set "DATABASE_PATH=%DATABASE_PATH%"
  echo set "DATABASE_URL=%DATABASE_URL%"
  echo set "UPLOAD_FOLDER=%UPLOAD_FOLDER%"
  echo set "OUTPUT_FOLDER=%OUTPUT_FOLDER%"
  echo set "TEMPLATES_FOLDER=%TEMPLATES_FOLDER%"
  echo set "LOG_FOLDER=%LOG_FOLDER%"
  echo set "BACKUPS_FOLDER=%BACKUPS_FOLDER%"
  echo set "LOCAL_STORAGE_PATH=%LOCAL_STORAGE_PATH%"
  echo set "DOCUMENTOS_FOLDER=%DOCUMENTOS_FOLDER%"
  echo set "CUENTAS_COBRO_FOLDER=%CUENTAS_COBRO_FOLDER%"
  echo set "FRONTEND_ORIGIN=%FRONTEND_ORIGIN%"
  echo set "PUBLIC_APP_URL=%PUBLIC_APP_URL%"
  echo set "ALLOWED_ORIGINS=%ALLOWED_ORIGINS%"
  echo set "FORCE_HTTPS=%FORCE_HTTPS%"
  echo set "SESSION_COOKIE_SECURE=%SESSION_COOKIE_SECURE%"
  echo set "SESSION_COOKIE_SAMESITE=%SESSION_COOKIE_SAMESITE%"
  echo set "TRUSTED_PROXY_COUNT=%TRUSTED_PROXY_COUNT%"
  echo set "SINGLE_TENANT_MODE=%SINGLE_TENANT_MODE%"
  echo set "ALLOW_EXPERIMENTAL_MULTI_TENANT=%ALLOW_EXPERIMENTAL_MULTI_TENANT%"
  echo set "MULTI_TENANT_STRICT=%MULTI_TENANT_STRICT%"
  echo set "TENANT_STORAGE_ISOLATION=%TENANT_STORAGE_ISOLATION%"
  echo set "MULTI_TENANT_SCHEMA_VERSION=%MULTI_TENANT_SCHEMA_VERSION%"
  echo set "ALLOW_LEGACY_QUERY_TOKENS=%ALLOW_LEGACY_QUERY_TOKENS%"
  echo set "ALLOW_PASSWORD_RESET_TOKEN_RESPONSE=%ALLOW_PASSWORD_RESET_TOKEN_RESPONSE%"
  echo set "ALLOW_LOCAL_RECOVERY_CODE=%ALLOW_LOCAL_RECOVERY_CODE%"
  echo set "SECRET_KEY=%SECRET_KEY%"
  echo set "JWT_SECRET_KEY=%JWT_SECRET_KEY%"
  echo set "INITIAL_ADMIN_USERNAME=%INITIAL_ADMIN_USERNAME%"
  echo set "INITIAL_ADMIN_EMAIL=%INITIAL_ADMIN_EMAIL%"
  echo set "INITIAL_ADMIN_PASSWORD=%INITIAL_ADMIN_PASSWORD%"
  echo set "INITIAL_ADMIN_NAME=%INITIAL_ADMIN_NAME%"
  echo set "INITIAL_ADMIN_FORCE_PASSWORD_CHANGE=%INITIAL_ADMIN_FORCE_PASSWORD_CHANGE%"
  echo set "INITIAL_FOUNDATION_NAME=%INITIAL_FOUNDATION_NAME%"
  echo set "PYTHONUTF8=1"
  echo set "PYTHONIOENCODING=utf-8"
  echo echo.
  echo echo Plataforma local unificada: %LOCAL_FRONTEND%
  echo echo Instancia verificada: %PROJECT_INSTANCE_ID%
  echo echo Logs de errores: %LOG_FOLDER%
  if "%NEW_LOCAL_DATABASE%"=="1" (
    echo echo Base local nueva creada.
    echo echo Usuario inicial: %INITIAL_ADMIN_USERNAME%
    echo echo Credenciales guardadas en: %LOCAL_CREDENTIALS_FILE%
    echo echo Cambia la clave en el primer ingreso.
  ) else (
    echo echo Base local existente detectada. Usa el usuario y la clave ya registrados.
  )
  echo echo.
  echo "%VENV_PY%" app.py
) > "%RUN_BACKEND_CMD%"

echo.
echo [7/7] Iniciando plataforma...
start "Primera Infancia - Backend + Frontend" cmd /k ""%RUN_BACKEND_CMD%""

echo Esperando respuesta del backend...
for /L %%I in (1,1,60) do (
  powershell -NoProfile -Command "$ErrorActionPreference='Stop'; try { $r=Invoke-RestMethod -Uri '%LOCAL_URL%/api/health' -TimeoutSec 2; if ([string]$r.project_instance_id -eq '%PROJECT_INSTANCE_ID%' -and [string]$r.public_tunnel_mode -eq '%EXPECTED_TUNNEL_MODE%') { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
  if not errorlevel 1 goto :open_browser
  timeout /t 1 /nobreak >nul
)

echo [AVISO] No pude confirmar que el puerto corresponda a esta copia y a este modo.
echo Revisa la ventana "Primera Infancia - Backend + Frontend" y data\logs.
echo Instancia esperada: %PROJECT_INSTANCE_ID% - modo tunel=%EXPECTED_TUNNEL_MODE%
del /Q "%BOOTSTRAP_PASS_FILE%" >nul 2>&1
goto :end

:open_browser
echo.
echo ============================================================
echo Plataforma lista.
echo URL local: %LOCAL_FRONTEND%
echo Instancia: %PROJECT_INSTANCE_ID%
echo Logs de errores: %LOG_FOLDER%
if "%NEW_LOCAL_DATABASE%"=="1" (
  echo Usuario inicial local: %INITIAL_ADMIN_USERNAME%
  echo Credenciales: %LOCAL_CREDENTIALS_FILE%
  echo Debes cambiar la clave en el primer ingreso.
) else (
  echo Base existente: usa las credenciales ya registradas.
)
echo ============================================================
echo.
del /Q "%BOOTSTRAP_PASS_FILE%" >nul 2>&1
start "" "%LOCAL_FRONTEND%"
goto :end

:pip_error
echo.
echo [ERROR] Fallo instalando dependencias.
echo Soluciones rapidas:
echo 1. Mueve el proyecto a una ruta corta, por ejemplo C:\PI\.
echo 2. Borra backend\.venv y ejecuta de nuevo.
echo 3. Usa Python 3.11 o 3.12.
echo 4. Si Windows bloquea rutas largas, habilita LongPathsEnabled.
if not defined PI_NO_PAUSE pause
exit /b 1

:end
if not defined PI_NO_PAUSE pause
endlocal
