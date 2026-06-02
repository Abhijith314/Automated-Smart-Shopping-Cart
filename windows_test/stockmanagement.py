import sqlite3
import random

def purchase_item(barcode, quantity):
    conn = sqlite3.connect("cart_database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT product_name, stock_quantity, reorder_level
        FROM products
        WHERE barcode = ?
    """, (barcode,))

    product = cursor.fetchone()

    if product:
        name, current_stock, reorder = product

        if current_stock >= quantity:

            remaining_stock = current_stock - quantity

            cursor.execute("""
                UPDATE products
                SET stock_quantity = ?
                WHERE barcode = ?
            """, (remaining_stock, barcode))

            conn.commit()

            print("\n------------------------------------")
            print("🛒 Product Name     :", name)
            print("📦 Current Stock    :", current_stock)
            print("🛍 Purchased Qty     :", quantity)
            print("📉 Remaining Stock  :", remaining_stock)

            if remaining_stock <= reorder:
                print("⚠ LOW STOCK - Reorder Required")
            print("------------------------------------")

        else:
            print(f"\n❌ Not enough stock for {name}")

    conn.close()


# -------- MAIN PROGRAM --------

conn = sqlite3.connect("cart_database.db")
cursor = conn.cursor()

cursor.execute("SELECT barcode FROM products")
all_barcodes = [row[0] for row in cursor.fetchall()]

conn.close()

# Randomly select number of products
number_of_products = random.randint(1, len(all_barcodes))
selected_products = random.sample(all_barcodes, number_of_products)

print("\n🧾 SUPERMARKET TRANSACTION STARTED")
print("Total Products Selected:", number_of_products)

for barcode in selected_products:
    quantity = random.randint(1, 5)
    purchase_item(barcode, quantity)

print("\n✅ TRANSACTION COMPLETED SUCCESSFULLY")
