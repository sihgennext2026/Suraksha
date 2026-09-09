<#
.SYNOPSIS
  Builds a standalone, installable APK of SSB Suraksha.

.DESCRIPTION
  The output runs on its own: the JavaScript bundle is compiled into the APK, so
  there is no Metro server, no Expo Go, and no development machine involved. That
  is the only build that demonstrates the actual product, which is an offline
  screening tool.

  The script exists because three things about this build are environment-
  specific and easy to get wrong by hand:

    * the JDK. Gradle 8.14 and the Android Gradle Plugin want Java 17-21. The
      JetBrains runtime shipped with recent Android Studio is Java 25, which
      Gradle does not support, so the newest JDK is the wrong choice.
    * the Android SDK location, which is not on PATH here.
    * TLS. Antivirus HTTPS scanning (Avast, Kaspersky, corporate proxies) hands
      the JVM a certificate signed by a private CA. Node is already told about
      it through NODE_EXTRA_CA_CERTS; Java has no equivalent and fails every
      download with a PKIX error. See New-TrustStore below.

.PARAMETER Variant
  Release (default) produces a signed, self-contained APK. Debug produces one
  that still needs a Metro server, and is only useful for native debugging.

.PARAMETER Clean
  Regenerate android/ from app.json before building. Use after changing app
  config or plugins.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/build-apk.ps1
#>
[CmdletBinding()]
param(
    [ValidateSet('Release', 'Debug')]
    [string]$Variant = 'Release',
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

<#
  Picks a JDK that Gradle supports, newest first within the supported range.
  An unsupported JDK does not fail early with a clear message - it fails deep
  inside Kotlin compilation with an unrecognised class file version - so it is
  worth resolving deliberately rather than inheriting whatever JAVA_HOME holds.
#>
function Resolve-Jdk {
    $candidates = @()
    if ($env:JAVA_HOME) { $candidates += $env:JAVA_HOME }
    $candidates += Get-ChildItem "$env:USERPROFILE\.jdks" -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | ForEach-Object { $_.FullName }
    $candidates += Get-ChildItem "$env:ProgramFiles\Eclipse Adoptium" -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | ForEach-Object { $_.FullName }
    $candidates += "$env:ProgramFiles\Android\Android Studio\jbr"

    foreach ($candidate in $candidates) {
        if (-not (Test-Path (Join-Path $candidate 'bin\java.exe'))) { continue }

        # Read the version from the JDK's own `release` manifest rather than
        # running `java -version`: that writes to stderr, which Windows
        # PowerShell turns into a terminating error under $ErrorActionPreference
        # = 'Stop' even when the process exits 0.
        $manifest = Join-Path $candidate 'release'
        if (-not (Test-Path $manifest)) { continue }
        $line = Select-String -Path $manifest -Pattern '^JAVA_VERSION="([^"]+)"' | Select-Object -First 1
        if (-not $line) { continue }

        $major = [int](($line.Matches[0].Groups[1].Value -split '\.')[0])
        if ($major -ge 17 -and $major -le 21) {
            Write-Host "JDK        $candidate (Java $major)"
            return $candidate
        }
    }
    throw "No Java 17-21 JDK found. Install one via Android Studio > Settings > Build Tools > Gradle > Download JDK."
}

function Resolve-AndroidSdk {
    foreach ($sdk in @($env:ANDROID_HOME, $env:ANDROID_SDK_ROOT, "$env:LOCALAPPDATA\Android\Sdk")) {
        if ($sdk -and (Test-Path (Join-Path $sdk 'platform-tools'))) {
            Write-Host "Android SDK $sdk"
            return $sdk
        }
    }
    throw "Android SDK not found. Install it through Android Studio > Settings > Languages & Frameworks > Android SDK."
}

<#
  Returns a truststore containing the JDK's own roots plus any locally installed
  interception CA, or $null when nothing is intercepting.

  NODE_EXTRA_CA_CERTS is the signal: whatever installed the intercepting proxy
  set it so Node would keep working, and that same CA is what the JVM is
  missing. Copying the JDK's cacerts and adding one certificate keeps every
  public root trusted - it widens trust by exactly the CA already installed on
  this machine, rather than disabling verification.
#>
function New-TrustStore {
    param([Parameter(Mandatory)][string]$JdkHome)

    $ca = $env:NODE_EXTRA_CA_CERTS
    if (-not $ca -or -not (Test-Path $ca)) { return $null }

    $store = "$env:LOCALAPPDATA\ssb-suraksha\android-truststore.jks"
    $source = Join-Path $JdkHome 'lib\security\cacerts'

    # Rebuild when either input is newer than the store, so a JDK switch or a
    # rotated antivirus certificate does not leave a stale store behind.
    if (Test-Path $store) {
        $built = (Get-Item $store).LastWriteTime
        if ($built -gt (Get-Item $ca).LastWriteTime -and $built -gt (Get-Item $source).LastWriteTime) {
            Write-Host "TLS        reusing $store"
            return $store
        }
    }

    Write-Host "TLS        HTTPS interception detected; trusting $ca"
    New-Item -ItemType Directory -Force -Path (Split-Path $store) | Out-Null
    Remove-Item $store -Force -ErrorAction SilentlyContinue
    Copy-Item $source $store
    # No stderr redirection here for the same reason as in Resolve-Jdk: keytool
    # reports success on stderr, and capturing it would raise a false failure.
    & (Join-Path $JdkHome 'bin\keytool.exe') -importcert -noprompt -trustcacerts `
        -alias local-tls-interception -file $ca -keystore $store -storepass changeit
    if ($LASTEXITCODE -ne 0) { throw "keytool could not add $ca to $store" }
    return $store
}

# --- build ----------------------------------------------------------------

$jdk = Resolve-Jdk
$sdk = Resolve-AndroidSdk
$env:JAVA_HOME = $jdk
$env:ANDROID_HOME = $sdk
$env:ANDROID_SDK_ROOT = $sdk

$truststore = New-TrustStore -JdkHome $jdk
if ($truststore) {
    # JAVA_TOOL_OPTIONS rather than GRADLE_OPTS: the wrapper's downloader, the
    # Gradle daemon and the forked Kotlin compiler are separate JVMs, and each
    # one needs the trust setting. Every JVM reads this variable at startup.
    $env:JAVA_TOOL_OPTIONS = "-Djavax.net.ssl.trustStore=$truststore -Djavax.net.ssl.trustStorePassword=changeit"
}

Push-Location $ProjectRoot
try {
    if ($Clean -or -not (Test-Path 'android')) {
        Write-Host "`nGenerating android/ from app.json..."
        & npx expo prebuild --platform android --clean --no-install
        if ($LASTEXITCODE -ne 0) { throw "expo prebuild failed" }
    }

    Write-Host "`nBuilding $Variant APK...`n"
    Push-Location 'android'
    try {
        & .\gradlew.bat "assemble$Variant" --no-daemon
        if ($LASTEXITCODE -ne 0) { throw "Gradle build failed" }
    } finally { Pop-Location }

    $apk = Get-ChildItem "android\app\build\outputs\apk\$($Variant.ToLower())\*.apk" |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $apk) { throw "Build reported success but produced no APK" }

    New-Item -ItemType Directory -Force -Path 'dist' | Out-Null
    $out = "dist\SSB-Suraksha-$($Variant.ToLower()).apk"
    Copy-Item $apk.FullName $out -Force

    Write-Host "`nAPK  $((Resolve-Path $out).Path)"
    Write-Host ("Size {0:N1} MB" -f ($apk.Length / 1MB))
    Write-Host "`nInstall over USB:  adb install -r `"$out`""
    Write-Host "Or copy the file to the phone and open it (allow install from unknown sources)."
} finally { Pop-Location }
