# LLM Multi-Agent Moral Stance Discussion Simulation

# 다중 에이전트 도덕적 입장 토론 시뮬레이션

This repository contains an experimental framework to observe and analyze how LLM agents adjust their moral stances during group discussions across various conditions.

본 저장소는 다양한 조건 내에서 LLM 에이전트들이 그룹 토론을 통해 도덕적 입장을 어떻게 조정하고 변화시키는지 관찰하고 분석하기 위한 실험 프레임워크를 포함하고 있습니다.

## Project Overview (프로젝트 개요)

The experiment investigates the dynamics of opinion change in LLM populations when exposed to social information, peer rationales, and consensus statistics. It specifically uses the Ollama framework to run local models (e.g., Mistral).

이 실험은 사회적 정보, 동료의 근거, 그리고 합의 통계에 노출되었을 때 LLM 집단 내에서 입장이 어떻게 변화하는지 그 동학을 조사합니다. Ollama 프레임워크를 사용하여 Mistral과 같은 로컬 모델을 구동합니다.

## Installation (설치 방법)

1. **Prerequisites (사전 요구사항)**:
    - Python 3.10+
    - [Ollama](https://ollama.ai/) with `mistral` model installed.

2. **Setup (설정)**:

    ```bash
    pip install -r requirements.txt
    ```

## Usage (사용법)

### Running Experiments (실험 실행)

To run a batch experiment with a specific configuration (e.g., 30 agents, 15 rounds):
특정 설정(예: 30명 에이전트, 15라운드)으로 배치 실험을 실행하려면:

```bash
python run_batch.py --thesis-lite --initial-mode enforced
```

### Analysis and Visualization (분석 및 시각화)

After the experiment completes, generate reports and plots:
실험이 완료된 후, 보고서와 그래프를 생성합니다:

```bash
python analyze.py --all
python visualize.py --all
```

## Directory Structure (디렉토리 구조)

- `src/`: Core logic (Agent, Experiment, LLM Client) / 핵심 로직
- `logs/`: Raw logs and summaries / 데이터 로그 및 요약
- `plots/`: Generated visualizations / 시각화 결과물
- `docs/`: Documentation and research notes / 문서 및 연구 노트
- `tmp/`: Temporary analysis scripts / 임시 분석용 스크립트

---
*This project is part of an ongoing research on multi-agent interaction dynamics.*
*본 프로젝트는 다중 에이전트 상호작용 동학에 관한 연구의 일환입니다.*
