import os
import json
import logging
import subprocess
import sys
from typing import AsyncGenerator
from dotenv import load_dotenv

load_dotenv()

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

        # Step 5: Load and Send Final Result
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
        else:
            yield {"type": "error", "content": "FinalResult.json was not generated."}

    except subprocess.CalledProcessError as e:
        logger.error(f"Script execution failed: {e}")
        yield {"type": "error", "content": f"Pipeline failed at script execution: {e}"}
    except Exception as e:
        logger.error(f"Master Agent Error: {e}")
        yield {"type": "error", "content": str(e)}

if __name__ == "__main__":
    import asyncio
    async def test():
        async for chunk in run_master_agent("Get total order amount per customer"):
            print(chunk)
    asyncio.run(test())
