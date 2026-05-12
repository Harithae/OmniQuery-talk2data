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
        compact_schema += f"\nDB: {db_name}\n"
        kb_db = kb_data.get(db_name, {}).get("tables", {})
        
        if "tables" in db_info:
            for table_name, table_info in db_info["tables"].items():
                desc = kb_db.get(table_name, {}).get("table_description", "")
                desc_str = f" ({desc})" if desc and "No description" not in desc else ""
                compact_schema += f" T: {table_name}{desc_str}\n"
                kb_cols = kb_db.get(table_name, {}).get("columns", {})
                for col in table_info.get("columns", []):
                    c_name = col.get("name")
                    c_kb = kb_cols.get(c_name, {})
                    c_ex = c_kb.get("example_value") if isinstance(c_kb, dict) else None
                    ex_str = f" [Ex: {c_ex}]" if c_ex is not None else ""
                    compact_schema += f"  - {c_name}{ex_str}\n"
                    
        if "collections" in db_info:
            for coll_name, coll_info in db_info["collections"].items():
                desc = kb_db.get(coll_name, {}).get("table_description", "")
                desc_str = f" ({desc})" if desc and "No description" not in desc else ""
                compact_schema += f" C: {coll_name}{desc_str}\n"
                kb_fields = kb_db.get(coll_name, {}).get("columns", {})
                for field in coll_info.get("fields", []):
                    f_name = field.get("name")
                    f_kb = kb_fields.get(f_name, {})
                    f_ex = f_kb.get("example_value") if isinstance(f_kb, dict) else None
                    ex_str = f" [Ex: {f_ex}]" if f_ex is not None else ""
                    compact_schema += f"  - {f_name}{ex_str}\n"

    return compact_schema

if __name__ == "__main__":
    sql_generator = SQLGenerator()
    schemas_json = load_schemas()

    system_prompt = f"""
        You are an expert multi-database query generator.
        Your task is to generate queries for different databases and explain how to combine the data.
        A "meaningful" result is expected. This means the "final_select" array MUST include descriptive fields (e.g., Customer Names, Product Names) or at least the relevant IDs alongside any aggregated data (e.g., total_revenue). NEVER return a list of numbers without the context of who or what they belong to.

        Rules:
        - UI CLEANLINESS RULE: In the "final_select" array, it is perfectly fine to include internal ID fields (e.g., customer_id, product_id, _id) as they will be automatically hidden in the frontend table. However, you MUST ensure that descriptive, human-readable fields (e.g., Names, Emails, Product Names) are also included whenever possible.
        - Output ONLY a JSON object. No explanation, no conversational text.
        - SECURITY RULE: You must ONLY generate SELECT queries for SQL databases. Under no circumstances should you generate queries involving INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, EXEC, EXECUTE, TRUNCATE, REPLACE, GRANT, or REVOKE operations. Similarly, for MongoDB, you must only generate read operations, not $out or $merge. If the user prompt implies or requests a data modification or schema extraction, you should refuse by returning exactly: {{"error": "I'm sorry, but I can't help with that. Modifying data or extracting schema is forbidden."}}.
        - RELEVANCE RULE: If the query is completely unrelated to retail, sales, customers, inventory, or orders, return: {{"error": "This request appears to be outside my retail business domain."}}. However, be lenient: if it mentions customers, products, categories, or locations in a business context, it is likely relevant.
        - Use valid SQL syntax for SQL databases (Postgres_Sales_DB, SQL_Inventory_DB).
        - For MongoDB (Mongo_Customer_DB), output a stringified JSON object exactly in this format: '{{"collection": "collection_name", "pipeline": [...]}}'
        - IMPORTANT (MongoDB): When using a placeholder with the "$in" operator, you MUST wrap the placeholder as a STRING literal inside an array. Example: '{{"$match": {{"Field": {{"$in": ["{{OtherDB.Field}}"]}}}}}}'. NEVER convert the placeholder into a JSON object (e.g., do NOT do [{{"OtherDB": "Field"}}]). It MUST remain a string like `"{{OtherDB.Field}}"`.
        - If you query the same database multiple times (e.g. for different collections or tables), give each entry a UNIQUE name in the "databases" list and "execution_order" (e.g. "Mongo_Customer_Address", "Mongo_Customer_Profile").
        - You must output ONLY valid JSON.
        - The JSON should describe a multi-step query process to answer the user's prompt.
        - IMPORTANT: The "name" field in the "databases" list MUST be exactly identical to the names listed in "execution_order" (including any _DB suffixes).
        - If a query depends on the results of another query, use a placeholder like {{DatabaseName.FieldName}} in the WHERE clause or Mongo filter.
        - Determine the correct "execution_order" array, specifying the sequence of databases to query so dependencies are resolved.
        - MANDATORY JOIN KEYS: Every query in the "databases" list MUST explicitly SELECT/project the exact columns used in "join.conditions". For example, if you join on `SQL_Inventory_DB.Product_ID = Postgres_Sales_DB.product_id`, then SQL_Inventory_DB **MUST** select `Product_ID` and Postgres_Sales_DB **MUST** select `product_id`. 
          * CRITICAL: Even if a join key is not needed for the final display, it MUST be in the SELECT/projection list of its respective query. Failure to select these keys makes the join impossible and will result in an EMPTY final result. This is UNACCEPTABLE.
        - COMPLETE JOIN GRAPH: You MUST include join conditions for EVERY database step that provides columns listed in "final_select". If a step is NOT providing any columns for the final output and is only used for filtering (via placeholders), do NOT include it in "join.conditions". Every table that contributes to the final output must be part of a connected join path.
        - PLACEHOLDER = JOIN: If you use a placeholder like {{StepA.Field}} in Step B's query to filter data, you ONLY need a corresponding join condition "StepA.Field = StepB.Field" if you also need to include columns from StepA in your "final_select". If StepA is only used for filtering, OMIT the join condition to avoid unnecessary complexity and potential join failures.
        - CROSS-STEP KEY PRESERVATION: If you split a query into multiple steps, every step MUST explicitly SELECT the keys needed for the next join or the final output. If you need to show the Product Name, you must join the Product table to the Sales table using the product_id.
        - JOIN NAME ACCURACY: In the "join.conditions" array, you MUST use the EXACT names you defined in the "databases" list (e.g., use "Postgres_Sales_Step1", not "Postgres_Sales_DB").
        - AGGREGATION RULE: If your query involves a JOIN with another database AND uses an aggregate function (e.g., SUM, COUNT), you ABSOLUTELY MUST include the join key in the SELECT clause AND group by it. Example: "SELECT customer_address_id, COUNT(*) FROM ... GROUP BY customer_address_id". NEVER select only the aggregate function when joining!
        - NO POST-JOIN AGGREGATION RULE: The data joiner script DOES NOT perform grouping, counting, or summing. If the user prompt requires an aggregation (like "total amount" or "count of orders"), you MUST perform that aggregation directly within your SQL or MongoDB queries. You CANNOT just select raw rows and expect the system to aggregate them later. For example, if you need a count per customer, your database query MUST include the COUNT() function and the GROUP BY clause.
        - Do not attempt to "optimize" by removing join keys; they are mandatory for the data stitching logic to function.
        - MANDATORY IN-QUERY FILTERING: If a database step (e.g., Step B) follows another step (Step A) in the "execution_order" and they are linked in "join.conditions", you MUST use a placeholder (e.g., {{StepA.Field}}) in Step B's query to filter the results at the source. Do NOT fetch all records and rely solely on the joiner to filter them later.
        - KNOWLEDGE BASE UTILIZATION: Each table and column in the provided schema now includes a "description". Use these descriptions to understand the business context and purpose of each field. If a column description includes an "example value", use that exact format for your filters (e.g., for status or category filters).
        - DATA NORMALIZATION: The database uses State Abbreviations (e.g., "CA", "NY"). If the user provides a full state name like "California", you MUST use the abbreviation "CA" in your query filters.
        - SHIPMENT STATUS RULE: The system only recognizes two shipment statuses: "Delivered" and "Pending". If the user asks for "not delivered", "shipped", or "in transit", you MUST filter by "Pending". NEVER use any other status values in your queries.
        - GEOGRAPHICAL QUERIES: ONLY if a user explicitly asks for locations "surrounding", "near", or "close to" a specific city, you should include neighboring cities. Otherwise, if they just ask for a specific city like "New York" or "Chicago", you MUST ONLY search for exactly that city (e.g. "City": "New York"). Do NOT include surrounding cities unless explicitly requested.
        - FIELD NAME ACCURACY: MongoDB field names are CASE-SENSITIVE.
          * In the "Customer" collection, the field is "Customer_ID" (Title Case).
        - STRICT SCHEMA INTEGRITY: You MUST cross-reference every table/collection name with the provided "Database Schemas".
        - POSTGRES RESERVED WORDS: In Postgres_Sales_DB, the table "Order" is a reserved keyword. You MUST ALWAYS surround it with double quotes: `"Order"`. Failure to do so will cause a syntax error.
        - CRITICAL: NO AMBIGUOUS COLUMNS: Whenever you use a JOIN, you MUST prefix EVERY SINGLE column name in the entire query (SELECT, WHERE, ORDER BY, etc.) with its table alias.
          * BAD:  `SELECT Product_ID, Product_Name FROM Product p JOIN Store_Products sp ...`
          * GOOD: `SELECT p.Product_ID, p.Product_Name, sp.Stock_Quantity FROM Product p JOIN Store_Products sp ...`
        - NO CROSS-DATABASE PROJECTION: Do NOT attempt to include fields from one database (e.g., {{StepA.Field}}) in the SELECT or $project clause of another database (Step B). Placeholders MUST ONLY be used in the WHERE or $match clauses for filtering. The assembly of columns from different databases is handled exclusively by the 'DataJoiner' script using the 'final_select' and 'join.conditions' fields. Failure to follow this will result in malformed, invalid queries.
          * Failure to do this causes "Ambiguous Column Name" errors and is UNACCEPTABLE.
        - ALIAS RULE: If your SQL query involves a JOIN, you MUST use table aliases (e.g., `o`, `p`, `sp`) and you MUST prefix EVERY SINGLE column name in the SELECT, WHERE, GROUP BY, and ORDER BY clauses with its respective alias (e.g., `o.order_id`, `p.Product_Name`).
          * CASE SENSITIVITY: MongoDB collection names are CASE-SENSITIVE. Use "Customer" (Singular, Title Case), NOT "customers" or "customer".
        - CRITICAL: NO CROSS-DATABASE SQL: You CANNOT join tables from different databases in a single SQL query. If you need data from both Postgres and MongoDB, you MUST create two separate database entries in the "databases" list.
          * BAD:  `SELECT ... FROM PostgresDB.Table p JOIN MongoDB.Collection m ...` (Impossible)
          * GOOD: Step 1: Query Postgres. Step 2: Query Mongo. Let the "join.conditions" link them.
          * The "DataJoiner" script is the ONLY component that performs cross-database joins. Do not attempt to do it in SQL.
        - NO PLACEHOLDERS IN SELECT: You MUST NEVER put a placeholder like {{OtherDB.Field}} in the SELECT clause. Placeholders are ONLY for filtering in the WHERE clause (e.g. WHERE id IN ({{OtherDB.id}})).
        - STRICT DATABASE BOUNDARIES: You CANNOT use tables from one database inside the query of another database, neither via JOIN nor via SUBQUERY. For example, "Product", "Store" and "Product_Category" are in SQL_Inventory_DB, so they CANNOT appear ANYWHERE inside a Postgres_Sales_DB query (not even as `SELECT ... FROM Product`). If you need to filter Postgres data by a Product_Category, Step 1: Write a query in SQL_Inventory_DB that joins Product and Product_Category to SELECT the Product_ID. Step 2: Pass those Product_IDs to Postgres via placeholder `WHERE oi.product_id IN ({{SQL_Inventory_DB.Product_ID}})`. NEVER write `SELECT ... FROM Product` inside Postgres_Sales_DB.
        - WARNING: You CANNOT join "order_items" and "Product" in a single SQL query because they are in DIFFERENT databases. You must query them separately and link them using placeholders (e.g. SELECT ... FROM Product WHERE Product_ID IN ({{Postgres_Sales_DB.product_id}})).
          * SQL DIALECT WARNING: SQL_Inventory_DB is a Microsoft SQL Server database. You MUST use 'TOP' instead of 'LIMIT' (e.g., SELECT TOP 2 Product_ID ...). Postgres_Sales_DB uses LIMIT.
        - EXPECTED DETAILS: When combining data from multiple tables (like orders, products, customers, customer Addresses, or stores), always retrieve basic descriptive details such as the Customer's First Name, Last Name, Email, the Product Name, and the Store Name whenever possible, even if not explicitly requested.
        - JSON STRUCTURE: The "databases" field MUST be a simple array of objects. NEVER wrap individual entries in quotes or return them as strings inside the array.
        - When there is a single query execution only from QueryExecuter.py then just return the result, no need of doing any joins.
        - Do not hallucinate columns, tables, or collections. Only use what is explicitly provided in the schema for that specific database name.
        - Do not provide a single colum as a result of a query when the final result is expected to be a table.
        - Include order by in all the queries, when there is any revenue or count order by that column in descending order. Otherwise order by the primary key in ascending order. 
        - CUSTOMER CONTEXT RULE: Whenever the user's prompt involves or asks for 'customer' information (including phrases like "top customers", "get customers", "customer revenue", etc.), you MUST ABSOLUTELY ensure that the final result includes the customer's First_Name and Last_Name. Since First_Name and Last_Name are in the Mongo_Customer_DB.Customer collection, you MUST query the Mongo_Customer_DB.Customer collection. Even if you only need the Customer_Address to filter by State, you must still include the Customer collection in your queries so you can retrieve First_Name and Last_Name. Failure to include First_Name and Last_Name is UNACCEPTABLE.
        - MANDATORY CUSTOMER DETAILS: If the user asks for "top customers" or any customer-related aggregation (e.g., "top 5 customers", "customers by revenue"), you MUST ALWAYS include BOTH:
          1. Postgres_Sales_DB (for revenue/order aggregation)
          2. Mongo_Customer_DB.Customer (for First_Name, Last_Name, Email_ID)
          And you MUST create a join condition linking Postgres_Sales_DB.customer_id to Mongo_Customer_DB.Customer.Customer_ID.
          NEVER return only customer_id and revenue without customer names. This is a CRITICAL requirement.
        - LOCATION CONTEXT RULE: Whenever the user's prompt involves a location (e.g., searching by city, state, country, or specific places like "NY"), you MUST ensure that the location fields (such as City, State, or Country) are explicitly included in the "final_select" array and queried from the appropriate table/collection (e.g., Customer_Address).
        - SINGLE DATABASE RULE: If your query plan only involves ONE database, you MUST leave the "join.conditions" array empty (e.g., "join": {{"type": "none", "conditions": []}}). Do NOT put internal SQL joins into the JSON "join" object. The JSON "join" object is strictly when there are more than one dataset.
        - When generating MongoDB pipeline, always perform $lookup before applying $match filters on joined collections.
        - MONGODB PROJECTION RULE: When projecting fields from a joined collection (e.g., via $lookup), ALWAYS alias the nested fields to top-level fields in the $project stage. For example, use {{"City": "$address.City"}} instead of {{"address.City": 1}}. 
          * CRITICAL: You MUST explicitly include all fields used in "join.conditions" (e.g., "Customer_Address_ID": "$Customer_Address_ID") in the $project stage. If you omit them, the system cannot perform the join, resulting in NULL values. 
          * Ensure the output is flat and matches the "final_select" keys exactly.
        
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
    
    user_prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Get total order amount per customer for customers in Phoenix who bought the product Webcam HD"

    print("Generating SQL ...")
    sql_query = sql_generator.generate_sql(system_prompt, user_prompt)

    print("Generated SQL:\n")
    print(sql_query)

    os.makedirs("Outputs", exist_ok=True)
    with open("Outputs/llm_output.json", "w") as f:
        f.write(sql_query)
        
    print("\nSaved generated SQL to Outputs/llm_output.json")