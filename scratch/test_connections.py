"""
test_connections.py
Tests connectivity to all 3 databases:
  - SQL Server  (InventoryDB)   via pyodbc       [SQL_DB_CONN]
  - PostgreSQL  (SalesDB)       via psycopg2     [PG_DB_CONN]
  - MongoDB     (CustomerDB)    via pymongo      [MONGO_URI / CUSTOMER_DB]

Run from the workspace root:
    python scratch/test_connections.py
"""

import os
import sys

# Load .env from the backend folder
from dotenv import load_dotenv
load_dotenv(dotenv_path="backend/.env", override=True)

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS = "✅ PASS"
FAIL = "❌ FAIL"

results = {}

# ---------------------------------------------------------------------------
# 1. SQL Server — InventoryDB
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("  1. SQL Server — InventoryDB")
print("=" * 60)

try:
    import pyodbc

    conn_str = os.getenv("SQL_DB_CONN", "").strip('"').strip("'")
    if not conn_str:
        raise ValueError("SQL_DB_CONN is not set in .env")

    print(f"  Connection string : {conn_str}")
    conn = pyodbc.connect(conn_str, timeout=5)
    cursor = conn.cursor()

    # Verify we can query a known table
    cursor.execute("SELECT TOP 3 Product_ID, Product_Name FROM Product")
    rows = cursor.fetchall()
    conn.close()

    print(f"  Sample rows from [Product]:")
    for row in rows:
        print(f"    {dict(zip([d[0] for d in cursor.description], row))}")

    results["SQL Server"] = PASS
    print(f"  Result: {PASS}")

except Exception as e:
    results["SQL Server"] = FAIL
    print(f"  Result: {FAIL}")
    print(f"  Error : {e}")

# ---------------------------------------------------------------------------
# 2. PostgreSQL — SalesDB
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("  2. PostgreSQL — SalesDB")
print("=" * 60)

try:
    import psycopg2
    import psycopg2.extras

    pg_conn_str = os.getenv("PG_DB_CONN", "").strip('"').strip("'")
    if not pg_conn_str:
        raise ValueError("PG_DB_CONN is not set in .env")

    print(f"  Connection string : {pg_conn_str}")
    conn = psycopg2.connect(pg_conn_str)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('SELECT order_id, customer_id, order_amount FROM "Order" LIMIT 3')
        rows = cur.fetchall()
    conn.close()

    print(f"  Sample rows from [Order]:")
    for row in rows:
        print(f"    {dict(row)}")

    results["PostgreSQL"] = PASS
    print(f"  Result: {PASS}")

except Exception as e:
    results["PostgreSQL"] = FAIL
    print(f"  Result: {FAIL}")
    print(f"  Error : {e}")

# ---------------------------------------------------------------------------
# 3. MongoDB — CustomerDB
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("  3. MongoDB — CustomerDB")
print("=" * 60)

try:
    import pymongo

    mongo_uri   = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    customer_db = os.getenv("CUSTOMER_DB", "CustomerDB")

    print(f"  URI      : {mongo_uri}")
    print(f"  Database : {customer_db}")

    client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    # Force a real connection attempt
    client.server_info()

    db = client[customer_db]
    collections = db.list_collection_names()
    print(f"  Collections found : {collections}")

    # Sample a document from the Customer collection
    sample = db["Customer"].find_one({}, {"_id": 0, "Customer_ID": 1, "First_Name": 1, "Last_Name": 1})
    print(f"  Sample doc from [Customer]: {sample}")
    client.close()

    results["MongoDB"] = PASS
    print(f"  Result: {PASS}")

except Exception as e:
    results["MongoDB"] = FAIL
    print(f"  Result: {FAIL}")
    print(f"  Error : {e}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("  SUMMARY")
print("=" * 60)
for db, status in results.items():
    print(f"  {db:<15} {status}")
print("=" * 60 + "\n")

all_passed = all(s == PASS for s in results.values())
sys.exit(0 if all_passed else 1)
