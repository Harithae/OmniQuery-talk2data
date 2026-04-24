from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from master_agent import run_master_agent
import uvicorn
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="OmniQuery Master Agent API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Streaming endpoint for the master agent.
    Yields JSON chunks for tokens, tools, and final results.
    """
    if not req.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
        
    async def event_generator():
        try:
            async for chunk in run_master_agent(req.message):
                # Yield as JSON string with a newline for easy parsing
                yield json.dumps(chunk) + "\n"
        except Exception as e:
            print(f"Streaming error: {e}")
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
