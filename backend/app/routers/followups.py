from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CallLog, Customer, Followup


router = APIRouter(tags=["CRM Follow-ups"])


from ..schemas import CallLogCreate, CallLogOut, FollowupCreate, FollowupUpdate, FollowupOut


def get_customer_or_404(db: Session, customer_id: int) -> Customer:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post(
    "/api/customers/{customer_id}/calls",
    response_model=CallLogOut,
    status_code=201,
)
def create_call_log(
    customer_id: int,
    payload: CallLogCreate,
    db: Session = Depends(get_db),
):
    get_customer_or_404(db, customer_id)

    call = CallLog(
        customer_id=customer_id,
        call_status=payload.call_status.strip(),
        notes=payload.notes,
        called_at=datetime.utcnow(),
    )

    db.add(call)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(call)
    return call


@router.get(
    "/api/customers/{customer_id}/calls",
    response_model=list[CallLogOut],
)
def list_call_logs(
    customer_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    get_customer_or_404(db, customer_id)

    return (
        db.query(CallLog)
        .filter(CallLog.customer_id == customer_id)
        .order_by(CallLog.called_at.desc())
        .limit(limit)
        .all()
    )


@router.post(
    "/api/customers/{customer_id}/followups",
    response_model=FollowupOut,
    status_code=201,
)
def create_followup(
    customer_id: int,
    payload: FollowupCreate,
    db: Session = Depends(get_db),
):
    get_customer_or_404(db, customer_id)

    if payload.followup_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Follow-up date cannot be in the past",
        )

    duplicate = db.query(Followup.id).filter(
        Followup.customer_id == customer_id,
        Followup.followup_date == payload.followup_date.isoformat(),
        Followup.followup_time == payload.followup_time,
        Followup.status == "pending",
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="An identical pending follow-up already exists")

    followup = Followup(
        customer_id=customer_id,
        followup_date=payload.followup_date.isoformat(),
        followup_time=payload.followup_time,
        status="pending",
        reason=payload.reason,
        notes=payload.notes,
        created_at=datetime.utcnow(),
    )

    db.add(followup)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(followup)
    return followup


@router.get(
    "/api/customers/{customer_id}/followups",
    response_model=list[FollowupOut],
)
def list_customer_followups(
    customer_id: int,
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    get_customer_or_404(db, customer_id)

    query = db.query(Followup).filter(Followup.customer_id == customer_id)

    if status:
        query = query.filter(Followup.status == status)

    return (
        query
        .order_by(
            Followup.followup_date.asc(),
            Followup.followup_time.asc(),
        )
        .all()
    )


@router.get(
    "/api/followups/today",
    response_model=list[FollowupOut],
)
def todays_followups(
    status: str = Query(default="pending"),
    db: Session = Depends(get_db),
):
    return (
        db.query(Followup)
        .filter(
            Followup.followup_date == date.today().isoformat(),
            Followup.status == status,
        )
        .order_by(
            Followup.followup_time.asc(),
            Followup.id.asc(),
        )
        .all()
    )


@router.get(
    "/api/followups/upcoming",
    response_model=list[FollowupOut],
)
def upcoming_followups(
    days: int = Query(default=7, ge=1, le=90),
    status: str = Query(default="pending"),
    db: Session = Depends(get_db),
):
    start = date.today()
    end = start + timedelta(days=days)

    return (
        db.query(Followup)
        .filter(
            Followup.followup_date >= start.isoformat(),
            Followup.followup_date <= end.isoformat(),
            Followup.status == status,
        )
        .order_by(
            Followup.followup_date.asc(),
            Followup.followup_time.asc(),
        )
        .all()
    )


@router.get('/api/followups/overdue', response_model=list[FollowupOut])
def overdue_followups(status: str = Query(default='pending'), db: Session = Depends(get_db)):
    today_str = date.today().isoformat()
    return db.query(Followup).filter(
        Followup.followup_date < today_str,
        Followup.status == status
    ).order_by(Followup.followup_date.asc()).all()


@router.patch(
    "/api/followups/{followup_id}",
    response_model=FollowupOut,
)
def update_followup(
    followup_id: int,
    payload: FollowupUpdate,
    db: Session = Depends(get_db),
):
    followup = (
        db.query(Followup)
        .filter(Followup.id == followup_id)
        .first()
    )

    if not followup:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    data = payload.model_dump(exclude_unset=True)

    if "followup_date" in data and data["followup_date"] is not None:
        if data["followup_date"] < date.today():
            raise HTTPException(
                status_code=400,
                detail="Follow-up date cannot be in the past",
            )
        data["followup_date"] = data["followup_date"].isoformat()

    for key, value in data.items():
        setattr(followup, key, value)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(followup)
    return followup


@router.delete("/api/followups/{followup_id}")
def delete_followup(
    followup_id: int,
    db: Session = Depends(get_db),
):
    followup = (
        db.query(Followup)
        .filter(Followup.id == followup_id)
        .first()
    )

    if not followup:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    db.delete(followup)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"message": "Follow-up deleted", "id": followup_id}
