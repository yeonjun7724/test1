# -*- coding: utf-8 -*-
"""하자 접수대장 집계 — rules/aggregation_rules.md 기준 (강사 백업본, Python 표준 라이브러리만).

사용(레포 루트에서):
  python scripts/aggregate.py inputs/m2/A-M2-01_하자접수대장_week1.csv --out outputs/m2
출력: summary.csv(공종·처리상태·긴급·면적), excluded_rows.csv(원본행·사유·원본값), run_log.md
검사 순서: 합계 행 → 위치코드 정규화 → 중복(접수번호 / 위치·공종·접수일) → 면적 환산(평 → ㎡)
원본 CSV는 읽기만 한다.
"""
import argparse
import csv
import os
import re
from decimal import Decimal, ROUND_HALF_UP

NOTICE = ("> [가상 자료] 이 자료의 기관·인물·지구·업체·수치·연락처는 모두 실습용 가상 정보입니다. "
          "실제 사실이 아니며 실무에 사용할 수 없습니다.")
TYPES = ["마감", "창호", "설비", "전기", "방수결로"]
STATUSES = ["접수", "처리중", "완료"]
PYEONG = Decimal("3.3058")
STD = re.compile(r"^(\d{3})-(\d{3,4})-([가-힣]+)$")
ALT = [re.compile(r"^(\d{3})동\s*(\d{3,4})호\s+([가-힣]+)$"),   # 103동 1204호 욕실
       re.compile(r"^(\d{3})-(\d{3,4})\s+([가-힣]+)$")]          # 103-1204 욕실


def normalize_location(raw):
    """(표준 위치코드 또는 None, 고쳤는지)"""
    s = raw.strip()
    m = STD.match(s)
    changed = False
    if not m:
        for p in ALT:
            m = p.match(s)
            if m:
                changed = True
                break
    if not m or not 101 <= int(m.group(1)) <= 112:
        return None, False
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", changed


def check_date(raw):
    """접수일 검사(rules 5): YYYY-MM-DD가 아니면 None → 보류(확인 필요)."""
    d = raw.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        return None, None
    return d, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", required=True)
    ap.add_argument("--area-fix", action="append", default=[], help="접수번호=실측값(㎡), 별도 행으로만 계산")
    a = ap.parse_args()
    with open(a.input, encoding="utf-8-sig", newline="") as f:
        rd = csv.reader(f)
        header = next(rd)
        rows = [r for r in rd]
    col = {name: i for i, name in enumerate(header)}

    kept, excluded, fixed = [], [], []
    seen_no, seen_key = set(), set()
    for n, r in enumerate(rows, 1):
        no = r[col["접수번호"]].strip()
        if no == "합계":
            excluded.append((n, "합계 행", r))
            continue
        code, loc_changed = normalize_location(r[col["위치코드"]])
        if code is None:
            excluded.append((n, "위치 확인 필요", r))
            continue
        notes = []
        if loc_changed:
            notes.append(f"위치코드 {r[col['위치코드']].strip()} → {code}")
        date, date_note = check_date(r[col["접수일"]])
        if date is None:
            excluded.append((n, "확인 필요(접수일 표기)", r))
            continue
        if date_note:
            notes.append(date_note)
        if no in seen_no:
            excluded.append((n, "중복(접수번호)", r))
            continue
        key = (code, r[col["공종"]].strip(), date)
        if key in seen_key:
            excluded.append((n, "중복(위치·공종·접수일)", r))
            continue
        seen_no.add(no)
        seen_key.add(key)
        area_txt = r[col["보수면적"]].strip()
        area = Decimal(area_txt) if area_txt else Decimal("0")
        if r[col["면적단위"]].strip() == "평":
            notes.append(f"면적 {area_txt}평 → {area * PYEONG}㎡")
            area = area * PYEONG
        kept.append({"no": no, "type": r[col["공종"]].strip(), "status": r[col["처리상태"]].strip(),
                     "urgent": r[col["긴급구분"]].strip(), "area": area})
        if notes:
            fixed.append((n, no, "; ".join(notes)))

    total_area = sum((k["area"] for k in kept), Decimal("0")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    summary = [["전체", "정상 건수", str(len(kept)), "건"]]
    summary += [["공종", t, str(sum(1 for k in kept if k["type"] == t)), "건"] for t in TYPES]
    summary += [["처리상태", s, str(sum(1 for k in kept if k["status"] == s)), "건"] for s in STATUSES]
    summary += [["긴급", "긴급", str(sum(1 for k in kept if k["urgent"] == "긴급")), "건"],
                ["면적", "보수면적 합계", str(total_area), "㎡"]]
    fixnotes = []
    if a.area_fix:
        fix_total = sum((k["area"] for k in kept), Decimal("0"))
        for item in a.area_fix:
            no, val = item.split("=")
            tgt = [k for k in kept if k["no"] == no]
            if not tgt:
                fixnotes.append(f"{no}: 집계 대상 아님 — 정정 미적용")
                continue
            fix_total += Decimal(val) - tgt[0]["area"]
            fixnotes.append(f"{no}: {tgt[0]['area']}㎡ → {val}㎡")
        summary.append(["면적", "보수면적 합계(실측 정정 반영)", str(fix_total.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)), "㎡"])

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "summary.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(["구분", "항목", "값", "단위"])
        w.writerows(summary)
    with open(os.path.join(a.out, "excluded_rows.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(["원본행", "사유", "원본값"])
        w.writerows([[str(n), why, "|".join(r)] for n, why, r in excluded])

    counts = {}
    for _, why, _ in excluded:
        counts[why] = counts.get(why, 0) + 1
    out = a.out.replace("\\", "/")
    lines = [NOTICE, "", "# 집계 실행 기록", "",
             f"- 실행 명령: `python scripts/aggregate.py {a.input} --out {out}" + "".join(f" --area-fix {x}" for x in a.area_fix) + "`",
             f"- 입력 파일: `{a.input}`(수정하지 않음)",
             "- 집계 기준: `rules/aggregation_rules.md`",
             f"- 입력 데이터 행: {len(rows)}행(머리행 제외)",
             f"- 집계 대상 행: {len(kept)}행",
             f"- 제외 행: {len(excluded)}행"]
    lines += [f"  - {k}: {v}행" for k, v in counts.items()]
    lines.append(f"- 수정 후 포함 행: {len(fixed)}행")
    lines += [f"- 면적 정정(--area-fix): {x}" for x in fixnotes]
    lines += ["", "| 원본행 | 접수번호 | 수정 내용 |", "|---|---|---|"]
    lines += [f"| {n} | {no} | {t} |" for n, no, t in fixed]
    lines += ["", "## 결과", "", "| 구분 | 항목 | 값 | 단위 |", "|---|---|---|---|"]
    lines += [f"| {x[0]} | {x[1]} | {x[2]} | {x[3]} |" for x in summary]
    with open(os.path.join(a.out, "run_log.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"정상 {len(kept)}행 · 제외 {len(excluded)}행 · 수정 {len(fixed)}행 · 보수면적 합계 {total_area}㎡ → {out}")


if __name__ == "__main__":
    main()
