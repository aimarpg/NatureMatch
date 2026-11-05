from fastapi import APIRouter

router = APIRouter(tags=["assessments"])


@router.get("/assessments")
def assess(activity: str, step_free: bool = False) -> dict:
    raise NotImplementedError   # call naturematch.assessment
