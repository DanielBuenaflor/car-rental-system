@echo off
REM Car Rental Admin Desktop Application Launcher
REM Location: JavaAdmin folder

echo Starting Car Rental Admin...

REM Change to app directory
cd /d "%~dp0"

REM Set MySQL connector path (from Maven cache)
set MYSQL_CONNECTOR=C:\Users\Administrator\.m2\repository\com\mysql\mysql-connector-j\8.0.33\mysql-connector-j-8.0.33.jar

REM Run the Java app
java -cp "target\classes;%MYSQL_CONNECTOR%" com.carrental.admin.MainApp

pause