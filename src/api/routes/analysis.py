"""Analysis pipeline routes."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ...models import User, AnalysisRun
from ...models.db import get_db, SessionLocal
from ..auth import get_current_user
from ..schemas.analysis import AnalyzeRequest, AnalysisRunResponse, AnalysisStartResponse
from ...services import analysis as analysis_service, market_data

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _run_analysis_background(run_id: str):
    """Execute analysis in a background thread with its own DB session."""
    session = SessionLocal()
    try:
        run = session.get(AnalysisRun, run_id)
        if run:
            analysis_service.execute_analysis(session, run)
            session.commit()
    except Exception as e:
        session.rollback()
        # Mark as failed
        try:
            run = session.get(AnalysisRun, run_id)
            if run:
                run.status = "failed"
                run.error_message = str(e)
                session.commit()
        except Exception:
            session.rollback()
    finally:
        session.close()


@router.post("/run", response_model=AnalysisStartResponse, status_code=201)
def start_analysis(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start an analysis run. Returns immediately with a run_id; analysis runs in background."""
    market_data.check_rate_limit_or_raise(user.id)

    run = analysis_service.start_analysis(
        db=db,
        user_id=user.id,
        symbol=body.symbol,
        portfolio_id=body.portfolio_id,
    )
    db.commit()  # Commit so background thread can see the row

    background_tasks.add_task(_run_analysis_background, run.id)

    return AnalysisStartResponse(run_id=run.id, status=run.status)


@router.get("/run/{run_id}", response_model=AnalysisRunResponse)
def get_analysis_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status and results of an analysis run."""
    run = db.get(AnalysisRun, run_id)
    if not run or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return run


@router.get("/runs", response_model=list[AnalysisRunResponse])
def list_analysis_runs(
    symbol: str | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recent analysis runs."""
    q = db.query(AnalysisRun).filter_by(user_id=user.id)
    if symbol:
        q = q.filter_by(symbol=symbol.upper())
    runs = q.order_by(AnalysisRun.created_at.desc()).limit(min(limit, 100)).all()
    return runs
