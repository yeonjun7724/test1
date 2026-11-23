#!/usr/bin/env python3
"""outputs/m1/evidence.md 각 행의 값에 든 숫자가 위치 칸의 원문에 글자 그대로 있는지 찾기만 한다.

- 위치에 발언 순번([NN])이 있으면 그 순번 발언에서, 없으면 출처 파일 전체에서 찾는다.
- 숫자(날짜·시각·건수·%)가 없는 값은 '직접 확인'으로 둔다.
- 뜻은 판단하지 않고, 아무 파일도 고치지 않는다(읽기 전용, 표준 출력만).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "outputs" / "m1" / "evidence.md"
INPUT_DIR = ROOT / "inputs" / "m1"

# 값에서 찾을 숫자 글자: 연도 포함 날짜, 월. 일. 날짜, 시각, 숫자+단위(건·%·주·일·개·명·동·호·㎡)
TOKEN_RE = re.compile(
    r"\d{4}\. \d{1,2}\. \d{1,2}\."
    r"|\d{1,2}\. \d{1,2}\."
    r"|\d{1,2}:\d{2}"
    r"|\d+(?:건|%|주|일|개|명|동|호|㎡)"
)


def read(path):
    return path.read_text(encoding="utf-8-sig")


def source_file(file_id):
    found = sorted(INPUT_DIR.glob(file_id + "_*"))
    return found[0] if found else None


def utterances(text):
    """전사본에서 '**[NN] ...' 로 시작하는 줄을 순번별로 나눈다."""
    result = {}
    for line in text.splitlines():
        m = re.match(r"\*\*\[(\d+)\]", line)
        if m:
            result[m.group(1).zfill(2)] = line
    return result


def build_corpus(location, source_ids):
    parts = []
    cache = {}

    def file_text(fid):
        if fid not in cache:
            p = source_file(fid)
            cache[fid] = read(p) if p else ""
        return cache[fid]

    loc = re.sub(r"\([^)]*\)", "", location)  # 괄호 속 설명은 위치가 아님
    for seg in loc.split(","):
        ids = re.findall(r"A-M1-0\d", seg)
        nums = re.findall(r"\[(\d+)\]", seg)
        if nums:
            fid = ids[0] if ids else "A-M1-01"
            utt = utterances(file_text(fid))
            for n in nums:
                parts.append(utt.get(n.zfill(2), ""))
        else:
            for fid in (ids or source_ids):
                parts.append(file_text(fid))
    return "\n".join(parts)


def main():
    rows = []
    for line in read(EVIDENCE).splitlines():
        if not line.startswith("| E"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6:
            print("열 수가 6이 아닌 행: " + line, file=sys.stderr)
            continue
        rows.append(cells)

    print("| # | 위치 | 값 | 결과 | 못 찾은 글자 |")
    print("|---|---|---|---|---|")
    for num, _sentence, value, source, location, _handling in rows:
        tokens = list(dict.fromkeys(TOKEN_RE.findall(value)))
        if not tokens:
            result, missing = "직접 확인", "—"
        else:
            corpus = build_corpus(location, re.findall(r"A-M1-0\d", source))
            lost = [t for t in tokens if t not in corpus]
            result = "없음" if lost else "있음"
            missing = ", ".join(lost) if lost else "—"
        print(f"| {num} | {location} | {value} | {result} | {missing} |")


if __name__ == "__main__":
    main()
