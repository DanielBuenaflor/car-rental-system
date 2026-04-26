# Car Rental System

A full-featured car rental booking system with web frontend (Flask) and desktop admin application (Java Swing).

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                  Car Rental System                       │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌──────────────────┐          │
│  │  Web App        │    │  Desktop Admin   │          │
│  │  (Flask)        │    │  (Java Swing)     │          │
│  ├─────────────────┤    ├──────────────────┤          │
│  │ - User Login    │    │ - Dashboard      │          │
│  │ - Browse Fleet  │    │ - Vehicles CRUD │          │
│  │ - Book Cars   │    │ - Bookings      │          │
│  │ - Payments    │    │ - Users        │          │
│  │ - My Bookings │    │ - Verifications│          │
│  │ - Invoices   │    │ - Reports      │          │
│  └────────┬──────┘    └────────┬───────┘          │
│           │                    │                    │
│           └──────────┬─────────┘                    │
│                      ▼                               │
│              ┌──────────────┐                       │
│              │   MySQL DB   │                       │
│              └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.10+ | Web app runtime |
| Java JDK | 11+ | Desktop app runtime |
| MySQL | 8.0 | Database |
| Docker | Latest | Containerization |

---

## System Setup Guide

### Option 1: Docker Setup (Recommended)

The easiest way to run the entire system.

```bash
# 1. Clone the repository
git clone https://github.com/DanielBuenaflor/car-rental-system.git
cd car-rental-system

# 2. Start all services with Docker
docker-compose up -d

# 3. Access the applications
# Web App: http://localhost:5000
# Adminer (DB): http://localhost:8080
# ngrok: http://localhost:4040
```

### Option 2: Manual Setup

#### Step 1: Database Setup (MySQL)

```bash
# Install MySQL 8.0
# Create database
CREATE DATABASE car_rental_system;

# Initialize schema
python init_schema.py
```

#### Step 2: Web Application (Flask)

```bash
# 1. Navigate to project
cd car-rental-system

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your settings

# 5. Run the web app
python app.py

# Access: http://localhost:5000
```

#### Step 3: Desktop Admin Application (Java)

```bash
# 1. Navigate to JavaAdmin
cd JavaAdmin

# 2. Configure database connection
copy src\main\resources\config.properties.example src\main\resources\config.properties
# Edit config.properties with your database credentials

# 3. Build the application
build.bat

# 4. Run the admin app
run.bat
```

---

## Environment Configuration

### Web App (.env)

```env
# Database
DB_HOST=db
DB_USER=car_user
DB_PASSWORD=john
DB_NAME=car_rental_system

# Email
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password

# Payment
PAYMONGO_SECRET_KEY=sk_test_xxx
PAYMONGO_PUBLIC_KEY=pk_test_xxx

# Security
SECRET_KEY=your_secret_key

# Base URL
BASE_URL=http://localhost:5000
```

### Desktop Admin (config.properties)

```properties
# Database Connection
db.url=jdbc:mysql://localhost:3307/car_rental_system
db.username=car_user
db.password=your_password_here
db.driver=com.mysql.cj.jdbc.Driver
```

**Note:** If using Docker, change `localhost` to `db` in URLs.

---

## Database Schema

### Tables

| Table | Description |
|-------|-------------|
| `users` | User accounts (customers & admins) |
| `vehicle_brands` | Vehicle manufacturers |
| `vehicles` | Available vehicles |
| `bookings` | Rental bookings |
| `payments` | Payment records |
| `invoices` | Generated invoices |
| `verifications` | User identity verification |
| `testimonials` | Customer reviews |
| `contact_queries` | Contact form submissions |
| `subscribers` | Newsletter subscribers |

---

## Application Ports

| Service | Port | URL |
|--------|-----|-----|
| Web App | 5000 | http://localhost:5000 |
| MySQL | 3307 | localhost:3307 |
| Adminer | 8080 | http://localhost:8080 |
| ngrok | 4040 | http://localhost:4040 |

---

## User Roles

### Admin (role = 'admin')
- Access admin dashboard
- Manage vehicles, bookings, users
- Approve verifications
- View reports and analytics

### User (role = 'user')
- Browse vehicle fleet
- Make bookings
- Make payments
- View booking history

---

## Development

### Running in Development Mode

```bash
# Web App
FLASK_DEBUG=True python app.py

# Desktop Admin
# Just run run.bat
```

### Database Updates

```bash
# Reinitialize database
python init_schema.py --drop
```

---

## Troubleshooting

### Connection Issues

**MySQL Connection Failed**
- Check MySQL is running: `docker ps`
- Verify credentials in .env
- For Docker: Ensure DB_HOST=db

**Java App Can't Connect**
- Verify config.properties credentials
- Check MySQL port (3307 in Docker)

### Build Issues

**Java Build Failed**
- Install Java JDK (not JRE)
- Add Java `bin` folder to PATH

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Web Frontend | Flask, HTML, CSS, JavaScript |
| Web Backend | Python |
| Desktop App | Java Swing |
| Database | MySQL 8.0 |
| Container | Docker |
| Payment | PayMongo/GCash |

---

## License

MIT License

---

## Author

Daniel Buenaflor