"""
distinct 대표 선택 문제 확인:
와파린/레보티록신/콜히친이 일반명코드 있는 행을 가지고 있는데
distinct에서 STD: 행이 대표로 뽑혔는지 검사.
실행: python check_warfarin.py
"""
from app.database import get_conn, init_db

init_db()
TARGETS = ["와파린", "레보티록신", "콜히친", "푸로세미드"]

with get_conn() as conn:
    for name in TARGETS:
        rows = conn.execute("""
            SELECT short_name, ingredient_code, kd_code
            FROM drug_master
            WHERE short_name LIKE ?
            ORDER BY ingredient_code
        """, (f"%{name}%",)).fetchall()

        total = len(rows)
        with_code = [r for r in rows if r["ingredient_code"]
                     and not r["ingredient_code"].startswith("STD:")]
        print(f"\n[{name}] 총 {total}행, 일반명코드 있는 행 {len(with_code)}개")
        # 샘플 5개
        for r in rows[:5]:
            print(f"   {r['short_name'][:28]:30s} {r['ingredient_code']}")
        if with_code:
            print(f"   → 일반명코드 예: {with_code[0]['ingredient_code']} "
                  f"({with_code[0]['short_name'][:20]})")
