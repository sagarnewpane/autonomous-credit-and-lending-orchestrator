import json
import app.services.income_profile_calculations as calculations
from data.income_table import display_transactions_table

data = {}
with open('./data/categorized_transactions.json') as j:
    data = json.load(j)


print(calculations.generate_income_profile(data))

display_transactions_table(data)