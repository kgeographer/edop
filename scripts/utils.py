import csv
from pathlib import Path

path = Path("app/data/wh_wikipedia_leads.tsv")

rows = []
with path.open(encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter="\t")
    for r in reader:
        text = r["wiki_lead"]
        words = text.split()
        rows.append({
            "id_no": r["id_no"],
            "wh_name": r["wh_name"],
            "wiki_title": r["wiki_title"],
            "chars": len(text),
            "words": len(words),
        })

# sort shortest first
rows.sort(key=lambda r: r["words"])

for r in rows:
    print(
        f"{r['wh_name'][:35]:35s} | "
        f"{r['words']:4d} words | "
        f"{r['chars']:5d} chars | "
        f"{r['wiki_title']}"
    )
