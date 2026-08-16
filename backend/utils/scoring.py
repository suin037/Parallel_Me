"""입력 → 모델 feature 벡터 변환 유틸."""

from schemas import PredictRequest


def build_feature_vector(req: PredictRequest) -> dict:
    """PredictRequest 를 모델들이 쓰는 공통 feature dict 로 변환.

    None 인 항목은 각 모델이 학습 데이터 중앙값으로 대체한다.
    """
    return {
        "age": req.age,
        "sex": req.sex,
        "major": req.major,
        "gpa": req.gpa,
        "choice": req.choice,
        "monthly_wage": req.monthly_wage,
        "satis_overall": req.satis_overall,
        "life_satis": req.life_satis,
        "happy": req.happy,
        "is_regular": req.is_regular,
        "firm_size": req.firm_size,
        "occupation_group": req.occupation_group,
        "employment_status": req.employment_status,
        "tenure_years": req.tenure_years,
        "edu_level": req.edu_level,
        # 궤적 매칭 정교화용(선택). 주면 그 축까지 써서 이웃을 고르고,
        # 안 주면 그 축은 거리 계산에서 아예 빠진다(중앙값으로 채우지 않는다).
        "tenure_years": req.tenure_years,
        "job_category": req.job_category,
    }
