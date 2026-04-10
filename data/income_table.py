from tabulate import tabulate

def display_transactions_table(transactions, columns=None):
    """
    Display transactions in a nicely formatted table.
    
    Args:
        transactions: List of transaction dictionaries
        columns: List of column names to display (defaults to all keys)
    """
    if not transactions:
        print("No transactions to display")
        return
    
    # Use all keys from first transaction if columns not specified
    if columns is None:
        columns = list(transactions[0].keys())
    
    # Extract only the specified columns
    table_data = []
    for txn in transactions:
        row = [txn.get(col, 'N/A') for col in columns]
        table_data.append(row)
    
    # Print as table
    print(tabulate(table_data, headers=columns, tablefmt='grid'))
