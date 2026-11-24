"""근거표(outputs/m1/evidence.md)의 값이 적힌 위치의 원문에 글자 그대로 있는지 찾는다.

판단은 하지 않는다. 값에 든 숫자(날짜·건수·%·물량)를 하나씩 꺼내
- 위치에 발언 순번 [nn]이 있으면 그 순번 발언들에서,
- 순번이 없으면(머리 표·절·행) 출처 파일 전체에서
글자 그대로 찾기만 한다. 숫자가 없는 값은 '직접 확인'으로 남긴다.
실행: python scripts/m1_check.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "outputs" / "m1" / "evidence.md"
INPUTS = ROOT / "inputs" / "m1"

NUM = re.compile(r"\d{1,2}:\d{2}|\d+(?:,\d{3})*(?:\.\d+)?")
SEQ = re.compile(r"\[(\d{2})\]")
FILE_ID = re.compile(r"[ACG]-M1-0\d")


def load_sources():
    files = {}
    for p in sorted(INPUTS.glob("*-M1-0*")):
        files[p.name[:7]] = p.read_text(encoding="utf-8")
    return files


def utterances(text):
    """전사본을 발언 순번별로 나눈다. 줄 맨 앞이 [nn](굵은 글씨 ** 포함)인 줄이 한 발언."""
    parts = {}
    for line in text.splitlines():
        m = re.match(r"\s*\**\[(\d{2})\]", line)
        if m:
            parts[m.group(1)] = line
    return parts


def rows(md):
    out = []
    for line in md.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and cells[0].isdigit():
            out.append(dict(no=cells[0], value=cells[2], src=cells[3], loc=cells[4]))
    return out


def main():
    files = load_sources()
    result = []
    for r in rows(EVIDENCE.read_text(encoding="utf-8")):
        ids = FILE_ID.findall(r["src"] + " " + r["loc"]) or [k for k in files if k.endswith("01")]
        seqs = SEQ.findall(r["loc"])
        if seqs:
            transcript = next((files[i] for i in ids if i.endswith("01")), "")
            u = utterances(transcript)
            text = "\n".join(u.get(s, "") for s in seqs)
            # 순번 밖 출처(요약 파일 등)가 같이 적혔으면 그 파일도 함께 본다
            text += "\n".join(files.get(i, "") for i in ids if not i.endswith("01"))
        else:
            text = "\n".join(files.get(i, "") for i in ids)
        nums = [n for n in NUM.findall(r["value"]) if n != "2026"]
        if not nums:
            verdict, missing = "직접 확인(숫자 없음)", []
        else:
            missing = [n for n in nums if not re.search(r"(?<!\d)(?<!\d[.,])" + re.escape(n) + r"(?!\d|[.,]\d)", text)]
            verdict = "있음" if not missing else "없음"
        result.append((r["no"], r["loc"], r["value"], verdict, ", ".join(missing)))

    print("| # | 위치 | 값 | 결과 | 못 찾은 글자 |")
    print("|---|---|---|---|---|")
    for row in result:
        print("| " + " | ".join(row) + " |")
    count = {}
    for row in result:
        count[row[3]] = count.get(row[3], 0) + 1
    print()
    print(" / ".join(f"{k} {v}행" for k, v in count.items()))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
