from app.services.income_categorizer import assign_tnx_category
from data.income_data import DebitCategory, CreditCategory
from app.services.llm_service import categorize_txn
import json
from tabulate import tabulate

from data.income_table import display_transactions_table

all_txns = {}

# Read the JSON
with open('./data/transactions.json') as j:
    transactions = json.load(j)
    all_txns = transactions['transactions']

# Add categories with the confidence score
for tran in all_txns:
    tran['category'],tran['category_confidence'] = assign_tnx_category(tran)

# Create a new list with only unknown categories
unknown_txns = [tran for tran in all_txns if tran['category'] == DebitCategory.UNKNOWN or tran['category'] == CreditCategory.UNKNOWN]

categozied_llm = categorize_txn(unknown_txns)

# Join LLM results back into all_txns
# Create a lookup dict for LLM results by id
llm_lookup = {item['id']: {'category': item['category'], 'confidence': item['confidence']} for item in categozied_llm}

# Update all_txns with LLM categorizations
final_transactions = []
for tran in all_txns:
    if tran['id'] in llm_lookup:
        tran['category'] = llm_lookup[tran['id']]['category']
        tran['category_confidence'] = llm_lookup[tran['id']]['confidence']
    # Convert enum to string if necessary
    if hasattr(tran['category'], 'value'):
        tran['category'] = tran['category'].value
    final_transactions.append(tran)

print(f"Total transactions: {len(final_transactions)}")


# Save the transaction for testing for now
with open("./data/categorized_transactions.json", "w") as file:
    json.dump(final_transactions, file)

display_transactions_table(final_transactions)