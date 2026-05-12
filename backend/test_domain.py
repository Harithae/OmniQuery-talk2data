from master_agent import is_retail_domain
from llm_client import get_llm_client

user_prompt = "Find all customers living in 'CA' who have 'Pending' orders for any product in the 'Category 9' category. Show their full names, the specific product name, the order date, and the current order status."

try:
    client = get_llm_client(provider="groq", model="llama-3.1-8b-instant")
    system_prompt = (
        "You are a domain validator. Determine if the user's query is related to RETAIL. "
        "Valid retail topics for this system include: Customers, Orders, Sales, Products, Stores, Inventory, "
        "Payments, Invoices, Shipments, Deliveries, Wish Lists, Browsing/View History, Product Features (color, size), and Product Categories (demographics). "
        "Note: Queries asking for geographical locations of customers or stores (e.g., 'nearby New York', 'in California') ARE valid retail queries. "
        "Respond with 'YES' if it is related, and 'NO' otherwise. Return ONLY 'YES' or 'NO'."
    )
    decision = client.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0,
        max_tokens=5
    )
    print("Decision output:", repr(decision))
except Exception as e:
    print("Error:", e)
