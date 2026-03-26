# QuantMarket GCP 비용 검토 메모

## 기준 시나리오

운영단계는 아래 구조를 가정한다.

- Cloud Scheduler 1개
- Cloud Run Job 1개
- 결과 JSON은 Cloud Storage 또는 소용량 저장소에 보관
- QuantService는 생성된 결과를 읽기만 함
- 리전은 서울(`asia-northeast3`) 가정

## 공식 가격 참고

- Cloud Run Jobs
  - 서울 리전 지원
  - Free tier: CPU 240,000 vCPU-sec / RAM 450,000 GiB-sec / month
  - 출처: Cloud Run pricing
- Cloud Scheduler
  - job 당 월 0.10 USD
  - billing account 당 3 jobs free
  - 출처: Cloud Scheduler pricing
- Cloud Logging
  - 로그 저장 0.50 USD / GiB
  - project 당 월 50 GiB free
  - 출처: Google Cloud Observability pricing
- Cloud Storage
  - Asia multi-region standard storage: 0.000035616 USD / GiB-hour
  - 대략 월 0.026 USD / GiB 수준
  - 출처: Cloud Storage pricing

## 비용 추정 1: 소규모 초기 운영

가정:
- Cloud Run Job: 1 vCPU, 0.5 GiB
- 1회 실행 시간: 3분
- 하루 실행: 12회
- 월 30일

월 사용량:
- CPU: 64,800 vCPU-sec
- RAM: 32,400 GiB-sec

해석:
- Cloud Run free tier 이내라서 실행비는 사실상 0 USD 가능성이 높음
- Scheduler는 1 job이면 free tier 이내
- Logging도 소량이면 대부분 free tier 이내
- Storage도 snapshot 수 MB~수백 MB 수준이면 사실상 무시 가능

예상:
- 월 0 ~ 5 USD 수준
- 원화로는 대략 수천원 이하 가능성이 높음

## 비용 추정 2: 보수적 초기 운영

가정:
- Cloud Run Job: 1 vCPU, 1 GiB
- 1회 실행 시간: 5분
- 하루 실행: 24회
- 월 30일

월 사용량:
- CPU: 216,000 vCPU-sec
- RAM: 216,000 GiB-sec

해석:
- 이것도 여전히 free tier 안쪽 또는 거의 근접한 수준
- Scheduler 1 job은 여전히 free
- Logging/Storage가 소량이면 추가비 매우 작음

예상:
- 월 0 ~ 10 USD 수준
- 원화로는 대략 0 ~ 1.5만원 정도 범위로 시작 가능

## 비용 추정 3: 조금 더 여유 있는 운영

가정:
- Cloud Run Job: 2 vCPU, 2 GiB
- 1회 실행 시간: 5분
- 하루 실행: 24회
- 월 30일

월 사용량:
- CPU: 432,000 vCPU-sec
- RAM: 432,000 GiB-sec

대략 계산:
- CPU 초과분 약 192,000 vCPU-sec
- 서울 기준 CPU 단가를 적용하면 대략 3.5 USD 전후
- RAM은 free tier 거의 소진 수준
- 여기에 logging/storage가 소량 추가

예상:
- 월 5 ~ 15 USD 수준
- 원화로는 대략 0.7만 ~ 2만원대

## 현실적인 예산 권장치

초기 운영 예산은 아래처럼 잡는 것이 무난하다.

- 최소 예상:
  - 월 0 ~ 1만원
- 보수적 예산:
  - 월 2만 ~ 5만원
- 운영 안정화 후 일반적 가능 범위:
  - 대부분 5만원 이내에서 시작 가능성이 높음

## 주의

- 실제 청구는 리전/통화/로그량/네트워크 송신량에 따라 달라진다.
- 같은 리전의 Google Cloud 리소스 간 전송은 별도 비용이 없을 수 있어 구조를 같은 리전에 두는 것이 유리하다.
- 로그를 과도하게 남기거나 대용량 원천 데이터를 장기 저장하면 비용이 빨리 커질 수 있다.

## 권장

운영단계 전환 시에는 먼저 아래처럼 시작하는 것이 좋다.

- Cloud Scheduler 1개
- Cloud Run Job 1개
- 작은 CPU/메모리로 시작
- 로그 보관 최소화
- Storage는 snapshot 위주로 소량 저장

그리고 2~4주 실제 실행 데이터를 본 뒤 CPU/메모리/실행시간 기준으로 2차 예산을 다시 잡는다.
