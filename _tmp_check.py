import sqlite3
c = sqlite3.connect("drug_master.db")
c.row_factory = sqlite3.Row
for name in ["글루코파지정", "글루코트정", "그로민캡슐"]:
    rows = c.execute(
        "SELECT category, risk_keyword, indication, ingredient_code, full_name "
        "FROM drug_master WHERE short_name=?", (name,)
    ).fetchall()
    print(f"\n[{name}] {len(rows)}행")
    seen = set()
    for r in rows:
        key = (r["category"], r["risk_keyword"], r["indication"], r["ingredient_code"])
        if key in seen:
            continue
        seen.add(key)
        print(f"  {r['category']:<8} risk={r['risk_keyword']} ind={r['indication']} "
              f"code={r['ingredient_code']} | {(r['full_name'] or '')[:30]}")
