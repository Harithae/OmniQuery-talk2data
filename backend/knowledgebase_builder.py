import os
import json
import pymongo
import urllib.parse
import time
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from retry_utils import retry_decorator
from llm_client import get_llm_client

load_dotenv(override=True)

class KBBuilder:
    def __init__(self, llm_client=None):
        """
        Initialize KB Builder with an LLM client.
        
        Args:
            llm_client: Optional LLMClient instance. If None, creates one from env config.
        """
        self.llm_client = llm_client or get_llm_client()

    @retry_decorator(retries=3, delay=5)
    def get_llm_annotation(self, table_name, schema_info, sample_data):
        time.sleep(1.5) # Rate limit protection
        prompt = f"""
        You are a database documentation expert. Your task is to provide a structured description for the following database table.
        
        Table Name: {table_name}
        Schema: {json.dumps(schema_info, indent=2)}
        Sample Data: {json.dumps(sample_data, indent=2)}
        
        Return a JSON object with the following structure:
        {{
            "table_description": "A detailed description of what this table stores and its purpose in the business.",
            "columns": {{
                "column_name": {{
                    "description": "A detailed description of the column and what it represents.",
                    "example_value": "An actual example value for this column from the provided sample data (use the exact data type/format found in the database)."
                }}
            }}
        }}
        
        Rules:
        - Return ONLY valid JSON.
        - Be concise but informative.
        - The "example_value" MUST come from the provided Sample Data. If a column has only nulls in the samples, use null.
        """
        
        try:
            content = self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates database documentation in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            print(f"Error annotating table {table_name}: {e}")
            cols = schema_info.get('columns', schema_info.get('fields', []))
            return {
                "table_description": "No description available.",
                "columns": {col['name']: {"description": "No description available.", "example_value": None} for col in cols if isinstance(col, dict) and 'name' in col}
            }

def fetch_sql_samples(engine, table_name, limit=3):
    try:
        from decimal import Decimal
        with engine.connect() as conn:
            if "mssql" in str(engine.url):
                query = text(f"SELECT TOP {limit} * FROM [{table_name}]")
            else:
                query = text(f'SELECT * FROM "{table_name}" LIMIT {limit}')
            
            result = conn.execute(query)
            rows = [dict(row._mapping) for row in result]
            
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, Decimal):
                        row[k] = float(v)
                    elif hasattr(v, 'isoformat'):
                        row[k] = v.isoformat()
            return rows
    except Exception as e:
        print(f"Error fetching samples for {table_name}: {e}")
        return []

def fetch_mongo_samples(db, collection_name, limit=3):
    try:
        from bson import Decimal128, ObjectId
        from datetime import datetime
        collection = db[collection_name]
        samples = list(collection.find().limit(limit))
        
        def serialize_mongo(obj):
            if isinstance(obj, list):
                return [serialize_mongo(i) for i in obj]
            if isinstance(obj, dict):
                return {k: serialize_mongo(v) for k, v in obj.items()}
            if isinstance(obj, Decimal128):
                return float(str(obj))
            if isinstance(obj, ObjectId):
                return str(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        return serialize_mongo(samples)
    except Exception as e:
        print(f"Error fetching mongo samples for {collection_name}: {e}")
        return []

def main():
    builder = KBBuilder()
    kb = {"databases": {}}
    
    schema_dir = "DBSchemas"
    if not os.path.exists(schema_dir):
        print(f"Schema directory {schema_dir} not found. Run DBSchemaExtractor.py first.")
        return

    pg_conn_str = None
    pg_user = os.getenv("POSTGRES_USER")
    pg_pass = os.getenv("POSTGRES_PASSWORD")
    pg_host = os.getenv("POSTGRES_HOST")
    pg_port = os.getenv("POSTGRES_PORT")
    pg_db = os.getenv("POSTGRES_DB")
    if pg_user and pg_pass and pg_host and pg_port and pg_db:
        password = urllib.parse.quote_plus(pg_pass)
        pg_conn_str = f"postgresql://{pg_user}:{password}@{pg_host}:{pg_port}/{pg_db}"
    
    sql_conn_str = os.getenv("SQLSERVER_CONNECTION_STRING")
    mssql_conn_str = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(sql_conn_str)}" if sql_conn_str else None
    
    mongo_uri = os.getenv("MONGO_URI")
    mongo_db_name = os.getenv("MONGO_DB")
    
    for filename in os.listdir(schema_dir):
        if not filename.endswith(".json"):
            continue
            
        db_name = filename.replace("_Schema.json", "")
        print(f"Processing database: {db_name}...")
        
        with open(os.path.join(schema_dir, filename), "r") as f:
            schema = json.load(f)
            
        kb["databases"][db_name] = {"tables": {}}
        
        engine = None
        mongo_db = None
        
        if "Postgres" in db_name and pg_conn_str:
            engine = create_engine(pg_conn_str)
        elif "SQL_Inventory" in db_name and mssql_conn_str:
            engine = create_engine(mssql_conn_str)
        elif "Mongo" in db_name and mongo_uri:
            client = pymongo.MongoClient(mongo_uri)
            mongo_db = client[mongo_db_name]
            
        if "tables" in schema:
            for table_name, table_schema in schema["tables"].items():
                print(f"  Annotating table: {table_name}...")
                sample_data = fetch_sql_samples(engine, table_name) if engine is not None else []
                annotation = builder.get_llm_annotation(table_name, table_schema, sample_data)
                kb["databases"][db_name]["tables"][table_name] = annotation
                
        if "collections" in schema:
            for coll_name, coll_schema in schema["collections"].items():
                print(f"  Annotating collection: {coll_name}...")
                sample_data = fetch_mongo_samples(mongo_db, coll_name) if mongo_db is not None else []
                annotation = builder.get_llm_annotation(coll_name, coll_schema, sample_data)
                kb["databases"][db_name]["tables"][coll_name] = annotation

    with open("DBSchemas/knowledgebase_output.json", "w") as f:
        json.dump(kb, f, indent=4)
    
    print("Knowledge base generated and saved to DBSchemas/knowledgebase_output.json")

if __name__ == "__main__":
    main()
