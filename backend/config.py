"""앱 전역 설정. .env 에서 값을 읽어옵니다."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 의 부모 = 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    cloudflare_reference_model: str = "@cf/black-forest-labs/flux-2-klein-4b"
    # Mobile result cards do not need a large source image. Override in .env when needed.
    # 결과 카드 표시 크기에 맞춘 4:5 출력. 기존 384×480보다 픽셀 수를 약 31% 줄여
    # 첫 생성 지연과 전송량을 낮춘다. 고해상도가 필요하면 .env에서 덮어쓴다.
    cloudflare_image_width: int = 320
    cloudflare_image_height: int = 400
    cloudflare_image_max_attempts: int = 2
    # preprocess/preprocess_goms.py의 실제 출력 위치와 통일한다.
    goms_clean_path: str = "data/clean/goms_clean.csv"
    artifacts_dir: str = "backend/models/artifacts"
    # 데이터 루트. L5 궤적(KLIPS/YP)은 goms_clean 의 부모가 아니라 여기서 경로를 잡는다.
    # (goms_clean 이 data/clean/ 아래로 옮겨지면서 data/clean/raw/klips 같은
    #  존재하지 않는 경로가 계산돼 궤적이 통째로 비어 나오던 버그를 막는다.)
    data_dir: str = "data"

    # 기동 시 무거운 것(패널·아티팩트·심리RAG 임베딩 모델)을 미리 올릴지.
    # 끄면 첫 요청이 30초 넘게 걸린다 — 테스트·CLI 처럼 한 번만 쓰는 경우에만 끈다.
    warmup_on_startup: bool = True

    # Claude 모델 — 서사 생성용. 저렴+적당 기본값(Haiku).
    # 환경변수 CLAUDE_MODEL 로 덮어쓸 수 있음(예: claude-sonnet-5 / claude-opus-4-8).
    claude_model: str = "claude-haiku-4-5"

    # 셀카 → 아바타 설정 분석용. 사진을 "보고" 우리 선택지 중에서 고른다.
    # 서사용 모델(claude_model)보다 정확도가 중요한 작업이라 따로 둔다.
    avatar_vision_model: str = "claude-opus-5"

    # ── 서사 생성 지연 ──
    # 서사 호출 지연은 입력 처리가 아니라 출력 토큰 생성이 전부다(측정: 입력
    # 4,057tok 처리는 무시할 수준, 출력 1,266tok ÷ ~100tok/s = 12.4s).
    # True 면 서로 의존하지 않는 A 서사·B 서사·비교+이미지장면을 동시 3콜로 뽑아
    # 벽시계 시간을 '합'에서 '최댓값'으로 바꾼다. False 면 예전 1회 호출 경로
    # (A·B·비교가 한 컨텍스트에서 나오지만 3배 느리다).
    narrative_parallel: bool = True
    # 콜별 출력 상한. 한국어 JSON은 토큰 효율이 낮아 너무 낮추면 객체가 잘린다.
    narrative_max_tokens_story: int = 900
    narrative_max_tokens_comparison: int = 700

    # 아바타 실사 이미지 생성용. Claude API 는 이미지 생성을 지원하지 않아
    # 별도 서비스의 키가 필요하다. 비워두면 아바타는 SVG 로만 동작한다.
    avatar_image_provider: str = ""
    avatar_image_api_key: str = ""

    @property
    def goms_clean_abspath(self) -> Path:
        return ROOT / self.goms_clean_path

    @property
    def artifacts_abspath(self) -> Path:
        return ROOT / self.artifacts_dir

    @property
    def data_abspath(self) -> Path:
        return ROOT / self.data_dir


settings = Settings()
