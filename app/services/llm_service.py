from ollama import Client
import json
import re

client = Client(
  host='http://localhost:11434',
)

def categorize_prompt(txns):
    template = '''
            Classify these {count} transactions:
            {txns}

            **If Type is CREDIT:**
            - SALARY: Regular payroll, salary, or wages.
            - FREELANCE: Income from freelance work, gig work, or side projects (Upwork, Fiverr, etc).
            - REMITTANCE: Inward money from international or local remit services (IME, etc).
            - LOCAL_BUSINESS: Income from local business (kirana shop, merchant) via QR payments, wallet collections, or wallet settlements (eSewa, Khalti, FonePay).
            - INTEREST: Bank interest credits.
            - TRANSFER: General P2P transfers or internal account movements.
            - INVESTMENT_RETURN: Returns from stocks, dividends, or IPO refunds.
            - UNKNOWN: Only use if the description is completely nonsensical.

            **If Type is DEBIT:**
            - SHOPPING: Retail, groceries, malls, and e-commerce (Big Mart, Daraz, etc).
            - LIFESTYLE: Restaurants, cafes, movies, ridesharing (Pathao), and leisure.
            - UTILITIES: Electricity (NEA), Water, Internet (Worldlink), and Phone top-ups.
            - CASH_WITHDRAWAL: ATM or over-the-counter cash outs.
            - INVESTMENT: ASBA/IPO charges, share purchases, or broker payments.
            - WALLET_LOAD: Loading funds into eSewa or Khalti.
            - TAX: TDS or government taxes.
            - DEBT_REPAYMENT: Loan installments (EMI) or credit card payments.
            - UNKNOWN: Only use if the merchant is unidentified.

            ### GUIDELINES
            1. Clean the description by ignoring bank prefixes like "POS TRN FROM:", "FONEPAY::", or "NABIL/".
            2. Focus on the Merchant Name (e.g., "ORCHID COFFEE" is LIFESTYLE; "BHATBHATENI" is SHOPPING).
            3. Be decisive. If "FOOD" or "BURGER" is present, it is LIFESTYLE.
            4. Return ONLY the category name in plain text (e.g., "SALARY"). Do not include explanations.

            RESPOND WITH JSON ARRAY (no other text):
            It should contain the transaction id, category and a confidence score for the category picked on how sure you are. 0.0 for absolutely not sure, 0.5 for confused and 0.95 being absolute sure.
            '''
    return template.format(count=len(txns), txns=txns)

def call_llm(system, data):
    response = client.chat(model='gemma4',think=False, messages=[
    {
        'role': 'system',
        'content': f'{system}',
    },
    {
        'role': 'user',
        'content': f'{data}'
    }
    ])
    return response.message.content

def cleaned_json(response_text):
    # Remove markdown code block markers
    cleaned = re.sub(r'```json\s*', '', response_text)
    cleaned = re.sub(r'```\s*', '', cleaned)
    cleaned = cleaned.strip()
    
    # Parse and return the JSON
    return json.loads(cleaned)


def categorize_txn(transactions):
    system_prompt = 'You are a Financial Data Analyst specializing in the Nepali banking sector. Your task is to categorize bank transaction descriptions into a specific predefined Enum structure.'
    data = categorize_prompt(transactions)
    result = call_llm(system_prompt, data)
    return cleaned_json(result)
    
    
