"""
Standalone test for parser_agent on electricity bill and KYC images.

Usage:
    python tests/test_parser_agent.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.agents.parser_agent import parse_documents

file_paths = {
    "utility_bill": "data/samples/electricity.png",
    "kyc_form": "data/samples/kyc.png",
}

print("=" * 60)
print("Parser Agent Standalone Test")
print("=" * 60)
print()
for doc_type, path in file_paths.items():
    print(f"  {doc_type}: {path}")
print()

result = parse_documents(file_paths, debug=True, applicant_id="TEST-001")

print(json.dumps(result, indent=2, ensure_ascii=False))
print()

output_path = "tests/parser_agent_output.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(f"Output saved to: {output_path}")
print()

print("=" * 60)
for doc_type in file_paths:
    status = result.get("raw_extracted_data", {}).get(doc_type, {}).get("status", "missing")
    print(f"  {doc_type}: {status}")
print("=" * 60)
