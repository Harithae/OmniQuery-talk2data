import asyncio
from master_agent import is_retail_domain

user_prompt = "Find all customers living in 'CA' who have 'Pending' orders for any product in the 'Category 9' category. Show their full names, the specific product name, the order date, and the current order status."

print("Is retail domain:", is_retail_domain(user_prompt))
