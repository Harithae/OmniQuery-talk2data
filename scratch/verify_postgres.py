import os, sys
sys.path.insert(0, "backend")
from dotenv import load_dotenv
load_dotenv("backend/.env", override=True)
import psycopg2, psycopg2.extras

dsn = os.getenv("PG_DB_CONN", "").strip('"').strip("'")
print("DSN:", dsn)

conn = psycopg2.connect(dsn)
with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
    cur.execute('SELECT o.customer_id, SUM(o.order_amount) AS total_amount FROM "Order" o GROUP BY o.customer_id ORDER BY total_amount DESC LIMIT 5')
    rows = cur.fetchall()
conn.close()

print(f"Rows returned: {len(rows)}")
for r in rows:
    print(dict(r))
