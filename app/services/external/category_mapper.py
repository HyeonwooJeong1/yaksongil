"""
한국 표준 약효분류번호 → (카테고리, 적응증/위험키워드) 매핑.

약효분류번호는 약가마스터 / DUR / 식약처 데이터에 공통으로 포함된다.
이 매핑 하나로 4-5만 개 약물을 자동 분류 가능.

참고:
- 100번대: 신경계/감각기관
- 200번대: 개별기관계 (순환, 호흡, 소화, 호르몬 등)
- 300번대: 대사성 (혈액, 영양, 간, 당뇨 등)
- 400번대: 조직세포 (항암, 면역)
- 600번대: 항생물질, 화학요법
"""
import re

# (카테고리, 키워드)
# warning: 응급 시 의료진이 즉시 인지해야 할 약물
# normal:  일반 약물 — 적응증 표시
ATC_MAP: dict[str, tuple[str, str]] = {
    # ──────── warning (응급 위험 약물) ────────
    "112": ("warning", "호흡억제"),   # 최면진정제 (벤조다이아제핀 등)
    "116": ("warning", "낙상"),        # 정신신경용제 (항정신병약, 항우울제)
    "211": ("warning", "부정맥"),      # 강심제 (디곡신 등)
    "212": ("warning", "부정맥"),      # 부정맥용제
    "213": ("warning", "전해질"),      # 이뇨제 (저칼륨/저나트륨)
    "244": ("warning", "부신저하"),    # 부신피질호르몬제 (스테로이드)
    "332": ("warning", "응고"),        # 지혈제
    "333": ("warning", "출혈"),        # 혈액응고저지제 (와파린, 헤파린, DOAC)
    "334": ("warning", "출혈"),        # 혈전용해제 (tPA 등)
    "346": ("warning", "저혈당"),      # 당뇨병용제 (구분류 - 인슐린)
    "396": ("warning", "저혈당"),      # 당뇨병용제 (경구약 포함)
    "421": ("warning", "골수억제"),    # 항악성종양제
    "422": ("warning", "감염위험"),    # 면역억제제

    # ──────── normal (일반 약물) ────────
    "111": ("normal", "마취"),
    "113": ("normal", "항전간"),
    "114": ("normal", "진통"),         # 해열·진통·소염제
    "115": ("normal", "각성"),
    "117": ("normal", "자율신경"),
    "118": ("normal", "진경"),
    "119": ("normal", "항히스타민"),

    "214": ("normal", "혈관확장"),
    "215": ("normal", "고지혈"),
    "216": ("normal", "혈압강하"),
    "217": ("normal", "고혈압"),       # 혈압강하제 (ACE-I, ARB, CCB 등)
    "218": ("normal", "고지혈"),       # 동맥경화용제 (스타틴)
    "219": ("normal", "순환기"),
    "221": ("normal", "호흡촉진"),
    "222": ("normal", "진해거담"),
    "223": ("normal", "함소"),
    "224": ("normal", "진통"),
    "225": ("normal", "천식"),         # 기관지확장제
    "229": ("normal", "호흡기"),
    "231": ("normal", "위산"),         # 제산제
    "232": ("normal", "위산"),         # 소화성궤양용제 (PPI, H2차단제)
    "233": ("normal", "정장"),
    "234": ("normal", "변비"),
    "235": ("normal", "소화"),
    "239": ("normal", "소화기"),
    "241": ("normal", "호르몬"),
    "242": ("normal", "갑상선"),
    "243": ("normal", "스테로이드"),
    "245": ("normal", "호르몬"),
    "246": ("normal", "호르몬"),
    "247": ("normal", "호르몬"),
    "249": ("normal", "호르몬"),
    "251": ("normal", "비뇨"),
    "252": ("normal", "자궁"),
    "259": ("normal", "비뇨"),
    "261": ("normal", "외용소독"),
    "264": ("normal", "외용소염"),
    "269": ("normal", "외용"),
    "271": ("normal", "치과"),
    "281": ("normal", "안과"),
    "282": ("normal", "이비과"),

    "311": ("normal", "비타민"),
    "312": ("normal", "비타민"),
    "313": ("normal", "비타민"),
    "314": ("normal", "비타민"),
    "315": ("normal", "비타민"),
    "316": ("normal", "비타민"),
    "317": ("normal", "비타민"),
    "319": ("normal", "칼슘"),
    "321": ("normal", "무기질"),
    "322": ("normal", "당류"),
    "323": ("normal", "유기산"),
    "324": ("normal", "아미노산"),
    "331": ("normal", "혈액대용"),
    "335": ("normal", "혈관강화"),
    "339": ("normal", "혈액"),
    "341": ("normal", "간장"),
    "342": ("normal", "해독"),
    "344": ("normal", "통풍"),
    "345": ("normal", "효소"),
    "347": ("normal", "대사"),
    "349": ("normal", "대사"),

    "392": ("normal", "변비"),
    "393": ("normal", "알레르기"),
    "394": ("normal", "자율신경"),
    "395": ("normal", "항히스타민"),
    "399": ("normal", "대사"),

    "611": ("normal", "항생제"),
    "612": ("normal", "항생제"),
    "613": ("normal", "항생제"),
    "614": ("normal", "항진균"),
    "615": ("normal", "항결핵"),
    "618": ("normal", "항생제"),
    "619": ("normal", "항생제"),
    "620": ("normal", "화학요법"),
    "621": ("normal", "설파"),
    "624": ("normal", "항균"),
    "625": ("normal", "항원충"),
    "629": ("normal", "화학요법"),
}


def map_atc_code(atc_code: str) -> tuple[str, str]:
    """
    한국 약효분류번호로 (카테고리, 키워드) 결정.
    매핑이 없으면 ('normal', '기타')로 기본 분류.

    atc_code: 3자리 숫자 문자열 (예: "217"). 4자리 이상이어도 앞 3자리 사용.
    """
    if not atc_code:
        return ("normal", "기타")
    key = str(atc_code).strip()[:3]
    return ATC_MAP.get(key, ("normal", "기타"))


# ──────── 국제 ATC 코드 매핑 (약가마스터용) ────────
# ATC: WHO 국제표준 의약품 분류 코드 (예: C09AA01 = 에날라프릴)
# 가장 긴 매칭부터 시도 (5자리 → 4자리 → 3자리 → 1자리)
INTL_ATC_MAP: dict[str, tuple[str, str]] = {
    # ── WARNING (응급 위험 약물) ──
    "A10":   ("warning", "저혈당"),     # 당뇨병용제 (인슐린 + 경구약)
    # B01(항혈전제)은 4자리로 세분화 — 'X(기타)' 하위코드는 모호하므로 warning 제외.
    # 한약재가 B01AX를 달고 있어 출혈 오분류 발생 → AX는 normal로.
    "B01AA": ("warning", "출혈"),        # 비타민K 길항제 (와파린)
    "B01AB": ("warning", "출혈"),        # 헤파린
    "B01AC": ("warning", "출혈"),        # 항혈소판제 (아스피린, 클로피도그렐)
    "B01AD": ("warning", "출혈"),        # 효소 (혈전용해제)
    "B01AE": ("warning", "출혈"),        # 직접 트롬빈 억제제 (DOAC)
    "B01AF": ("warning", "출혈"),        # 직접 Xa 억제제 (DOAC)
    "B02":   ("warning", "응고"),        # 지혈제
    "C01":   ("warning", "부정맥"),      # 강심제 / 부정맥용제 (디곡신, 아미오다론)
    "C03":   ("warning", "전해질"),      # 이뇨제
    "H02":   ("warning", "부신저하"),    # 부신피질호르몬 (스테로이드)
    "L01":   ("warning", "골수억제"),    # 항암제
    "L04":   ("warning", "감염위험"),    # 면역억제제
    "N02A":  ("warning", "호흡억제"),    # 마약성 진통제
    "N03":   ("warning", "낙상"),        # 항전간제
    "N05A":  ("warning", "낙상"),        # 항정신병약
    "N05B":  ("warning", "낙상"),        # 항불안제
    "N05C":  ("warning", "호흡억제"),    # 수면제

    # ── NORMAL (일반 약물) ──
    "A02":   ("normal", "위산"),         # 산관련질환용제 (PPI, H2)
    "A03":   ("normal", "위장운동"),
    "A04":   ("normal", "구토"),
    "A05":   ("normal", "담즙"),
    "A06":   ("normal", "변비"),
    "A07":   ("normal", "설사"),
    "A09":   ("normal", "소화효소"),
    "A11":   ("normal", "비타민"),
    "A12":   ("normal", "무기질"),
    "A14":   ("normal", "단백동화"),
    "A16":   ("normal", "대사"),
    "B03":   ("normal", "빈혈"),
    "C02":   ("normal", "고혈압"),       # 혈압강하제 (구분류)
    "C04":   ("normal", "혈관확장"),
    "C05":   ("normal", "정맥약"),
    "C07":   ("normal", "고혈압"),       # 베타차단제
    "C08":   ("normal", "고혈압"),       # 칼슘차단제
    "C09":   ("normal", "고혈압"),       # ACE-I / ARB
    "C10":   ("normal", "고지혈"),       # 지질대사조절제 (스타틴)
    "D":     ("normal", "피부"),
    "G01":   ("normal", "부인과"),
    "G02":   ("normal", "산부인과"),
    "G03":   ("normal", "성호르몬"),
    "G04":   ("normal", "비뇨"),
    "H01":   ("normal", "뇌하수체"),
    "H03":   ("normal", "갑상선"),
    "H04":   ("normal", "췌장호르몬"),
    "H05":   ("normal", "칼슘대사"),
    "J01":   ("normal", "항생제"),
    "J02":   ("normal", "항진균"),
    "J04":   ("normal", "항결핵"),
    "J05":   ("normal", "항바이러스"),
    "J06":   ("normal", "면역혈청"),
    "J07":   ("normal", "백신"),
    "M01":   ("normal", "진통"),         # NSAIDs
    "M02":   ("normal", "외용진통"),
    "M03":   ("normal", "근이완"),
    "M04":   ("normal", "통풍"),
    "M05":   ("normal", "골다공증"),
    "N01":   ("normal", "마취"),
    "N02B":  ("normal", "진통"),         # 비마약성 진통제
    "N04":   ("normal", "파킨슨"),
    "N06A":  ("normal", "항우울"),
    "N06D":  ("normal", "치매"),
    "N07":   ("normal", "기타신경계"),
    "P01":   ("normal", "항원충"),
    "P02":   ("normal", "항기생충"),
    "P03":   ("normal", "외부기생충"),
    "R01":   ("normal", "비강"),
    "R02":   ("normal", "인후"),
    "R03":   ("normal", "천식"),
    "R05":   ("normal", "진해거담"),
    "R06":   ("normal", "항히스타민"),
    "S01":   ("normal", "안과"),
    "S02":   ("normal", "이과"),
    "V":     ("normal", "기타"),
}


def map_intl_atc(atc: str) -> tuple[str, str]:
    """
    국제 ATC 코드로 (카테고리, 키워드) 결정.
    가장 긴 매칭부터 시도 (5자리 → 4자리 → 3자리 → 1자리).

    안전장치: 4번째 글자가 'X'(WHO ATC상 '기타' 그룹)인 경우,
    3자리 매핑이 warning이어도 normal로 강등. (모호 분류로 인한 오탐 방지)
    """
    if not atc:
        return ("normal", "기타")
    key = str(atc).strip().upper()

    # 4자리 ATC의 4번째 글자가 X면 '기타' 하위그룹 → warning 신뢰 불가
    is_other_group = len(key) >= 4 and key[3] == "X"

    for length in (5, 4, 3, 1):
        prefix = key[:length]
        if prefix in INTL_ATC_MAP:
            cat, kw = INTL_ATC_MAP[prefix]
            # 정확히 그 X-코드를 명시 매핑한 게 아니라면, X그룹은 warning 강등
            if cat == "warning" and is_other_group and length < 4:
                return ("normal", "기타")
            return (cat, kw)
    return ("normal", "기타")


# 한방/생약 제품 판별 — 응급 시나리오에서 warning 분류하면 오도되므로 normal 강제.
_HERBAL_SUFFIXES = ("탕", "산", "환", "음", "음자", "엑스과립", "엑스산", "단")
_HERBAL_KEYWORDS = ("한방", "생약", "단미", "혼합단미", "엑스")
# 한약은 보통 제품명(괄호 안 성분) 끝이 ~탕/~산/~환. 단, 양약 성분명에도
# '산'(염산/황산), '정'이 흔하므로 오탐 방지를 위해 명확한 한방 접미만 사용.
_HERBAL_TANG_PATTERN = re.compile(r"(탕|산|환|음자|음)(엑스|과립|산|정|캡슐)?$")


def _looks_herbal_token(token: str) -> bool:
    token = token.strip()
    if not token:
        return False
    # '~탕'은 한약 거의 확실. '~산/~환/~음'은 단독으로는 양약 가능성 있어
    # 제형 접미(엑스/과립) 동반 또는 '탕'일 때만 인정.
    if token.endswith("탕"):
        return True
    if any(token.endswith(s) for s in ("탕엑스", "탕과립", "산엑스", "탕산")):
        return True
    return False


def is_herbal(product_name: str, drug_type: str = "") -> bool:
    """제품명/구분으로 한약(생약) 여부 추정. 괄호 안 성분명까지 검사."""
    if drug_type and "한약" in drug_type:
        return True
    name = (product_name or "").strip()
    if not name:
        return False

    if any(k in name for k in _HERBAL_KEYWORDS):
        return True

    # 본체(괄호 앞) + 괄호 안 성분명 모두 검사
    base = name.split("(")[0]
    inner = ""
    if "(" in name and ")" in name:
        inner = name[name.find("(") + 1: name.rfind(")")]

    for token in (base, inner):
        if _looks_herbal_token(token):
            return True
        # 'OO엑스과립' / 'OO엑스산' 류 (생약 엑스제)
        if token.endswith(("엑스과립", "엑스산", "엑스정", "엑스캡슐")):
            return True
    return False
