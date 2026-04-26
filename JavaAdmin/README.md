# Car Rental Admin Desktop Application

A Java Swing desktop application for managing the Car Rental System. Provides a full-featured admin dashboard for managing vehicles, bookings, users, verifications, and more.

## Features

- **Dashboard** - View statistics and quick actions
- **Vehicles** - Add, edit, delete vehicles
- **Bookings** - Manage rental bookings (confirm, complete, cancel)
- **Users** - Manage customer accounts (activate, deactivate)
- **Verifications** - Approve/reject user identity verification
- **Brands** - Manage vehicle brands
- **Testimonials** - Approve/reject customer reviews
- **Queries** - Reply to contact form submissions
- **Subscribers** - Manage newsletter subscribers

## Requirements

- Java JDK 11 or higher
- MySQL 8.0 database
- MySQL Connector/J (included in lib/)

## Setup

### 1. Clone and Navigate
```bash
git clone https://github.com/DanielBuenaflor/car-rental-system.git
cd car-rental-system/JavaAdmin
```

### 2. Configure Database

Copy the example config file:
```bash
copy src\main\resources\config.properties.example src\main\resources\config.properties
```

Edit `config.properties` with your database credentials:
```properties
db.url=jdbc:mysql://localhost:3307/car_rental_system
db.username=your_username
db.password=your_password
db.driver=com.mysql.cj.jdbc.Driver
```

**Note:** If using Docker, change `localhost` to the container name (e.g., `db`)

### 3. Build

Run the build script:
```bash
build.bat
```

Or manually compile:
```bash
mkdir target\classes
javac -cp "lib/*" -d "target\classes" src\main\java\com\carrental\admin\*.java
jar cf "target\CarRentalAdmin.jar" -C "target\classes" .
```

### 4. Run

```bash
run.bat
```

The admin application will open with a login window.

## Project Structure

```
JavaAdmin/
├── src/main/
│   ├── java/com/carrental/admin/
│   │   ├── dao/         # Data Access Objects
│   │   ├── model/       # Data Models
│   │   ├── ui/         # Swing UI Panels
│   │   └── util/       # Utilities
│   └── resources/
│       ├── config.properties          # Database config (local)
│       └── config.properties.example # Template
├── lib/                # MySQL connector
├── target/              # Compiled classes
├── build.bat           # Build script
├── run.bat            # Run script
└── pom.xml           # Maven config (optional)
```

## Troubleshooting

### Connection Error
- Make sure MySQL is running
- Check `config.properties` credentials are correct
- If using Docker, ensure container port is exposed (e.g., `-p 3307:3306`)

### Build Error
- Install Java JDK (not JRE)
- Add Java `bin` folder to PATH

### Port Already in Use
- Stop other MySQL instances
- Or change port in config (e.g., `localhost:3306`)

## Technology

- **Language:** Java 11
- **GUI:** Swing (built-in)
- **Database:** MySQL 8.0
- **JDBC Driver:** MySQL Connector/J 8.0.33

## License

MIT License - See LICENSE file for details

---

Built for Car Rental System