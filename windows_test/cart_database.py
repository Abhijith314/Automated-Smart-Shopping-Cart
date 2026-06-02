import sqlite3

def setup_database():
    """Creates and populates the SQLite database with sample product data."""
    try:
        conn = sqlite3.connect('cart_database.db')
        cursor = conn.cursor()

        
        # Create users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username VARCHAR(512),
            email VARCHAR(512),
            phone_no VARCHAR(512),
            last_time_spend VARCHAR(512),
            avg_time VARCHAR(512),
            last_spend VARCHAR(512),
            avg_spend VARCHAR(512),
            last_purchase VARCHAR(512),
            total_purchase VARCHAR(512),
            created_at VARCHAR(512)
        )
        """)
        # Insert sample users
        users_data = [
            (
                1234567890, "Test User", "test@mail.com", "1234567890", "","","", "", "", "0",
                "2025-12-23 19:21:06.361401+00"
            ),
            (
                8848385318, "Abhijith", "abhijith@mail.com", "8848385318", "","","", "", "", "0",
                "2025-12-18 19:30:09.192856+00"
            ),
            (
                8891114832, "hasna", "hasna@mail.com", "8891114832", "","","", "", "", "0",
                "2025-12-22 11:03:16.264095+00"
            )
        ]
        cursor.executemany("""
        INSERT OR IGNORE INTO users
        (id, username, email, phone_no, last_time_spend, avg_time, last_spend, avg_spend,
         last_purchase, total_purchase, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, users_data)

        # Create inventory table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL,
            mrp REAL NOT NULL,
            discount REAL NOT NULL,
            tax_rate REAL NOT NULL,
            quantity_value REAL NOT NULL,
            quantity_unit TEXT NOT NULL,
            stock_quantity INTEGER NOT NULL,
            reorder_level INTEGER NOT NULL
        )
        """)

        # Sample data
        products = [
        ('8901057512345', 'Aashirvaad Atta', 350, 20, 5, 5, 'kg', 60, 15),
        ('8901725187654', 'Sunflower Oil', 180, 30, 5, 1, 'L', 45, 10),
        ('8901302009876', 'Nescafe Coffee', 290, 18, 12, 100, 'g', 35, 8),
        ('8901491198765', 'Dettol Liquid', 85, 14, 12, 250, 'ml', 70, 15),
        ('8906003012345', 'Himalaya Soap', 45, 0, 5, 75, 'g', 120, 25),
        ('8901719101122', 'Bru Coffee', 240, 16, 12, 200, 'g', 40, 10),
        ('8901526709988', 'Dove Soap', 55, 20, 5, 100, 'g', 95, 20),
        ('7501031312345', 'Sprite Bottle', 45, 0.5, 12, 500, 'ml', 85, 20),
        ('8901725198760', 'Kissan Jam', 140, 50, 12, 500, 'g', 50, 12),
        ('8906003098765', 'Pears Soap', 60, 30, 5, 125, 'g', 65, 15),
        ('8901058009439', 'Nestle Munch', 5, 10, 5, 10.4, 'g', 100, 20),
        ('8906016491738', 'Elite premium milk rusk', 35, 12, 5, 182, 'g', 80, 15),
        ('8901030538421', 'Vim dishwash liquid', 25, 8, 12, 200, 'ml', 60, 10),
        ('8914129764182', 'Island healthy desert', 5, 5, 5, 14, 'g', 50, 10),
        ('0736649746503', 'Souhridham peanut', 40, 10, 5, 130, 'g', 70, 15),
        ('8909081008429', 'Sunfeast Yippee! Noodles', 60, 15, 12, 290.4, 'g', 90, 20)
    ]

        # Insert data, ignore if barcode already exists
        cursor.executemany("INSERT OR IGNORE INTO products (barcode, product_name, mrp, discount, tax_rate, quantity_value, quantity_unit, stock_quantity, reorder_level) VALUES (?,?,?,?,?,?,?,?,?)", products)

        
        #create billing table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            items_json TEXT,           -- Stores [id, name, qty, price] as JSON
            subtotal REAL,
            tax_total REAL,
            grand_total REAL,
            payment_status TEXT DEFAULT 'PAID',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        #insert sample bills
        sample_bills = [
            (1234567890, '[{"id":1,"name":"Aashirvaad Atta","qty":2,"price":700}]', 700, 35, 735, 'PAID'),
            (8848385318, '[{"id":2,"name":"Sunflower Oil","qty":1,"price":180}]', 180, 9, 189, 'PAID')
        ]

        cursor.executemany("INSERT OR IGNORE INTO bills (user_id, items_json, subtotal, tax_total, grand_total, payment_status) VALUES (?,?,?,?,?,?)", sample_bills)

        #create orders table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            cart_id INTEGER,
            total_amount REAL,
            payment_status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)
        
        #insert sample orders
        sample_orders = [
            (1234567890, 1, 735, 'Completed'),
            (8848385318, 2, 189, 'Completed')
        ]

        cursor.executemany("INSERT OR IGNORE INTO orders (user_id, cart_id, total_amount, payment_status) VALUES (?,?,?,?)", sample_orders)


        conn.commit()
        print("Database 'cart_database.db' created and populated successfully.")
        print(f"{len(products)} sample products added.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    setup_database()