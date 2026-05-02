import sys
sys.path.insert(0, "backend")

from dotenv import load_dotenv
load_dotenv("backend/.env", override=True)

from llm_client import get_llm_client

print("Testing LLM Configuration System")
print("=" * 50)

# Test default configuration
client = get_llm_client()
print(f"Provider: {client.get_provider()}")
print(f"Model: {client.get_model_name()}")
print()

# Test a simple completion
print("Testing chat completion...")
try:
    response = client.chat_completion(
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Respond in one sentence."},
            {"role": "user", "content": "What is 2+2?"}
        ],
        temperature=0,
        max_tokens=50
    )
    print(f"Response: {response}")
    print("\n✅ Configuration test PASSED")
except Exception as e:
    print(f"❌ Error: {e}")
