@echo off
REM =============================================
REM Car Rental Admin - Build Script
REM =============================================
REM This script compiles the Java source files
REM Requirements: Java JDK installed
REM =============================================

echo Building Car Rental Admin...
echo.

REM Create target directory if not exists
if not exist "target\classes" mkdir "target\classes"

REM Compile all Java files
echo Compiling Java files...
javac -cp "lib/*" -d "target\classes" "src\main\java\com\carrental\admin\model\*.java" "src\main\java\com\carrental\admin\dao\*.java" "src\main\java\com\carrental\admin\util\*.java" "src\main\java\com\carrental\admin\ui\*.java" "src\main\java\com\carrental\admin\MainApp.java"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Build FAILED!
    echo Make sure Java JDK is installed
    pause
    exit /b 1
)

REM Create JAR file
echo Creating JAR file...
if exist "target\CarRentalAdmin.jar" del "target\CarRentalAdmin.jar"
jar cf "target\CarRentalAdmin.jar" -C "target\classes" .

echo.
echo =============================================
echo Build SUCCESSFUL!
echo =============================================
echo.
echo Next steps:
echo 1. Copy config.properties.example to config.properties
echo 2. Edit config.properties with your database credentials
echo 3. Run run.bat to start the application
echo.
pause