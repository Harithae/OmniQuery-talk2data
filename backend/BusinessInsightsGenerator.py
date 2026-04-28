import os
import json
import sys
from groq import Groq
from dotenv import load_dotenv

load_dotenv(override=True)

def generate_insights(user_prompt: str, data_json_str: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise Exception("GROQ_API_KEY not set")
    
    client = Groq(api_key=api_key)
    model = os.getenv("MODEL_NAME", "llama3-8b-8192") # default model if not set
    
    system_prompt = """
        You are an expert AI business analyst. Your task is to analyze the user's prompt and the provided data, and generate actionable business insights.
        Focus on identifying top-performing metrics, revenue contributions, trends, and anomalies.

        AI Insight: "[A brief, impactful sentence summarizing the core finding or trend from the data]"
        Actionable Item: "[A clear, practical recommendation or next step based on the insight]"

        Sample interaction:
        User Prompt: Which products sold the most this week?
        System returns:
        Top 5 selling products.
        Revenue contribution.
        Sales trend chart.
        AI Insight: "Wireless Earbuds, Phone Chargers, and Smart Watches contributed 34% of this week’s revenue, with accessories sales increasing 12% over last week."
        Actionable Item: "Increase inventory of Wireless Earbuds and Phone Chargers by 20% to meet rising demand, and run a targeted promotion on smart watches to capitalize on the trend."

        Format your response exactly as:
        AI Insight: "<Your insight here>"
        Actionable Item: "<Your recommendation here>"
        Do not include any conversational filler.
    """

    # Truncate data if it's too large to fit in context window
    if len(data_json_str) > 10000:
        data_json_str = data_json_str[:10000] + "... [truncated]"

    content = f"User Prompt: {user_prompt}\nData:\n{data_json_str}"
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ],
        temperature=0.3
    )
    
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python BusinessInsightsGenerator.py <user_prompt>")
        sys.exit(1)
        
    user_prompt = sys.argv[1]
    
    try:
        with open("FinalResult.json", "r") as f:
            final_data = json.load(f)
            
        results = final_data.get("results", [])
        data_str = json.dumps(results)
        
        insight = generate_insights(user_prompt, data_str)
        
        # Save to a file so master_agent can read it
        with open("insight_output.txt", "w", encoding='utf-8') as f:
            f.write(insight)
            
        print("Insight generated successfully.")
    except Exception as e:
        print(f"Error generating insights: {e}")
        sys.exit(1)
