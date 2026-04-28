import os
import json
import logging
import subprocess
import sys
from typing import AsyncGenerator
from dotenv import load_dotenv

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_master_agent(user_prompt: str) -> AsyncGenerator[dict, None]:
    """
    Sequentially calls the project scripts to process the request.
    1. DBSchemaExtractor.py
    2. multipleDB_QueryGenerator.py
    3. QueryExecutor.py
    4. DataJoiner.py
    """
    try:
        # Step 1: Extract Schema
        yield {"type": "tool_start", "tool": "DBSchemaExtractor", "input": "Extracting database schemas..."}
        subprocess.run([sys.executable, "DBSchemaExtractor.py"], check=True)
        yield {"type": "tool_end", "tool": "DBSchemaExtractor", "status": "success"}
        yield {"type": "token", "content": "✅ Database schemas extracted.\n"}

        # Step 2: Generate Query Plan
        yield {"type": "tool_start", "tool": "QueryGenerator", "input": user_prompt}
        # multipleDB_QueryGenerator.py writes to llm_output.json
        subprocess.run([sys.executable, "multipleDB_QueryGenerator.py", user_prompt], check=True)
        yield {"type": "tool_end", "tool": "QueryGenerator", "status": "success"}
        yield {"type": "token", "content": "✅ Multi-DB query plan generated.\n"}

        # --- DATA GUARDRAILS ---
        if os.path.exists("llm_output.json"):
            with open("llm_output.json", "r") as f:
                plan = json.load(f)
            
            if "error" in plan:
                msg = f"Security Warning: {plan['error']}"
                logger.warning(msg)
                yield {"type": "error", "content": msg}
                return

            if "databases" not in plan:
                msg = "Error: Invalid query plan generated."
                logger.warning(msg)
                yield {"type": "error", "content": msg}
                return

            import re
            forbidden_sql_pattern = re.compile(r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|EXEC|EXECUTE|GRANT|REVOKE|REPLACE|CREATE)\b', re.IGNORECASE)
            schema_tables = ["INFORMATION_SCHEMA", "PG_CATALOG", "PG_TABLES", "SYS.TABLES", "SYS.COLUMNS"]

            for db in plan.get("databases", []):
                db_name = db.get("name", "").lower()
                query = str(db.get("query", "")).strip()
                
                if "mongo" not in db_name:
                    upper_query = query.upper()
                    
                    # 1. Enforce SELECT only
                    if not (upper_query.startswith("SELECT") or upper_query.startswith("WITH")):
                        msg = "Security Warning: Only SELECT queries are permitted. Modifying data is forbidden."
                        logger.warning(msg)
                        yield {"type": "error", "content": msg}
                        return
                        
                    # 2. Forbid any DML/DDL keywords
                    if forbidden_sql_pattern.search(query):
                        msg = "Security Warning: Disallowed SQL operations detected. Only SELECT queries are permitted."
                        logger.warning(msg)
                        yield {"type": "error", "content": msg}
                        return
                    
                    # 3. Forbid schema extraction
                    for st in schema_tables:
                        if st in upper_query:
                            msg = "Security Warning: DB schema extraction is not allowed."
                            logger.warning(msg)
                            yield {"type": "error", "content": msg}
                            return
                else:
                    # MongoDB guardrails: Prevent write operations like $out, $merge
                    if "$out" in query or "$merge" in query:
                        msg = "Security Warning: Data modification operations ($out, $merge) are not allowed in MongoDB queries."
                        logger.warning(msg)
                        yield {"type": "error", "content": msg}
                        return

        # Step 3: Execute Queries
        yield {"type": "tool_start", "tool": "QueryExecutor", "input": "Executing cross-database queries..."}
        # QueryExecutor.py reads llm_output.json and writes to QueryOutput.json
        subprocess.run([sys.executable, "QueryExecutor.py"], check=True)
        yield {"type": "tool_end", "tool": "QueryExecutor", "status": "success"}
        yield {"type": "token", "content": "✅ Queries executed successfully.\n"}

        # Step 4: Join Results
        yield {"type": "tool_start", "tool": "DataJoiner", "input": "Merging results..."}
        # DataJoiner.py reads QueryOutput.json and llm_output.json, writes to FinalResult.json
        subprocess.run([sys.executable, "DataJoiner.py"], check=True)
        yield {"type": "tool_end", "tool": "DataJoiner", "status": "success"}
        yield {"type": "token", "content": "✅ Data merged and finalized.\n"}

        # Step 5: Generate Business Insights
        yield {"type": "tool_start", "tool": "BusinessInsights", "input": "Generating business insights..."}
        subprocess.run([sys.executable, "BusinessInsightsGenerator.py", user_prompt], check=True)
        yield {"type": "tool_end", "tool": "BusinessInsights", "status": "success"}
        yield {"type": "token", "content": "✅ Business insights generated.\n"}

        # Step 6: Load and Send Final Result
        if os.path.exists("FinalResult.json"):
            with open("FinalResult.json", "r") as f:
                final_data = json.load(f)
            
            results = final_data.get("results", [])
            row_count = final_data.get("row_count", 0)

            # Send raw results to UI for table display
            yield {
                "type": "result",
                "tool": "FinalResult",
                "content": results
            }

            # Generate a small summary and markdown table for chat
            yield {"type": "token", "content": f"\n### Final Results ({row_count} rows)\n"}
            
            if results:
                cols = list(results[0].keys())
                header = "| " + " | ".join(cols) + " |"
                sep = "| " + " | ".join(["---"] * len(cols)) + " |"
                table_rows = []
                for r in results[:10]:
                    table_rows.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
                
                table_md = "\n" + header + "\n" + sep + "\n" + "\n".join(table_rows) + "\n"
                if row_count > 10:
                    table_md += f"\n*Displaying first 10 rows. Use 'View Table' for full results.*\n"
                
                yield {"type": "token", "content": table_md}
            else:
                yield {"type": "token", "content": "No results found for the given criteria."}
                
            # Send business insights to UI
            insight_text = ""
            if os.path.exists("insight_output.txt"):
                with open("insight_output.txt", "r", encoding='utf-8') as f:
                    insight_text = f.read()

            if insight_text:
                yield {"type": "insight", "content": f"\n### Business Insights\n{insight_text}\n"}
        else:
            yield {"type": "error", "content": "FinalResult.json was not generated."}

    except Exception as e:
        logger.error(f"Master Agent Error: {e}")
        yield {"type": "error", "content": "An unexpected error occurred while processing your request. Please try again later."}

if __name__ == "__main__":
    import asyncio
    async def test():
        async for chunk in run_master_agent("Get total order amount per customer"):
            print(repr(chunk))
    asyncio.run(test())
