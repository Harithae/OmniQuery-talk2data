import os
import json
import logging
import subprocess
import sys
import time
from typing import AsyncGenerator
from dotenv import load_dotenv
from retry_utils import run_command_with_heartbeat
from llm_client import get_llm_client

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def is_retail_domain(user_prompt: str) -> bool:
    """
    Checks if the user prompt is related to the retail domain.
    """
    try:
        # Always use Groq for this check (fast and cheap)
        client = get_llm_client(provider="groq", model="llama-3.1-8b-instant")
        
        system_prompt = (
            "You are a domain validator for a Retail Management System. "
            "Your job is to determine if a query is related to RETAIL BUSINESS. "
            "Valid retail topics include: \n"
            "- Customers (names, locations, emails, history)\n"
            "- Orders & Sales (amounts, dates, statuses, invoices, payments)\n"
            "- Products & Inventory (names, categories, prices, stock levels)\n"
            "- Logistics (shipments, deliveries, stores, areas)\n\n"
            "Queries about specific locations (e.g., 'in CA', 'near Chicago') are VALID if they relate to customers or stores. "
            "Even if a query mentions specific categories like 'Category 9' or statuses like 'Pending', it is still RETAIL. "
            "Respond with 'YES' if it is related, and 'NO' otherwise. Return ONLY the word 'YES' or 'NO'."
        )
        
        decision = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
            max_tokens=10
        )
        
        logger.info(f"Domain validation decision for '{user_prompt[:50]}...': {decision}")
        return "YES" in decision.upper()
    except Exception as e:
        logger.error(f"Domain check error: {e}")
        return True  # Fallback to proceed if check fails

async def run_master_agent(user_prompt: str) -> AsyncGenerator[dict, None]:
    """
    Sequentially calls the project scripts to process the request.
    1. DBSchemaExtractor.py
    2. multipleDB_QueryGenerator.py
    3. QueryExecutor.py
    4. DataJoiner.py
    """
    try:
        # Step 0: Domain Guardrail
        if not is_retail_domain(user_prompt):
            yield {
                "type": "token", 
                "content": "I'm sorry, but I can only help with queries related to the retail domain (Customers, Sales, Order, Products and Inventory information). Please try asking something else!"
            }
            return

        # Step 1: Extract Schema (Conditional)
        schema_dir = "DBSchemas"
        if not os.path.exists(schema_dir) or not os.listdir(schema_dir):
            yield {"type": "tool_start", "tool": "DBSchemaExtractor", "input": "Extracting database schemas..."}
            async for hb in run_command_with_heartbeat([sys.executable, "DBSchemaExtractor.py"], "DBSchemaExtractor"):
                yield hb
            yield {"type": "tool_end", "tool": "DBSchemaExtractor", "status": "success"}
        else:
            yield {"type": "status", "content": "Using cached database schemas."}

        # Step 1.5: Build Knowledge Base (Conditional)
        if not os.path.exists("DBSchemas/knowledgebase_output.json"):
            yield {"type": "tool_start", "tool": "KnowledgeBaseBuilder", "input": "Generating knowledge base (initial setup)..."}
            async for hb in run_command_with_heartbeat([sys.executable, "knowledgebase_builder.py"], "KnowledgeBaseBuilder"):
                yield hb
            yield {"type": "tool_end", "tool": "KnowledgeBaseBuilder", "status": "success"}
        else:
            yield {"type": "status", "content": "Using existing knowledge base."}

        # Step 2: Generate Query Plan
        yield {"type": "tool_start", "tool": "QueryGenerator", "input": user_prompt}
        async for hb in run_command_with_heartbeat([sys.executable, "multipleDB_QueryGenerator.py", user_prompt], "QueryGenerator"):
            yield hb
        yield {"type": "tool_end", "tool": "QueryGenerator", "status": "success"}

        # --- DATA GUARDRAILS ---
        if os.path.exists("Outputs/llm_output.json"):
            with open("Outputs/llm_output.json", "r") as f:
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
        async for hb in run_command_with_heartbeat([sys.executable, "QueryExecutor.py"], "QueryExecutor"):
            yield hb
        yield {"type": "tool_end", "tool": "QueryExecutor", "status": "success"}

        # Step 4: Join Results
        yield {"type": "tool_start", "tool": "DataJoiner", "input": "Merging results..."}
        async for hb in run_command_with_heartbeat([sys.executable, "DataJoiner.py"], "DataJoiner"):
            yield hb
        yield {"type": "tool_end", "tool": "DataJoiner", "status": "success"}

        # Step 5: Generate Business Insights
        yield {"type": "tool_start", "tool": "BusinessInsights", "input": "Generating business insights..."}
        async for hb in run_command_with_heartbeat([sys.executable, "BusinessInsightsGenerator.py", user_prompt], "BusinessInsights"):
            yield hb
        yield {"type": "tool_end", "tool": "BusinessInsights", "status": "success"}
        yield {"type": "token", "content": "✅ Business insights generated.\n"}

        # Step 6: Load and Send Final Result
        if os.path.exists("Outputs/FinalResult.json"):
            with open("Outputs/FinalResult.json", "r") as f:
                final_data = json.load(f)
            
            results = final_data.get("results", [])
            row_count = final_data.get("row_count", 0)

            # Send raw results to UI for table display
            yield {
                "type": "result",
                "tool": "FinalResult",
                "content": results
            }

            if results:
                # Generate a small summary and markdown table for chat
                yield {"type": "token", "content": f"\n### Final Results ({row_count} rows)\n"}

                cols = list(results[0].keys())
                header = "| " + " | ".join(cols) + " |"
                sep = "| " + " | ".join(["---"] * len(cols)) + " |"
                table_rows = []
                for r in results[:10]:
                    table_rows.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
                
                table_md = "\n" + header + "\n" + sep + "\n" + "\n".join(table_rows) + "\n"
                if row_count > 10:
                    table_md += f"\n*Displaying first 10/{row_count} rows. Use 'View Table' for full results.*\n"
                
                yield {"type": "token", "content": table_md}
            else:
                yield {"type": "token", "content": "I couldn't find any data matching your request. Please try a different query."}
                
            # Send business insights to UI
            insight_text = ""
            if os.path.exists("Outputs/insight_output.txt"):
                with open("Outputs/insight_output.txt", "r", encoding='utf-8') as f:
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