#!/usr/bin/env python3
"""M2 하자접수대장 집계. 규칙: rules/aggregation_rules.md (표준 라이브러리만 사용)."""
import csv
import hashlib
import re
import sys
from collections import Counter, OrderedDict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "inputs/m2/A-M2-01_하자접수대장_week1.csv"
OUT = ROOT / "outputs/m2"
SRC = INPUT.name
SUPP = ROOT / "outputs/m3/supplement_A-M3-03.csv"  # 정정 메모(A-M3-03) 누락 접수분. 원본 CSV는 수정하지 않고 별도 파일로 보완

PYEONG = Decimal("3.3058")  # 가정값: 자료에 근거 없음 (rules 문서의 확인 필요 항목)
DATE_MIN, DATE_MAX = date(2026, 10, 26), date(2026, 10, 30)
URGENCY = {"긴급", "일반"}
STATUS = {"접수", "처리중", "완료"}
UNITS = {"㎡", "평"}
LOC_STD = re.compile(r"^\d{3}-\d{3,4}-[^\s-]+$")
LOC_KO = re.compile(r"^(\d{3})동\s*(\d{3,4})호\s*([^\s-]+)$")
LOC_SPACE = re.compile(r"^(\d{3}-\d{3,4})\s+([^\s-]+)$")
LOC_NOSEP = re.compile(r"^\d{6,7}$")
ID_RE = re.compile(r"^HA-\d+$")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def q2(x):
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def main():
    hash_before = sha256(INPUT)
    with open(INPUT, "r", encoding="utf-8-sig", newline="") as f:  # 읽기 전용
        rows = list(csv.reader(f))
    header, data = rows[0], rows[1:]
    n_orig = len(data)
    n_supp = 0
    if SUPP.exists():
        with open(SUPP, "r", encoding="utf-8-sig", newline="") as f:
            srows = list(csv.reader(f))
        assert srows[0] == header, "보완 파일 머리행이 원본과 다름"
        data = data + srows[1:]
        n_supp = len(srows) - 1
    col = {name: i for i, name in enumerate(header)}

    excluded = []   # (행번호, 사유, 원본값)
    excl_by_rule = Counter()
    fixed = []      # 고쳐서 포함
    flags = []      # 포함하되 확인 필요
    kept = []       # dict 목록

    def exclude(n, rule, reason, row):
        excluded.append((n, f"규칙{rule}: {reason}", ",".join(row)))
        excl_by_rule[rule] += 1

    seen_ids = {}
    for n, row in enumerate(data, 1):
        g = lambda k: row[col[k]].strip() if len(row) > col[k] else ""
        rid = g("접수번호")

        # 1 합계 행
        if not ID_RE.match(rid):
            exclude(n, "1", f"합계 행(접수번호 '{rid}')", row)
            continue
        # 2 / 2a 접수번호 중복
        if rid in seen_ids:
            if row == seen_ids[rid][1]:
                exclude(n, "2", f"완전 중복({rid}, 첫 행 {seen_ids[rid][0]}번 유지)", row)
                continue
            flags.append((n, f"규칙2a: {rid} 접수번호가 {seen_ids[rid][0]}번과 같고 내용이 다름 | 포함 | {{확인 필요: 어느 쪽이 맞는지}}"))
        else:
            seen_ids[rid] = (n, row)

        rec = {"n": n, "id": rid, "date": g("접수일"), "loc": g("위치코드"), "trade": g("공종"),
               "content": g("하자내용"), "urg": g("긴급구분"), "status": g("처리상태"),
               "area_s": g("보수면적"), "unit": g("면적단위"), "row": row}

        # 4 위치코드 표준화 (제외 규칙 아님: 고치거나 표시)
        loc = rec["loc"]
        if not LOC_STD.match(loc):
            m = LOC_KO.match(loc)
            m2 = LOC_SPACE.match(loc)
            if m:
                rec["loc"] = f"{m[1]}-{m[2]}-{m[3]}"
            elif m2:
                rec["loc"] = f"{m2[1]}-{m2[2]}"
            if rec["loc"] != loc:
                fixed.append((n, f"규칙4: 위치코드 | {loc} → {rec['loc']}"))
            elif LOC_NOSEP.match(loc):
                flags.append((n, f"규칙4a: 위치코드 '{loc}' 구분자 없음 | 포함 | {{확인 필요: 동·호}}"))
            else:
                flags.append((n, f"규칙4: 위치코드 '{loc}' 비표준, 복원 불가 | 포함 | {{확인 필요: 위치}}"))
        if re.search(r"\d{3,4}호", rec["content"]):
            flags.append((n, f"규칙4b: 하자내용에 다른 세대 정보 '{rec['content']}' | 포함 | 원문 유지"))

        # 7 형식·범위 (날짜, 구분값, 상태값)
        try:
            d = datetime.strptime(rec["date"], "%Y-%m-%d").date()
            if not DATE_MIN <= d <= DATE_MAX:
                exclude(n, "7", f"접수일 범위 밖({rec['date']})", row)
                continue
        except ValueError:
            exclude(n, "7", f"접수일 형식 오류({rec['date']})", row)
            continue
        if rec["urg"] not in URGENCY:
            exclude(n, "7", f"긴급구분 값 오류({rec['urg']})", row)
            continue
        if rec["status"] not in STATUS:
            exclude(n, "7", f"처리상태 값 오류({rec['status']})", row)
            continue

        # 5, 6 면적·단위
        a, u = rec["area_s"], rec["unit"]
        rec["area"] = None
        if a == "" and u == "":
            pass  # 6: 건수만 포함
        elif a == "" or u == "":
            exclude(n, "6", f"면적·단위 한쪽만 공란(면적='{a}', 단위='{u}')", row)
            continue
        else:
            try:
                val = Decimal(a)
            except Exception:
                exclude(n, "6", f"면적이 숫자가 아님('{a}')", row)
                continue
            if val <= 0:
                exclude(n, "7", f"면적이 0 이하({a})", row)
                continue
            if u not in UNITS:
                exclude(n, "5", f"알 수 없는 면적단위('{u}')", row)
                continue
            if u == "평":
                rec["area"] = val * PYEONG
                fixed.append((n, f"규칙5: 면적 | {a}평 → {val * PYEONG:.4f}㎡ (×{PYEONG})"))
            else:
                rec["area"] = val
        kept.append(rec)

    # 3 준중복 (표준화 후 위치+공종+내용 동일, 접수번호 다름)
    groups = {}
    for r in kept:
        groups.setdefault((r["loc"], r["trade"], r["content"]), []).append(r)
    for key, rs in groups.items():
        if len({r["id"] for r in rs}) > 1:
            ids = ", ".join(f"{r['id']}({r['n']}번)" for r in rs)
            for r in rs:
                flags.append((r["n"], f"규칙3: 준중복 {ids} | 포함 | {{확인 필요: 같은 건인지}}"))

    # summary
    agg = OrderedDict()
    for r in sorted(kept, key=lambda r: (r["trade"], r["status"], r["urg"])):
        k = (r["trade"], r["status"], r["urg"])
        s = agg.setdefault(k, [0, 0, Decimal(0)])
        s[0] += 1
        if r["area"] is not None:
            s[1] += 1
            s[2] += r["area"]
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "summary.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["공종", "처리상태", "긴급구분", "건수", "면적기재건수", "면적합계_㎡"])
        for (t, s_, u_), (c, ac, ar) in agg.items():
            w.writerow([t, s_, u_, c, ac, q2(ar)])
    with open(OUT / "excluded_rows.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["원본행", "사유", "원본값"])
        w.writerows(excluded)

    total_area = q2(sum((r["area"] for r in kept if r["area"] is not None), Decimal(0)))
    blank = [r["n"] for r in kept if r["area"] is None]
    hash_after = sha256(INPUT)

    # 8 합계 대조
    orig_total = next((r for r in data if not ID_RE.match(r[0].strip())), None)
    orig_cnt = orig_area = None
    if orig_total:
        m = re.match(r"(\d+)", orig_total[col["하자내용"]])
        orig_cnt = int(m[1]) if m else None
        orig_area = Decimal(orig_total[col["보수면적"]]) if orig_total[col["보수면적"]] else None
    raw_sum = sum((Decimal(r["area_s"]) for r in kept if r["area_s"] and r["n"] <= n_orig), Decimal(0))

    L = []
    L.append("# M2 실행 기록\n")
    L.append("## 실행 정보")
    L.append(f"- 실행 명령: `python3 {' '.join(sys.argv)}`")
    L.append(f"- 입력 파일: `inputs/m2/{SRC}` (읽기 전용)")
    L.append(f"- 규칙 문서: `rules/aggregation_rules.md`")
    L.append(f"- 입력 SHA-256 실행 전/후: {hash_before[:16]}… / {hash_after[:16]}… → {'동일(수정 없음)' if hash_before == hash_after else '불일치!'}")
    L.append(f"- 평→㎡ 환산 계수: {PYEONG} {{확인 필요: 자료에 근거 없는 가정값}}\n")
    L.append("## 행 수 전후")
    L.append(f"- 처리 전: 데이터 {n_orig}행 (합계 행 포함)" + (f" + 보완 {n_supp}행(`outputs/m3/supplement_A-M3-03.csv`, 원본 {n_orig + 1}~{n_orig + n_supp}번)" if n_supp else ""))
    L.append(f"- 처리 후: 집계 포함 {len(kept)}행, 제외 {len(excluded)}행\n")
    L.append("## 규칙별 제외 수")
    L.append("| 규칙 | 제외 수 | 원본행 |")
    L.append("|---|---|---|")
    for rule in ["1", "2", "5", "6", "7"]:
        rws = [str(e[0]) for e in excluded if e[1].startswith(f"규칙{rule}:")]
        L.append(f"| {rule} | {len(rws)} | {', '.join(rws) or '-'} |")
    L.append("\n## 고쳐서 포함한 행")
    L.append("[값 | 출처 파일 | 위치(데이터 행) | 처리]")
    for n, msg in sorted(fixed):
        a, b = msg.split(" | ", 1)
        L.append(f"- [{b} | {SRC} | {n}번 | 고쳐서 포함 ({a})]")
    L.append("\n## 포함했으나 확인 필요")
    for n, msg in sorted(set(flags)):
        L.append(f"- {n}번: {msg}")
    L.append("\n## 면적 공란 (건수만 포함, 면적 합계 제외)")
    L.append(f"- {len(blank)}행: {', '.join(map(str, blank))}")
    L.append("- 빈칸이 0인지 해당 없음인지 {확인 필요: 면적 공란의 의미}")
    L.append("\n## 합계 대조 (규칙 8)")
    L.append(f"- 원본 합계 행: 건수 {orig_cnt}건, 면적 {orig_area}")
    L.append(f"- 처리 결과: 건수 {len(kept)}건, 면적 {total_area}㎡")
    L.append(f"- 건수 차이 {None if orig_cnt is None else orig_cnt - (len(kept) - n_supp)}건(보완 {n_supp}건 제외 기준): 규칙2 완전 중복 제외 {excl_by_rule['2']}건")
    L.append(f"- 면적: 원본 {orig_area}는 ㎡·평 혼합 단순합. 포함 행(보완 제외)의 원본 숫자 단순합 {raw_sum}, 보완 {n_supp}건 면적 포함·평 환산 후 {total_area}㎡")
    (OUT / "run_log.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"포함 {len(kept)}행 / 제외 {len(excluded)}행 / 면적 {total_area}㎡ / 입력 불변={hash_before == hash_after}")


if __name__ == "__main__":
    main()
