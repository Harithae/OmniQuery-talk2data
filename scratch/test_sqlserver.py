import pyodbc
import os
from dotenv import load_dotenv

# Point to the .env in the backend folder
load_dotenv(dotenv_path="backend/.env")

conn_str = os.getenv("SQLSERVER_CONNECTION_STRING", "").strip('"')
print(f"Testing connection to: {conn_str}")

if not conn_str:
    print("FAILURE: Connection string is empty. Check your .env file.")
else:
    try:
        conn = pyodbc.connect(conn_str, timeout=5)
        print("SUCCESS: Connected to SQL Server!")
        cursor = conn.cursor()
        cursor.execute("SELECT TOP 1 * FROM Product")
        row = cursor.fetchone()
        print(f"Sample row: {row}")
        conn.close()
    except Exception as e:
        print(f"FAILURE: {e}")
