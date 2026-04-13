import asyncio
import json
from app.services.orchestrator import app
from app.models.state import AgentState

async def run_test():
    # Load transactions from JSON
    with open("data/transactions.json", "r") as f:
        data = json.load(f)
        raw_transactions = data.get("transactions", [])

    # 1. Define the starting point (Initial State)
        # 1. Define the starting point (Initial State)
    initial_state: AgentState = {
        "file_paths": {"citizenship": "data/lalpurja.jpeg", "lalpurja": "data/lalpurja.jpeg","tax":"data/tax.webp"},
        "raw_transactions": raw_transactions
    }

    # print("--- 🚀 Starting Pipeline Test ---")
    
    # 2. Invoke the graph
    # .ainvoke() is the async way to run the whole graph from start to finish
    try:
        final_state = await app.ainvoke(initial_state)
        
        # 3. Inspect the results
        # print("\n--- ✅ Test Complete ---")
        # print(f"Final Status: {final_state.get('status')}")
        
        print(final_state)
        
    except Exception as e:
        print(f"--- ❌ Pipeline Failed: {e} ---")



if __name__ == "__main__":
    asyncio.run(run_test())


