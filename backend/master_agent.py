import os
import json
import logging
import subprocess
import sys
from typing import AsyncGenerator
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def run_script(script_name, args=None):
    """Runs a python script with retry logic."""
    cmd = [sys.executable, script_name]
    if args:
        cmd.extend(args)
    logger.info(f"Running script: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

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
        run_script("DBSchemaExtractor.py")
        yield {"type": "tool_end", "tool": "DBSchemaExtractor", "status": "success"}
        yield {"type": "token", "content": "✅ Database schemas extracted.\n"}

        # Step 2: Generate Query Plan
        yield {"type": "tool_start", "tool": "QueryGenerator", "input": user_prompt}
        # multipleDB_QueryGenerator.py writes to llm_output.json
        run_script("multipleDB_QueryGenerator.py", [user_prompt])
        yield {"type": "tool_end", "tool": "QueryGenerator", "status": "success"}
        yield {"type": "token", "content": "✅ Multi-DB query plan generated.\n"}

        # Step 3: Execute Queries
        yield {"type": "tool_start", "tool": "QueryExecutor", "input": "Executing cross-database queries..."}
        # QueryExecutor.py reads llm_output.json and writes to QueryOutput.json
        run_script("QueryExecutor.py")
        yield {"type": "tool_end", "tool": "QueryExecutor", "status": "success"}
        yield {"type": "token", "content": "✅ Cross-DB queries executed.\n"}

        # Step 4: Join Data
        yield {"type": "tool_start", "tool": "DataJoiner", "input": "Merging and formatting results..."}
        # DataJoiner.py reads QueryOutput.json and writes to FinalResult.json
        run_script("DataJoiner.py")
        yield {"type": "tool_end", "tool": "DataJoiner", "status": "success"}
        yield {"type": "token", "content": "✅ Results merged and formatted.\n"}

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
            print(repr(chunk))
    asyncio.run(test())
