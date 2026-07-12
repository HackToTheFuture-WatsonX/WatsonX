import json, glob, os

# find the latest v4 json
path = "JSON File Extracts/RN-123456_789_10/RN-123456_789_10_v4.json"
with open(path, encoding="utf-8") as f:
    d = json.load(f)

print("=== DATABASE CHECK SUMMARY (cover page results) ===")
for c in d["report_summary"]["database_check_summary"]:
    print(f"  {c['check']:<42} {c['result']:<45} -> {c['status']}")

print()
print("=== OTHER CHECKS (detail pages with source) ===")
for c in d["other_checks"]:
    print(f"  {c['check_name']:<42} {c['result']:<45} -> {c['status']}")
