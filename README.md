# Car Rental System

A car rental booking system with a Flask web app and a Java Swing desktop admin app.

## Requirements

- Python 3.10+
- Java JDK 11+
- MySQL 8.0

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/DanielBuenaflor/car-rental-system.git
cd car-rental-system
```

### 2. Set up the database

```sql
CREATE DATABASE car_rental_system;
```

Then initialize the schema:

```bash
python init_schema.py
```

### 3. Set up the Flask web app

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

The web app runs at `http://localhost:5000`.

### 4. Set up the Java admin app

```bash
cd JavaAdmin
copy src\main\resources\config.properties.example src\main\resources\config.properties
build.bat
run.bat
```

## Environment Configuration

Example `.env` values:

```env
DB_HOST=localhost
DB_USER=car_user
DB_PASSWORD=your_password_here
DB_NAME=car_rental_system

MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password

PAYMONGO_SECRET_KEY=sk_test_xxx
PAYMONGO_PUBLIC_KEY=pk_test_xxx
PAYMONGO_WEBHOOK_SECRET=whsk_xxx

SECRET_KEY=your_secret_key
BASE_URL=http://localhost:5000
```

Java admin `config.properties` example:

```properties
db.url=jdbc:mysql://localhost:3307/car_rental_system
db.username=car_user
db.password=your_password_here
db.driver=com.mysql.cj.jdbc.Driver
```

## Application Ports

- Web app: `http://localhost:5000`
- MySQL: `localhost:3307`

## User Roles

- `admin`: manages vehicles, bookings, users, verifications, and reports
- `user`: browses vehicles, books cars, pays, and views booking history

## Development

Run Flask in development mode:

```bash
FLASK_DEBUG=True python app.py
```

Reinitialize the database:

```bash
python init_schema.py --drop
```

## Troubleshooting

### MySQL connection failed

- Make sure MySQL is running
- Verify the credentials in `.env`
- Confirm the app can reach `DB_HOST=localhost`

### Java app cannot connect

- Verify `config.properties` credentials
- Check that MySQL is listening on the configured port

### Java build failed

- Install Java JDK, not JRE
- Add Java `bin` to `PATH`

## Technology Stack

- Web frontend: Flask, HTML, CSS, JavaScript
- Web backend: Python
- Desktop app: Java Swing
- Database: MySQL 8.0
- Payment: PayMongo / GCash

## License

MIT License

## Author

Daniel Buenaflor
