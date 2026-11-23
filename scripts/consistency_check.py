#!/usr/bin/env python3
"""대장(ledger/ledger.csv) 값과 문서 속 수치·날짜·요일 대조. 표준 라이브러리만 사용. 문서는 읽기만 한다.
사용: python3 scripts/consistency_check.py --label "고치기 전" --out outputs/m3/consistency_report.md [--append]
minutes.md는 '## 5.' 절만 검사한다."""
import argparse
import csv
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "ledger/ledger.csv"
DOCS = [  # (파일, 5절만 여부)
    ("inputs/m3/A-M3-01_하자보수요청_협조전_초안.md", None),
    ("inputs/m3/A-M3-02_하자집계_업무보고서_초안.md", None),
    ("outputs/m1/minutes.md", "## 5."),
]
WD = "월화수목금토일"
DATE_RE = re.compile(r"(?:(\d{4})\.\s*)?(\d{1,2})\.\s*(\d{1,2})\.\s*\(([월화수목금토일])\)")
FULL_DATE_RE = re.compile(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.")
NUM = r"(\d+(?:\.\d+)?)"

# (대장 항목ID, 줄 키워드 정규식, 값 추출 정규식, 종류)
COUNT_RULES = [
    ("A-L01", r"접수 (?:건수|현황)", r"접수(?: 건수)?[:\s]*(\d+)건"),
    ("A-L07", r"긴급 건수", r"긴급 건수[:\s]*(\d+)건"),
    ("A-L09", r"미처리", r"미처리[^\d\n]{0,8}(\d+)건"),
]
TRADES = {"A-L02": "마감", "A-L03": "방수결로", "A-L04": "설비", "A-L05": "전기", "A-L06": "창호"}
DATE_RULES = [
    ("A-L10", r"1차 보수 착수"),
    ("A-L11", r"긴급 하자 (?:우선 )?착수|긴급 하자 착수"),
    ("A-L12", r"회신 기한"),
]


def load_ledger():
    with open(LEDGER, encoding="utf-8-sig", newline="") as f:
        return {r["항목ID"]: r for r in csv.DictReader(f)}


def weekday(y, m, d):
    try:
        return WD[date(y, m, d).weekday()]
    except ValueError:
        return None


def check_doc(path, only, led):
    text = (ROOT / path).read_text(encoding="utf-8")
    lines = text.split("\n")
    start = 0
    end = len(lines)
    if only:
        idx = [i for i, l in enumerate(lines) if l.startswith(only)]
        start = idx[0]
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    res = []  # (종류, 줄, 문서 값, 대장 항목, 대장 값, 판정)
    for n in range(start, end):
        line = lines[n]
        ln = n + 1
        # 건수
        for lid, key, rx in COUNT_RULES:
            if re.search(key, line):
                for m in re.finditer(rx, line):
                    ok = m.group(1) == led[lid]["값"]
                    res.append(("수치", ln, m.group(0), lid, led[lid]["값"] + led[lid]["단위"], "일치" if ok else "불일치"))
        # 공종별 건수
        for lid, tr in TRADES.items():
            for m in re.finditer(tr + r"[^\d\n,|]{0,6}" + r"(\d+)건", line):
                ok = m.group(1) == led[lid]["값"]
                res.append(("수치", ln, m.group(0), lid, led[lid]["값"] + "건", "일치" if ok else "불일치"))
        # 면적
        m = re.search(r"보수 대상 면적[:\s]*" + NUM + r"\s*(㎡|평)", line)
        if m:
            led_v = float(led["A-L08"]["값"])
            same = m.group(2) == "㎡" and abs(float(m.group(1)) - led_v) < 0.05
            res.append(("수치", ln, m.group(0), "A-L08", led["A-L08"]["값"] + "㎡", "일치" if same else "불일치"))
        # 날짜 항목
        for lid, key in DATE_RULES:
            if re.search(key, line):
                for m in FULL_DATE_RE.finditer(line):
                    s = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                    res.append(("날짜", ln, m.group(0), lid, led[lid]["값"], "일치" if s == led[lid]["값"] else "불일치"))
        # 요일
        for m in DATE_RE.finditer(line):
            y = int(m.group(1)) if m.group(1) else 2026
            real = weekday(y, int(m.group(2)), int(m.group(3)))
            ok = real == m.group(4)
            res.append(("요일", ln, m.group(0).strip(), "-", f"{y}-{int(m.group(2)):02d}-{int(m.group(3)):02d}은 {real}요일", "일치" if ok else "불일치"))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="")
    ap.add_argument("--out")
    ap.add_argument("--append", action="store_true")
    a = ap.parse_args()
    led = load_ledger()
    L = [f"## {a.label}\n" if a.label else "", "대장: `ledger/ledger.csv` (읽기). minutes.md는 5절만 검사. 실행: `python3 scripts/consistency_check.py`\n"]
    tot = bad = 0
    for path, only in DOCS:
        res = check_doc(path, only, led)
        b = [r for r in res if r[5] == "불일치"]
        tot += len(res)
        bad += len(b)
        L.append(f"### {path}" + (" (5절)" if only else ""))
        L.append(f"검사 {len(res)}건, 불일치 {len(b)}건\n")
        L.append("| 종류 | 줄 | 문서 값 | 대장 항목 | 대장 값 | 판정 |")
        L.append("|---|---:|---|---|---|---|")
        for r in res:
            L.append("| " + " | ".join(str(x) for x in r) + " |")
        L.append("")
    L.append(f"**합계: 검사 {tot}건, 불일치 {bad}건**\n")
    out = "\n".join(L)
    if a.out:
        p = ROOT / a.out
        mode = "a" if a.append and p.exists() else "w"
        with open(p, mode, encoding="utf-8") as f:
            if mode == "w":
                f.write("# 정합 검사 보고서 (대장 ↔ 문서)\n\n")
            else:
                f.write("\n")
            f.write(out)
    print(out)


if __name__ == "__main__":
    main()
