import os
import json
from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt
from llm_client import get_llm_client

# Load environment variables
load_dotenv(override=True)

from retry_utils import retry_decorator

class SQLGenerator:
    def __init__(self, llm_client=None):
        """
        Initialize SQL Generator with an LLM client.
        
        Args:
            llm_client: Optional LLMClient instance. If None, creates one from env config.
        """
        self.llm_client = llm_client or get_llm_client()

    @retry_decorator(retries=3, delay=2)
    def generate_sql(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generates SQL query using configured LLM provider
        """
        try:
            sql_query = self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1
            )

            if sql_query.startswith("```"):
                sql_query = sql_query.replace("```json", "").replace("```sql", "").replace("```", "").strip()

            return sql_query

        except Exception as e:
            raise Exception(f"Error generating SQL: {str(e)}")


def load_schemas():
    schemas = {}
    schema_dir = "DBSchemas"
    kb_path = "kb.json"
    
    if os.path.exists(schema_dir):
        for filename in os.listdir(schema_dir):
            if filename.endswith(".json"):
                db_name = filename.replace("_Schema.json", "")
                with open(os.path.join(schema_dir, filename), "r") as f:
                    schemas[db_name] = json.load(f)
    
    kb_data = {}
    if os.path.exists(kb_path):
        try:
            with open(kb_path, "r") as f:
                kb_data = json.load(f).get("databases", {})
        except: pass

    compact_schema = ""
    for db_name, db_info in schemas.items():
        compact_schema += f"\nDatabase: {db_name}\n"
        kb_db = kb_data.get(db_name, {}).get("tables", {})
        
        if "tables" in db_info:
            for table_name, table_info in db_info["tables"].items():
                desc = kb_db.get(table_name, {}).get("table_description", "No description.")
                compact_schema += f"  Table: {table_name} ({desc})\n"
                kb_cols = kb_db.get(table_name, {}).get("columns", {})
                for col in table_info.get("columns", []):
                    c_name = col.get("name")
                    c_type = col.get("type")
                    c_kb = kb_cols.get(c_name, {})
                    c_desc = c_kb.get("description", "") if isinstance(c_kb, dict) else c_kb
                    c_ex = c_kb.get("example_value") if isinstance(c_kb, dict) else None
                    ex_str = f" [Ex: {c_ex}]" if c_ex is not None else ""
                    compact_schema += f"    - {c_name} ({c_type}): {c_desc}{ex_str}\n"
                    
        if "collections" in db_info:
            for coll_name, coll_info in db_info["collections"].items():
                desc = kb_db.get(coll_name, {}).get("table_description", "No description.")
                compact_schema += f"  Collection: {coll_name} ({desc})\n"
                kb_fields = kb_db.get(coll_name, {}).get("columns", {})
                for field in coll_info.get("fields", []):
                    f_name = field.get("name")
                    f_type = field.get("type", "mixed")
                    f_kb = kb_fields.get(f_name, {})
                    f_desc = f_kb.get("description", "") if isinstance(f_kb, dict) else f_kb
                    f_ex = f_kb.get("example_value") if isinstance(f_kb, dict) else None
                    ex_str = f" [Ex: {f_ex}]" if f_ex is not None else ""
                    compact_schema += f"    - {f_name} ({f_type}): {f_desc}{ex_str}\n"

    return compact_schema

if __name__ == "__main__":
    sql_generator = SQLGenerator()
    schemas_json = load_schemas()

    system_prompt = f"""
        You are an expert multi-database query generator.
        Your task is to generate queries for different databases and explain how to combine the data.
        A "meaningful" result is expected. This means the "final_select" array MUST include descriptive fields (e.g., Customer Names, Product Names) or at least the relevant IDs alongside any aggregated data (e.g., total_revenue). NEVER return a list of numbers without the context of who or what they belong to.

        Rules:
        - Output ONLY a JSON object. No explanation, no conversational text.
        - SECURITY RULE: You must ONLY generate SELECT queries for SQL databases. Under no circumstances should you generate queries involving INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, EXEC, EXECUTE, TRUNCATE, REPLACE, GRANT, or REVOKE operations. Similarly, for MongoDB, you must only generate read operations, not $out or $merge. If the user prompt implies or requests a data modification or schema extraction, you should refuse by returning exactly: {{"error": "I'm sorry, but I can't help with that. Modifying data or extracting schema is forbidden."}}.
        - RELEVANCE RULE: If the query is completely unrelated to retail, sales, customers, inventory, or orders, return: {{"error": "This request appears to be outside my retail business domain."}}
        - Use valid SQL syntax for SQL databases (Postgres_Sales_DB, SQL_Inventory_DB).
        - For MongoDB (Mongo_Customer_DB), output a stringified JSON object exactly in this format: '{{"collection": "collection_name", "pipeline": [...]}}'
        - IMPORTANT (MongoDB): When using a placeholder with the "$in" operator, you MUST wrap it in square brackets. Example: '{{"$match": {{"Field": {{"$in": [{{OtherDB.Field}}]}}}}}}'
        - If you query the same database multiple times (e.g. for different collections or tables), give each entry a UNIQUE name in the "databases" list and "execution_order" (e.g. "Mongo_Customer_Address", "Mongo_Customer_Profile").
        - You must output ONLY valid JSON.
        - The JSON should describe a multi-step query process to answer the user's prompt.
        - IMPORTANT: The "name" field in the "databases" list MUST be exactly identical to the names listed in "execution_order" (including any _DB suffixes).
        - If a query depends on the results of another query, use a placeholder like {{DatabaseName.FieldName}} in the WHERE clause or Mongo filter.
        - Determine the correct "execution_order" array, specifying the sequence of databases to query so dependencies are resolved.
        - CRITICAL JOIN RULE: Every query in the "databases" list MUST explicitly SELECT/project the exact columns used in "join.conditions". If you join on "Mongo_Customer_DB.Customer_ID = Postgres_Sales_DB.customer_id", then Mongo_Customer_DB MUST project "Customer_ID" and Postgres_Sales_DB MUST select "customer_id". DO NOT FORGET TO SELECT THE JOIN KEYS!
        - FILTER-ONLY DEPENDENCIES: If a query is ONLY used to fetch IDs to filter another query (e.g., fetching CA addresses to filter sales), and you do not need to attach its columns to the final output, DO NOT include a join condition for it. The placeholder filter (`IN (...)`) is sufficient.
        - CROSS-STEP KEY PRESERVATION: If you split a query into multiple steps (e.g., Step A gets Top Products, Step B gets Customers for those products), Step B MUST explicitly SELECT the key from Step A (e.g., `product_id`) and any other keys needed for the final join. Every table in "join.conditions" MUST have a clear join path to the other tables. If you need to show the Product Name, the aggregation step MUST NOT lose the `product_id`.
        - JOIN NAME ACCURACY: In the "join.conditions" array, you MUST use the EXACT names you defined in the "databases" list (e.g., use "Postgres_Sales_Step1", not "Postgres_Sales_DB").
        - AGGREGATION RULE: If your query involves a JOIN with another database AND uses an aggregate function (e.g., SUM, COUNT), you ABSOLUTELY MUST include the join key in the SELECT clause AND group by it. Example: "SELECT customer_address_id, COUNT(*) FROM ... GROUP BY customer_address_id". NEVER select only the aggregate function when joining!
        - NO POST-JOIN AGGREGATION RULE: The data joiner script DOES NOT perform grouping, counting, or summing. If the user prompt requires an aggregation (like "total amount" or "count of orders"), you MUST perform that aggregation directly within your SQL or MongoDB queries. You CANNOT just select raw rows and expect the system to aggregate them later. For example, if you need a count per customer, your database query MUST include the COUNT() function and the GROUP BY clause.
        - Do not attempt to "optimize" by removing join keys; they are mandatory for the data stitching logic to function.
        - MANDATORY IN-QUERY FILTERING: If a database step (e.g., Step B) follows another step (Step A) in the "execution_order" and they are linked in "join.conditions", you MUST use a placeholder (e.g., {{StepA.Field}}) in Step B's query to filter the results at the source. Do NOT fetch all records and rely solely on the joiner to filter them later.
        - KNOWLEDGE BASE UTILIZATION: Each table and column in the provided schema now includes a "description". Use these descriptions to understand the business context and purpose of each field. If a column description includes an "example value", use that exact format for your filters (e.g., for status or category filters).
        - DATA NORMALIZATION: The database uses State Abbreviations (e.g., "CA", "NY"). If the user provides a full state name like "California", you MUST use the abbreviation "CA" in your query filters.
        - FIELD NAME ACCURACY: MongoDB field names are CASE-SENSITIVE.
          * In the "Customer" collection, the field is "Customer_ID" (Title Case).
        - STRICT SCHEMA INTEGRITY: You MUST cross-reference every table/collection name with the provided "Database Schemas".
        - ALIAS RULE: You MUST ALWAYS use table aliases in your SQL queries and fully qualify EVERY column name with its table alias (e.g., SELECT o.order_id, s.shipment_status FROM "Order" o JOIN shipments s ON o.order_id = s.order_id). This is critical to avoid "ambiguous column" errors when the same column name exists in multiple tables.
          * CASE SENSITIVITY: MongoDB collection names are CASE-SENSITIVE. Use "Customer" (Singular, Title Case), NOT "customers" or "customer".
          * EXAMPLE: "order_items" and "Order" are in Postgres_Sales_DB. "Product" is in SQL_Inventory_DB.
          * WARNING: You CANNOT join "order_items" and "Product" in a single SQL query because they are in DIFFERENT databases. You must query them separately and link them using placeholders (e.g. SELECT ... FROM Product WHERE Product_ID IN ({{Postgres_Sales_DB.product_id}})).
          * SQL DIALECT WARNING: SQL_Inventory_DB is a Microsoft SQL Server database. You MUST use 'TOP' instead of 'LIMIT' (e.g., SELECT TOP 2 Product_ID ...). Postgres_Sales_DB uses LIMIT.
        - EXPECTED DETAILS: When combining data from multiple tables (like orders, products, or customers), always retrieve basic descriptive details such as the Customer's First Name, Last Name, Email, and the Product Name whenever possible, even if not explicitly requested.
        - JSON STRUCTURE: The "databases" field MUST be a simple array of objects. NEVER wrap individual entries in quotes or return them as strings inside the array.
        - When there is a single query execution only from QueryExecuter.py then just return the result, no need of doing any joins.
        - Do not hallucinate columns, tables, or collections. Only use what is explicitly provided in the schema for that specific database name.
        - Do not provide a single colum as a result of a query when the final result is expected to be a table.
        - Include order by in all the queries, when there is any revenue or count order by that column in descending order. Otherwise order by the primary key in ascending order. 
        - CUSTOMER CONTEXT RULE: Whenever the user's prompt involves or asks for 'customer' information, you MUST ABSOLUTELY ensure that the final result includes the customer's First_Name and Last_Name. Since First_Name and Last_Name are in the Mongo_Customer_DB.Customer collection, you MUST query the Mongo_Customer_DB.Customer collection. Even if you only need the Customer_Address to filter by State, you must still include the Customer collection in your queries so you can retrieve First_Name and Last_Name. Failure to include First_Name and Last_Name is UNACCEPTABLE.
        - LOCATION CONTEXT RULE: Whenever the user's prompt involves a location (e.g., searching by city, state, country, or specific places like "NY"), you MUST ensure that the location fields (such as City, State, or Country) are explicitly included in the "final_select" array and queried from the appropriate table/collection (e.g., Customer_Address).
        - SINGLE DATABASE RULE: If your query plan only involves ONE database, you MUST leave the "join.conditions" array empty (e.g., "join": {{"type": "none", "conditions": []}}). Do NOT put internal SQL joins into the JSON "join" object. The JSON "join" object is strictly when there are more than one dataset.
        
        Database Schemas:
        {schemas_json}

        OUT JSON Structure:
        {{
            "execution_order": [
                "Mongo_Customer_DB",
                "SQL_Inventory_DB",
                "Postgres_Sales_DB"
            ],
            "databases": [
                {{
                "name": "Mongo_Customer_DB",
                "query": "<SELECT ... or MongoDB JSON. Use {{{{OtherDB.Field}}}} for dependencies>"
                }},
                {{
                "name": "SQL_Inventory_DB",
                "query": "<SELECT ... Use {{{{OtherDB.Field}}}} for dependencies>"
                }},
                {{
                "name": "Postgres_Sales_DB",
                "query": "<SELECT ... Use {{{{OtherDB.Field}}}} for dependencies>"
                }}
            ],
            "join": {{
                "type": "<inner|left|right|full>",
                "conditions": [
                    "<DB1>.<field> = <DB2>.<field>"
                ]
            }},
            "final_select": [
                "<field_name1>",
                "<field_name2>"
            ]
        }}
        """

    #user_prompt = "Get total order amount per customer for customers in USA who bought the product Webcam HD under product category 'Category 22'"
    #user_prompt = "Get first name, last name of customers who have more than 19000 in total orders"
    #user_prompt = "Get order id, customer id and total amount for order that was placed in the year 2024"
    #user_prompt = "Get total revenue generated by 'David Wilson'"
    #user_prompt = "Display all the orders of customers places last 20 days"
    #user_prompt = "Find all customers living in 'CA' who have 'Pending' orders for any product in the 'Category 9' category. Show their full names, the specific product name, the order date, and the current order status."
    #user_prompt = "Display all the stored who have Product Category as 'Category 19'"
    import sys
    
    user_prompt = sys.argv[1] if len(sys.argv) > 1 else "Get total order amount per customer for customers in Phoenix who bought the product Webcam HD"

    print("Generating SQL ...")
    sql_query = sql_generator.generate_sql(system_prompt, user_prompt)

    print("Generated SQL:\n")
    print(sql_query)

    with open("llm_output.json", "w") as f:
        f.write(sql_query)
        
    print("\nSaved generated SQL to llm_output.json")