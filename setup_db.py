import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "airline_pss.db")

def init_airline_db(db_path=DEFAULT_DB_PATH):
    """Initializes the database schema and seeds initial flight and booking data."""
    conn = sqlite3.connect(db_path, timeout=10.0)
    cursor = conn.cursor()

    # Drop existing tables to ensure clean schema recreation
    cursor.execute("DROP TABLE IF EXISTS bookings")
    cursor.execute("DROP TABLE IF EXISTS flights")

    # 1. Flight Status Table
    cursor.execute("""
        CREATE TABLE flights (
            flight_number TEXT PRIMARY KEY,
            origin TEXT,
            destination TEXT,
            status TEXT,
            departure_time TEXT,
            reason TEXT
        )
    """)

    # 2. Passenger Booking Table (PNR)
    cursor.execute("""
        CREATE TABLE bookings (
            pnr TEXT PRIMARY KEY,
            passenger_name TEXT,
            flight_number TEXT,
            tier TEXT,
            checked_bags INTEGER,
            status TEXT DEFAULT 'CONFIRMED',
            FOREIGN KEY (flight_number) REFERENCES flights (flight_number)
        )
    """)

    # Seed Sample Data
    flights_data = [
        ("PK302", "KHI", "LHE", "CANCELED", "18:00 PKT", "Heavy Fog at LHE"),
        ("PK304", "KHI", "LHE", "ON_TIME", "21:30 PKT", "None"),
        ("PK306", "KHI", "LHE", "ON_TIME", "08:00 PKT Tomorrow", "None"),
        ("PA200", "KHI", "ISB", "ON_TIME", "19:00 PKT", "None")
    ]

    bookings_data = [
        ("PK-88912", "Mahreen", "PK302", "Gold", 2, "CONFIRMED"),
        ("PK-44102", "Hammad", "PA200", "Regular", 1, "CONFIRMED")
    ]

    cursor.executemany("INSERT INTO flights VALUES (?,?,?,?,?,?)", flights_data)
    cursor.executemany("INSERT INTO bookings VALUES (?,?,?,?,?,?)", bookings_data)

    conn.commit()
    conn.close()
    print("Database initialized successfully with production schemas.")

if __name__ == "__main__":
    init_airline_db()