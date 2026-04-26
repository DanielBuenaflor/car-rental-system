@echo off
REM Car Rental Admin Desktop Application Launcher
REM Location: JavaAdmin folder

echo Starting Car Rental Admin...

REM Change to app directory
cd /d "%~dp0"

REM Run the Java app
java -cp "target\CarRentalAdmin_v2.jar;lib\mysql-connector-j-8.0.33.jar" com.carrental.admin.MainApp

pause