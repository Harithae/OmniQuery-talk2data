from groq import Groq
import os
import json
from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt

# Load environment variables
load_dotenv(override=True)

class SQLGenerator:
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b"):
        self.client = Groq(api_key=api_key)
        self.model = model

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    def generate_sql(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generates SQL query using Groq LLM
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                temperature=0.1
            )

            sql_query = response.choices[0].message.content.strip()

            if sql_query.startswith("```"):
                sql_query = sql_query.replace("```json", "").replace("```sql", "").replace("```", "").strip()

            return sql_query

        except Exception as e:
            raise Exception(f"Error generating SQL: {str(e)}")


def load_schemas():
    schemas = {}
    schema_dir = "DBSchemas"
    if os.path.exists(schema_dir):
        for filename in os.listdir(schema_dir):
            if filename.endswith(".json"):
                db_name = filename.replace("_Schema.json", "")
                with open(os.path.join(schema_dir, filename), "r") as f:
                    schemas[db_name] = json.load(f)
    return json.dumps(schemas, separators=(',', ':'))

if __name__ == "__main__":
    API_KEY = os.getenv("GROQ_API_KEY")
    MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.1-8b-instant")
    if not API_KEY:
        print("Please set GROQ_API_KEY in your environment or .env file.")
        exit(1)
    sql_generator = SQLGenerator(api_key=API_KEY)
    schemas_json = load_schemas()

    system_prompt = f"""
        You are an expert multi-database query generator.
        Your task is to generate queries for different databases and explain how to combine the data.
        A "meaningful" result is expected. This means the "final_select" array MUST include descriptive fields (e.g., Customer Names, Product Names) or at least the relevant IDs alongside any aggregated data (e.g., total_revenue). NEVER return a list of numbers without the context of who or what they belong to.

        Rules:
        - Output ONLY a JSON object. No explanation, no conversational text.
        - Use valid SQL syntax for SQL databases (Postgres_Sales_DB, SQL_Inventory_DB).
        - For MongoDB (Mongo_Customer_DB), output a stringified JSON object exactly in this format: '{{"collection": "collection_name", "pipeline": [...]}}'
        - IMPORTANT (MongoDB): When using a placeholder with the "$in" operator, you MUST wrap it in square brackets. Example: '{{"$match": {{"Field": {{"$in": [{{OtherDB.Field}}]}}}}}}'
        - If you query the same database multiple times (e.g. for different collections or tables), give each entry a UNIQUE name in the "databases" list and "execution_order" (e.g. "Mongo_Customer_Address", "Mongo_Customer_Profile").
        - You must output ONLY valid JSON.
        - The JSON should describe a multi-step query process to answer the user's prompt.
        - IMPORTANT: The "name" field in the "databases" list MUST be exactly identical to the names listed in "execution_order" (including any _DB suffixes).
        - If a query depends on the results of another query, use a placeholder like {{DatabaseName.FieldName}} in the WHERE clause or Mongo filter.
        - Determine the correct "execution_order" array, specifying the sequence of databases to query so dependencies are resolved.
        - CRITICAL JOIN RULE: Every query in the "databases" list MUST explicitly SELECT/project the columns mentioned in "join.conditions". If you join on "Mongo_Customer_DB.Customer_ID = Postgres_Sales_DB.customer_id", then Mongo_Customer_DB MUST project "Customer_ID" and Postgres_Sales_DB MUST select "customer_id". Failure to do this will break the application.
        - AGGREGATION RULE: If a query uses an aggregate function (e.g., SUM, COUNT, AVG), any field you put in "join.conditions" for that table MUST be present in the SELECT clause and the GROUP BY clause. If you want to show Product Names alongside Customer Names, you MUST include `product_id` in the GROUP BY so you can join it with the Product table later.
        - FILTER-ONLY DEPENDENCIES: If a query is ONLY used to fetch IDs to filter another query (e.g., fetching CA addresses to filter sales), and you do not need to attach its columns to the final output, DO NOT include a join condition for it. The placeholder filter (`IN (...)`) is sufficient.
        - MANDATORY IN-QUERY FILTERING: If a database step (Step B) follows another step (Step A) in the "execution_order" and they are linked in "join.conditions", you MUST use a placeholder (e.g., {{StepA.Field}}) in Step B's query to filter the results at the source.
        - CROSS-STEP KEY PRESERVATION: If you split a query into multiple steps (e.g., Step A gets Top Products, Step B gets Customers for those products), Step B MUST explicitly SELECT the key from Step A (e.g., `product_id`) and any other keys needed for the final join. Every table in "join.conditions" MUST have a clear join path to the other tables. If you need to show the Product Name, the aggregation step MUST NOT lose the `product_id`.
        - JOIN NAME ACCURACY: In the "join.conditions" array, you MUST use the EXACT names you defined in the "databases" list (e.g., use "Postgres_Sales_Step1", not "Postgres_Sales_DB").
        - DATA NORMALIZATION: The database uses State Abbreviations (e.g., "CA", "NY"). If the user provides a full state name like "California", you MUST use the abbreviation "CA" in your query filters.
        - FIELD NAME ACCURACY: MongoDB field names are CASE-SENSITIVE.
          * In the "Customer" collection, the field is "Customer_ID" (Title Case).
        - ALIAS VERIFICATION: If you use a table alias like `p.ColumnName` in the SELECT, WHERE, or ORDER BY clauses, you MUST ensure that the table with alias `p` is explicitly included in the FROM or JOIN clauses. Never select columns from a table you did not join.
        - STRICT SCHEMA INTEGRITY: You MUST cross-reference every table/collection name with the provided "Database Schemas".
          * CASE SENSITIVITY: MongoDB collection names are CASE-SENSITIVE. Use "Customer" (Singular, Title Case), NOT "customers" or "customer".
          * EXAMPLE: "order_items" and "Order" are in Postgres_Sales_DB. "Product" is in SQL_Inventory_DB.
          * WARNING: You CANNOT join "order_items" and "Product" in a single SQL query because they are in DIFFERENT databases. You must query them separately and link them using placeholders (e.g. SELECT ... FROM Product WHERE Product_ID IN ({{Postgres_Sales_DB.product_id}})).
          * SQL DIALECT WARNING: SQL_Inventory_DB is a Microsoft SQL Server database. You MUST use 'TOP' instead of 'LIMIT' (e.g., SELECT TOP 2 Product_ID ...). Postgres_Sales_DB uses LIMIT.
        - Do not hallucinate columns, tables, or collections. Only use what is explicitly provided in the schema for that specific database name.
        - Do not provide a single colum as a result of a query when the final result is expected to be a table.
        - Include order by in all the queries, when there is any revenue or count order by that column in descending order. Otherwise order by the primary key in ascending order.
        - EXPECTED DETAILS: When combining data from multiple tables (like orders, products, or customers), always retrieve basic descriptive details such as the Customer's First Name, Last Name, Email, and the Product Name whenever possible, even if not explicitly requested.
        - JSON STRUCTURE: The "databases" field MUST be a simple array of objects. NEVER wrap individual entries in quotes or return them as strings inside the array.
        - When there is a single query execution only from QueryExecuter.py then just return the result, no need of doing any joins.
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
    import os
    import json
    
    user_prompt = sys.argv[1] if len(sys.argv) > 1 else "Get total order amount per customer for customers in Phoenix who bought the product Webcam HD"

    # --- Conversational Memory Logic ---
    history_file = "chat_history.json"
    history = []
    
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except Exception:
            history = []

    # Build the contextualized prompt
    contextual_prompt = "Conversation History:\n"
    for turn in history:
        contextual_prompt += f"User: {turn['user']}\nSystem (Previous Action): {turn.get('action', 'Executed query')}\n\n"
    
    contextual_prompt += f"User (Current Query): {user_prompt}\n\n"
    contextual_prompt += "Based on the conversation history above, generate the appropriate query for the Current Query. If the current query uses terms like 'now', 'this', or 'compare', reference the previous queries for context (e.g. apply the new filter to the same tables as before)."

    print("Generating SQL with context...")
    sql_query = sql_generator.generate_sql(system_prompt, contextual_prompt)

    print("Generated SQL:\n")
    print(sql_query)

    with open("llm_output.json", "w") as f:
        f.write(sql_query)
        
    # Update History (Keep last 3 interactions to avoid context limit)
    history.append({"user": user_prompt, "action": "Generated multi-DB query plan"})
    if len(history) > 3:
        history.pop(0)
        
    with open(history_file, "w") as f:
        json.dump(history, f, indent=4)
        
    print("\nSaved generated SQL to llm_output.json")