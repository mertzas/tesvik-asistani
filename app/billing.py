import stripe
from sqlalchemy.orm import Session

from app.models import Organization, PlanType, settings

stripe.api_key = settings.STRIPE_SECRET_KEY

# Plan pricing configuration
PLAN_PRICES = {
    "pro": "price_1Aaaa11111111",      # ₺299/month (test mode)
    "business": "price_1Bbbb22222222",  # ₺999/month (test mode)
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


def create_subscription(org_id: str, plan_type: str, db: Session) -> dict:
    """Upgrade organization to a paid plan."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise ValueError("Organization not found")

    if plan_type not in PLAN_PRICES:
        raise ValueError(f"Invalid plan type: {plan_type}")

    customer_id = create_stripe_customer(org, db)

    # Cancel existing subscription if present
    if org.stripe_subscription_id:
        try:
            stripe.Subscription.delete(org.stripe_subscription_id)
        except stripe.error.InvalidRequestError:
            pass

    # Create new subscription
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": PLAN_PRICES[plan_type]}],
        payment_behavior="default_incomplete",
        expand=["latest_invoice.payment_intent"],
    )

    org.stripe_subscription_id = subscription.id
    org.plan = PlanType(plan_type)
    db.commit()

    return {
        "subscription_id": subscription.id,
        "client_secret": subscription.latest_invoice.payment_intent.client_secret
        if subscription.latest_invoice.payment_intent
        else None,
        "status": subscription.status,
    }


def cancel_subscription(org_id: str, db: Session) -> bool:
    """Cancel organization subscription and downgrade to free."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
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
    if event["type"] == "customer.subscription.updated":
        sub = event["data"]["object"]
        org = db.query(Organization).filter(
            Organization.stripe_subscription_id == sub["id"]
        ).first()
        if org:
            org.plan = PlanType(sub["metadata"].get("plan", "free"))
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
