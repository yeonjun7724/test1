# -*- coding: utf-8 -*-
"""수치 대장 ↔ 연결 문서 정합 검사 (강사 백업본, Python 표준 라이브러리만).

사용(레포 루트에서):
  python scripts/consistency_check.py ledger/ledger.csv \
      inputs/m3/A-M3-01_하자보수요청_협조전_초안.md inputs/m3/A-M3-02_하자집계_업무보고서_초안.md outputs/m1/minutes.md \
      --out outputs/m3/consistency_report.md
검사 항목: 유효 접수 건수(A-L01), 공종별 건수(A-L02~06), 긴급(A-L07), 보수 대상 면적·단위(A-L08),
          미처리(A-L09), 1차 보수 착수 기한(A-L10), 긴급 하자 우선 착수일(A-L11), 회신 기한(A-L12), 모든 날짜의 요일.
회의록(minutes.md)은 5절(후속 조치)만 검사한다.
"""
import argparse
import csv
import datetime as dt
import re

NOTICE = ("> [가상 자료] 이 자료의 기관·인물·지구·업체·수치·연락처는 모두 실습용 가상 정보입니다. "
          "실제 사실이 아니며 실무에 사용할 수 없습니다.")
WD = "월화수목금토일"
DATE = r"(2026)\.\s*(\d{1,2})\.\s*(\d{1,2})\."
TYPE_ROWS = [("A-L02", "마감"), ("A-L03", "창호"), ("A-L04", "설비"), ("A-L05", "전기"), ("A-L06", "방수·결로")]
DATE_ITEMS = [("A-L10", "1차 보수 착수 기한"), ("A-L11", "긴급 하자 우선 착수"), ("A-L12", "회신 기한")]


def iso(m):
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def section5(text):
    m = re.search(r"^## 5\..*?(?=^## |\Z)", text, flags=re.S | re.M)
    return m.group(0) if m else ""


def check(L, text):
    v = {k: r["값"] for k, r in L.items()}
    issues = []
    for m in re.finditer(r"접수(?: 건수)?\s*[:：]?\s*([\d,]+)건", text):
        if m.group(1).replace(",", "") != v["A-L01"]:
            issues.append(("A-L01", m.group(0), v["A-L01"] + "건", "값 불일치"))
    for lid, name in TYPE_ROWS:
        for m in re.finditer(r"\|\s*" + name + r"\s*\|\s*([\d,]+)건?\s*\|", text):
            if m.group(1).replace(",", "") != v[lid]:
                issues.append((lid, f"{name} {m.group(1)}건", v[lid] + "건", "값 불일치"))
    for m in re.finditer(r"긴급\s*([\d,]+)건", text):
        if m.group(1) != v["A-L07"]:
            issues.append(("A-L07", m.group(0), v["A-L07"] + "건", "값 불일치"))
    for m in re.finditer(r"보수 대상 면적\s*[:：]?\s*([\d,]+(?:\.\d+)?)\s*(㎡|평)", text):
        if m.group(2) != "㎡" or m.group(1).replace(",", "") != v["A-L08"]:
            issues.append(("A-L08", m.group(1) + m.group(2), v["A-L08"] + "㎡", "단위·값 불일치"))
    for m in re.finditer(r"미처리\s*([\d,]+)건", text):
        if m.group(1) != v["A-L09"]:
            issues.append(("A-L09", m.group(0), v["A-L09"] + "건", "값 불일치"))
    for lid, label in DATE_ITEMS:
        for m in re.finditer(label + r"[^\d\n]{0,40}?" + DATE, text):
            if iso(m) != v[lid]:
                issues.append((lid, m.group(0)[-14:].strip(), v[lid], "날짜 불일치"))
    for m in re.finditer(DATE + r"\((.)\)", text):
        real = WD[dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).weekday()]
        if real != m.group(4):
            issues.append(("요일", m.group(0), f"({real})", "달력과 요일 불일치"))
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    ap.add_argument("docs", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.ledger, encoding="utf-8-sig", newline="") as f:
        L = {r["항목ID"]: r for r in csv.DictReader(f)}
    lines = [NOTICE, "", "# 정합 검사 리포트", "", f"- 대장: `{a.ledger}`",
             "- 회의록(`minutes.md`)은 5절(후속 조치)만 검사함", ""]
    total = 0
    for doc in a.docs:
        with open(doc, encoding="utf-8") as f:
            text = f.read()
        if doc.replace("\\", "/").endswith("minutes.md"):
            text = section5(text)
        issues = check(L, text)
        total += len(issues)
        lines += [f"## `{doc}`", "", f"불일치 {len(issues)}건", ""]
        if issues:
            lines += ["| 대장 ID | 문서 값 | 대장 값 | 사유 |", "|---|---|---|---|"]
            lines += [f"| {i} | {d} | {l} | {w} |" for i, d, l, w in issues]
            lines.append("")
    lines.append(f"**합계 불일치 {total}건**")
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"불일치 {total}건 → {a.out}")


if __name__ == "__main__":
    main()
