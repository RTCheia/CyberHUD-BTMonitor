$ErrorActionPreference = "Stop"

$BUILD_TOOLS = "D:\android-sdk\build-tools\33.0.2"
$PLATFORM = "D:\android-sdk\platforms\android-33\android.jar"
$JAVA_HOME = "C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot"
$JAVA_BIN = "$JAVA_HOME\bin\java.exe"
$JAVAC_BIN = "$JAVA_HOME\bin\javac.exe"
$KEYTOOL_BIN = "$JAVA_HOME\bin\keytool.exe"
$JAR_BIN = "$JAVA_HOME\bin\jar.exe"

$APP_DIR = $PSScriptRoot
$BUILD_DIR = "$APP_DIR\build"
$RES_DIR = "$APP_DIR\src\main\res"
$MANIFEST = "$APP_DIR\src\main\AndroidManifest.xml"
$JAVA_SRC = "$APP_DIR\src\main\java"

Write-Host "=== [1/7] Cleaning and preparing build dir ==="
if (Test-Path $BUILD_DIR) { Remove-Item -Recurse -Force $BUILD_DIR }
New-Item -ItemType Directory -Force -Path "$BUILD_DIR\compiled_res" | Out-Null
New-Item -ItemType Directory -Force -Path "$BUILD_DIR\gen" | Out-Null
New-Item -ItemType Directory -Force -Path "$BUILD_DIR\classes" | Out-Null

Write-Host "=== [2/7] aapt2 compile ==="
$resFiles = Get-ChildItem -Path $RES_DIR -Recurse -File
foreach ($file in $resFiles) {
    if ($file.FullName -match "\\res\\(drawable|layout|values|color)") {
        & "$BUILD_TOOLS\aapt2.exe" compile $file.FullName -o "$BUILD_DIR\compiled_res"
    }
}

Write-Host "=== [3/7] aapt2 link ==="
$flatFiles = (Get-ChildItem -Path "$BUILD_DIR\compiled_res\*.flat" | ForEach-Object { $_.FullName })
& "$BUILD_TOOLS\aapt2.exe" link -I $PLATFORM `
    --manifest $MANIFEST `
    --java "$BUILD_DIR\gen" `
    -o "$BUILD_DIR\unaligned_res.apk" `
    --auto-add-overlay `
    $flatFiles

Write-Host "=== [4/7] javac compile ==="
$javaFiles = Get-ChildItem -Path "$BUILD_DIR\gen", $JAVA_SRC -Filter "*.java" -Recurse | ForEach-Object { $_.FullName }
& $JAVAC_BIN --release 8 -encoding UTF-8 -cp $PLATFORM -d "$BUILD_DIR\classes" $javaFiles

Write-Host "=== [5/7] d8 compile classes.dex ==="
$classFiles = Get-ChildItem -Path "$BUILD_DIR\classes" -Filter "*.class" -Recurse | ForEach-Object { $_.FullName }
& $JAVA_BIN -cp "$BUILD_TOOLS\lib\d8.jar" com.android.tools.r8.D8 --output $BUILD_DIR --lib $PLATFORM $classFiles

Write-Host "=== [6/7] inject classes.dex into APK ==="
Copy-Item "$BUILD_DIR\unaligned_res.apk" "$BUILD_DIR\app_unsigned.apk"
Push-Location $BUILD_DIR
& $JAR_BIN -uf "app_unsigned.apk" "classes.dex"
Pop-Location

Write-Host "=== [7/7] zipalign and apksigner ==="
& "$BUILD_TOOLS\zipalign.exe" -v -p 4 "$BUILD_DIR\app_unsigned.apk" "$BUILD_DIR\app_aligned.apk"

$KEYSTORE = "$APP_DIR\debug.keystore"
if (-not (Test-Path $KEYSTORE)) {
    & $KEYTOOL_BIN -genkeypair -v `
        -keystore $KEYSTORE `
        -alias androiddebugkey `
        -keyalg RSA -keysize 2048 -validity 10000 `
        -storepass android -keypass android `
        -dname "CN=Android Debug,O=Android,C=US"
}

& $JAVA_BIN -jar "$BUILD_TOOLS\lib\apksigner.jar" sign `
    --ks $KEYSTORE --ks-pass pass:android --ks-key-alias androiddebugkey --key-pass pass:android `
    --out "$APP_DIR\PCMonitor.apk" "$BUILD_DIR\app_aligned.apk"

Write-Host "=== [SUCCESS] APK Generated: $APP_DIR\PCMonitor.apk ==="
