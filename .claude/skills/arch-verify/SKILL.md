---
name: arch-verify
description: 하자 처리 자료(회의 전사본·접수대장·정정 메모)를 받으면 근거·집계·정합 검증 절차로 처리한다. "검증 절차로 처리해 줘", "다음 주 자료 처리해 줘"라고 할 때 쓴다.
---

> [가상 자료] 이 자료의 기관·인물·지구·업체·수치·연락처는 모두 실습용 가상 정보입니다. 실제 사실이 아니며 실무에 사용할 수 없습니다.

# 건축 자료 검증 절차

## 1. 언제 쓰나

- 하자 처리 회의 전사본, 하자 접수대장(CSV), 정정 메모를 한 묶음으로 받았을 때
- 매주 같은 형식의 다음 주 자료를 처음부터 다시 처리할 때
- 이미 만든 회의록·집계·문서가 수치 대장과 맞는지 다시 확인할 때

## 2. 입력

| 입력 | 위치 예 | 비고 |
|---|---|---|
| 회의 녹취 전사본 | `inputs/m4/A-M4-01_후속회의_전사본.md` | 발언 순번 `[01]`부터 |
| 하자 접수대장 | `inputs/m4/A-M4-02_하자접수대장_week2.csv` | 원본은 읽기만 |
| 정정 메모 | `inputs/m4/A-M4-03_정정메모.md` | 대장 항목 변경 |
| 규칙 | `CLAUDE.md`, `rules/aggregation_rules.md` | 매번 먼저 읽음 |
| 수치 대장 | `ledger/ledger.csv` | 수치의 단일 기준 |

## 3. 절차

1. **근거:** 전사본을 발언 순번별로 분류해 회의록을 만들고, 모든 수치·결정·기한에 [값 | 출처 파일 | 위치 | 처리]를 붙인 근거표를 만든다. 정정 메모는 정정 후 값을 쓰고, 근거표는 원문 위치를 직접 열어 대조한 뒤 확정한다.
2. **집계:** `rules/aggregation_rules.md`를 새 주차 CSV에 맞는지 확인한 뒤 `scripts/aggregate.py`로 집계하고, 제외한 행은 사유와 함께 `excluded_rows.csv`에 남긴다. 검산표와 두 번째 방법으로 대조한 뒤 확정한다.
3. **정합:** 확정한 값으로 대장이 바뀌면 `impact_list.md`를 먼저 만들고, 승인된 항목만 연결 문서에서 고친다. `scripts/consistency_check.py`로 불일치 0건을 확인하고 변경 사유를 기록한다.

## 4. 확인 체크

- 근거표의 모든 행을 원문 위치에서 직접 대조했고, 정정 전 값이 처리 칸에 남아 있다.
- 잡담·개인정보가 회의록에 없고, 자료에 없는 값은 `{확인 필요: …}`로 남아 있다.
- 집계 결과가 검산표 및 두 번째 방법과 일치하고, 제외 행이 모두 `excluded_rows.csv`에 사유와 함께 있다.
- `consistency_check.py` 결과가 불일치 0건이고, `inputs/` 아래 파일은 바뀌지 않았다(`git status`로 확인).

## 5. 하지 않는 것

- inputs/ 아래 원본 파일을 고치거나 지우지 않는다.
- 건수·면적을 대화로 계산하지 않는다(scripts/로 실행).
- 하자 판정·구조 안전·보상·계약금액을 확정하지 않는다. "담당 검토 후 확정" 또는 `{확인 필요: …}`로 남긴다.
- 개인의 이름·연락처·건강 정보를 회의록·문서에 옮기지 않는다.
- 지정하지 않은 문장을 고치지 않는다.

## 6. 출력

| 산출물 | 위치 |
|---|---|
| 근거 | `outputs/m4/utterance_table.md`, `outputs/m4/minutes.md`, `outputs/m4/evidence.md`, `outputs/m4/evidence_check.md` |
| 집계 | `outputs/m4/summary.csv`, `outputs/m4/excluded_rows.csv`, `outputs/m4/run_log.md`, `outputs/m4/check.md` |
| 정합 | `ledger/ledger.csv`(week2 항목 추가), `outputs/m4/impact_list.md`, `outputs/m4/consistency_report.md` |
| 재실행 보고 | `outputs/m4/rerun_report.md`(규칙 점검표 + 새로 나온 경우 대응 + CLAUDE.md 보강 문장) |

## 7. 예시

```text
/arch-verify inputs/m4 자료를 검증 절차로 처리해 줘. 결과는 outputs/m4/에 만들어 줘.
```
