from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.models import get_db, Organization, User, Query, PlanType
from app.auth import get_current_user
from app.schemas import OrganizationResponse, UserResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


def check_admin_role(current_user: User = Depends(get_current_user)):
    """Check if user is admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# ============ ORGANIZATION MANAGEMENT ============

@router.get("/organizations")
def list_organizations(
    admin: User = Depends(check_admin_role),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List all organizations (only for admins)."""
    orgs = db.query(Organization).offset(skip).limit(limit).all()
    return {
        "total": db.query(Organization).count(),
        "organizations": orgs,
    }


@router.get("/organizations/{org_id}")
def get_organization_details(
    org_id: str,
    admin: User = Depends(check_admin_role),
    db: Session = Depends(get_db),
):
    """Get organization details including users and usage."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    users = db.query(User).filter(User.org_id == org_id).all()
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    queries = db.query(Query).filter(
        Query.org_id == org_id,
        Query.created_at >= thirty_days_ago
    ).all()

    return {
        "organization": org,
        "users": users,
        "queries_this_month": len(queries),
        "storage_used": sum(len(str(q.results)) for q in queries),
    }


@router.post("/organizations/{org_id}/plan")
def update_plan(
    org_id: str,
    plan: str,
    admin: User = Depends(check_admin_role),
    db: Session = Depends(get_db),
):
    """Manually update organization plan (admin only)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if plan not in ["free", "pro", "business", "enterprise"]:
        raise HTTPException(status_code=400, detail="Invalid plan")

    org.plan = PlanType(plan)
    db.commit()

    return {"message": f"Plan updated to {plan}", "organization": org}


@router.delete("/organizations/{org_id}")
def delete_organization(
    org_id: str,
    admin: User = Depends(check_admin_role),
    db: Session = Depends(get_db),
):
    """Delete organization and all related data."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    db.delete(org)
    db.commit()

    return {"message": "Organization deleted"}


# ============ USER MANAGEMENT ============

@router.get("/users")
def list_users(
    admin: User = Depends(check_admin_role),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List all users."""
    users = db.query(User).offset(skip).limit(limit).all()
    return {
        "total": db.query(User).count(),
        "users": users,
    }


@router.post("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    role: str,
    admin: User = Depends(check_admin_role),
    db: Session = Depends(get_db),
):
    """Update user role."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if role not in ["admin", "member", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    user.role = role
    db.commit()

    return {"message": f"User role updated to {role}"}


@router.post("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    admin: User = Depends(check_admin_role),
    db: Session = Depends(get_db),
):
    """Deactivate user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()

    return {"message": "User deactivated"}


# ============ ANALYTICS ============

@router.get("/analytics/overview")
def get_analytics_overview(
    admin: User = Depends(check_admin_role),
    db: Session = Depends(get_db),
):
    """Get platform analytics overview."""
    total_orgs = db.query(Organization).count()
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active).count()

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    queries_this_month = db.query(Query).filter(
        Query.created_at >= thirty_days_ago
    ).count()

    # Plan distribution
    plan_distribution = {}
    for plan in ["free", "pro", "business", "enterprise"]:
        count = db.query(Organization).filter(Organization.plan == plan).count()
        plan_distribution[plan] = count

    return {
        "total_organizations": total_orgs,
        "total_users": total_users,
        "active_users": active_users,
        "queries_this_month": queries_this_month,
        "plan_distribution": plan_distribution,
        "monthly_active_rate": (active_users / total_users * 100) if total_users > 0 else 0,
    }


@router.get("/analytics/revenue")
def get_revenue_analytics(
    admin: User = Depends(check_admin_role),
    db: Session = Depends(get_db),
):
    """Get revenue analytics by plan."""
    pricing = {
        "free": 0,
        "pro": 299,
        "business": 999,
        "enterprise": 0,  # Custom pricing
    }

    revenue_breakdown = {}
    total_revenue = 0

    for plan in ["free", "pro", "business", "enterprise"]:
        count = db.query(Organization).filter(Organization.plan == plan).count()
        plan_revenue = count * pricing[plan]
        revenue_breakdown[plan] = plan_revenue
        if plan != "enterprise":
            total_revenue += plan_revenue

    return {
        "total_monthly_revenue": total_revenue,
        "revenue_breakdown": revenue_breakdown,
        "mrr_projection": total_revenue,  # Monthly Recurring Revenue
    }


@router.get("/analytics/churn")
def get_churn_analytics(
    admin: User = Depends(check_admin_role),
    db: Session = Depends(get_db),
):
    """Get churn analytics."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    sixty_days_ago = datetime.now(timezone.utc) - timedelta(days=60)

    # Organizations that were active 60 days ago but not in the last 30 days
    inactive_orgs = db.query(Organization).filter(
        Organization.updated_at < thirty_days_ago
    ).count()

    active_orgs = db.query(Organization).filter(
        Organization.updated_at >= thirty_days_ago
    ).count()

    churn_rate = (inactive_orgs / (inactive_orgs + active_orgs) * 100) if (inactive_orgs + active_orgs) > 0 else 0

    return {
        "inactive_organizations": inactive_orgs,
        "active_organizations": active_orgs,
        "churn_rate_percent": churn_rate,
    }
