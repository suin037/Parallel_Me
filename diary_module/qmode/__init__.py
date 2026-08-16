# -*- coding: utf-8 -*-
"""qmode — 질문형 일기 모드 (자유 일기 모드와 A/B 공존).

기존 diary_module 파일은 수정하지 않고 import 해서 감싸기만 한다.
    scheduler  : 출제 로직 (안전규칙 고정 + 다양성 완화 사다리)
    aggregate  : 답변 누적 → diary_metrics (길이 게이트·부러움 분기)
    card_map   : 질문 ID → 이론카드 직결 (질문 경로는 벡터검색 안 씀)
    session    : 하루치 세션 → 기존 파이프라인 연결
    setup_rag_local : RAG 원본 복사 + 로컬 재빌드 (자유칸 전용)
"""
