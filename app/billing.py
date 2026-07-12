from uuid import UUID

import stripe
from sqlalchemy.orm import Session

from app.models import Organization, PlanType, settings

stripe.api_key = settings.STRIPE_SECRET_KEY

# Plan pricing configuration (Stripe Price ID'leri; gercek degerler .env'de
# STRIPE_PRICE_PRO / STRIPE_PRICE_BUSINESS olarak tutulur)
PLAN_PRICES = {
    "pro": settings.STRIPE_PRICE_PRO,
    "business": settings.STRIPE_PRICE_BUSINESS,
}

PLAN_FEATURES = {
    PlanType.FREE: {
        "queries_per_month": 5,
        "api_access": False,
        "support": "email",
        "team_size": 1,
        "features": ["Temel arama", "Email desteği"],
    },
    PlanType.PRO: {
        "queries_per_month": 1000,
        "api_access": True,
        "support": "priority_email",
        "team_size": 3,
        "features": ["Sınırsız arama", "API erişimi", "Priority support"],
    },
    PlanType.BUSINESS: {
        "queries_per_month": None,  # Unlimited
        "api_access": True,
        "support": "priority_phone",
        "team_size": 10,
        "features": ["Sınırsız arama", "API + Webhooks", "Custom raporlar", "Team yönetimi"],
    },
    PlanType.ENTERPRISE: {
        "queries_per_month": None,  # Unlimited
        "api_access": True,
        "support": "dedicated",
        "team_size": None,  # Unlimited
        "features": ["On-premise", "White-label", "SSO/LDAP", "Dedicated support"],
    },
}


def create_stripe_customer(org: Organization, db: Session) -> str:
    """Create or get Stripe customer for organization."""
    if org.stripe_customer_id:
        return org.stripe_customer_id

    customer = stripe.Customer.create(
        email=org.email,
        name=org.name,
        metadata={"org_id": str(org.id)},
    )

    org.stripe_customer_id = customer.id
    db.commit()
    return customer.id


def create_checkout_session(org_id: str, plan_type: str, db: Session) -> dict:
    """Ilgili plan icin Stripe Checkout (barindirilan odeme sayfasi) oturumu olusturur.

    Kullanici kart bilgilerini Stripe'in kendi sayfasinda girer; bizim
    frontend'imizin Stripe.js/Elements entegrasyonuna ihtiyaci olmaz.
    Odeme tamamlaninca org.plan guncellemesi iki yoldan biriyle olur:
    1) Stripe webhook'u (checkout.session.completed) - production'da asil kaynak
    2) success_url'e donusteki session_id ile confirm_checkout() cagrisi -
       webhook receiver'i olmayan/lokal gelistirme ortamlari icin yedek yol
    """
    org = db.query(Organization).filter(Organization.id == UUID(org_id)).first()
    if not org:
        raise ValueError("Organization not found")

    if plan_type not in PLAN_PRICES or not PLAN_PRICES[plan_type]:
        raise ValueError(f"Invalid plan type or price not configured: {plan_type}")

    customer_id = create_stripe_customer(org, db)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": PLAN_PRICES[plan_type], "quantity": 1}],
        client_reference_id=str(org.id),
        metadata={"org_id": str(org.id), "plan": plan_type},
        subscription_data={"metadata": {"org_id": str(org.id), "plan": plan_type}},
        success_url=f"{settings.APP_URL}/dashboard?checkout_session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.APP_URL}/dashboard",
    )

    return {"checkout_url": session.url, "session_id": session.id}


def confirm_checkout_session(org_id: str, session_id: str, db: Session) -> dict:
    """success_url'e donuste Checkout Session'in gercekten odendigini dogrular
    ve org.plan'i webhook beklemeden gunceller (bkz. create_checkout_session)."""
    org = db.query(Organization).filter(Organization.id == UUID(org_id)).first()
    if not org:
        raise ValueError("Organization not found")

    session = stripe.checkout.Session.retrieve(session_id)

    if session.client_reference_id != str(org.id):
        raise ValueError("Bu odeme oturumu bu organizasyona ait degil")

    if session.payment_status != "paid" and session.status != "complete":
        raise ValueError(f"Odeme henuz tamamlanmadi (durum: {session.status})")

    plan_type = session.metadata.get("plan")
    if plan_type not in PLAN_PRICES:
        raise ValueError(f"Gecersiz plan bilgisi: {plan_type}")

    org.stripe_subscription_id = session.subscription
    org.plan = PlanType(plan_type)
    db.commit()

    return {"plan": plan_type, "status": "confirmed"}


def cancel_subscription(org_id: str, db: Session) -> bool:
    """Cancel organization subscription and downgrade to free."""
    org = db.query(Organization).filter(Organization.id == UUID(org_id)).first()
    if not org or not org.stripe_subscription_id:
        return False

    try:
        stripe.Subscription.delete(org.stripe_subscription_id)
        org.stripe_subscription_id = None
        org.plan = PlanType.FREE
        db.commit()
        return True
    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        return False


def handle_webhook(event: dict, db: Session):
    """Handle Stripe webhook events."""
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        org_id = session.get("client_reference_id") or (session.get("metadata") or {}).get("org_id")
        plan_type = (session.get("metadata") or {}).get("plan")
        org = db.query(Organization).filter(Organization.id == UUID(org_id)).first() if org_id else None
        if org and plan_type in PLAN_PRICES:
            org.stripe_subscription_id = session.get("subscription")
            org.plan = PlanType(plan_type)
            db.commit()

    elif event["type"] == "customer.subscription.updated":
        sub = event["data"]["object"]
        org = db.query(Organization).filter(
            Organization.stripe_subscription_id == sub["id"]
        ).first()
        if org:
            plan_type = sub.get("metadata", {}).get("plan")
            if plan_type in PLAN_PRICES:
                org.plan = PlanType(plan_type)
                db.commit()

    elif event["type"] == "customer.subscription.deleted":
        org = db.query(Organization).filter(
            Organization.stripe_subscription_id == event["data"]["object"]["id"]
        ).first()
        if org:
            org.plan = PlanType.FREE
            org.stripe_subscription_id = None
            db.commit()

    elif event["type"] == "invoice.payment_succeeded":
        print(f"Payment succeeded: {event['data']['object']['id']}")


def get_plan_limits(plan_type: str) -> dict:
    """Get limits for a given plan."""
    return PLAN_FEATURES.get(PlanType(plan_type), PLAN_FEATURES[PlanType.FREE])
