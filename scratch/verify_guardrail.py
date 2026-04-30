import os, sys
sys.path.insert(0, "backend")
from dotenv import load_dotenv
load_dotenv("backend/.env", override=True)
from groq import Groq

api_key = os.getenv("GROQ_API_KEY")
model = "llama-3.1-8b-instant"
print("Model:", model)

client = Groq(api_key=api_key)

prompts = [
    ("get me top 5 customers",      True),
    ("show total sales by region",  True),
    ("list all products in stock",  True),
    ("what is the weather today",   False),
    ("tell me a joke",              False),
]

all_ok = True
for prompt, expected in prompts:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a domain validator. Determine if the user query is related to RETAIL (Customers, Orders, Sales, Products, Inventory). Respond with YES or NO only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=5
    )
    decision = response.choices[0].message.content.strip().upper()
    allowed = "YES" in decision
    status = "OK" if allowed == expected else "WRONG"
    if status == "WRONG":
        all_ok = False
    print(f"  [{status}] raw={repr(decision):8}  expected={'ALLOW' if expected else 'BLOCK'}  prompt={prompt}")

print()
print("All correct:", all_ok)
