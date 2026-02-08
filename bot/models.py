from datetime import datetime, timedelta
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float,
    Text, ForeignKey, JSON, BigInteger
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    full_name = Column(String(200), nullable=True)
    bio = Column(Text, nullable=True)
    portfolio_url = Column(String(500), nullable=True)
    hourly_rate = Column(Float, nullable=True)
    experience_years = Column(Integer, default=0)

    # Categories as JSON list
    categories = Column(JSON, default=list)

    # Subscription
    is_trial = Column(Boolean, default=True)
    trial_start = Column(DateTime, default=datetime.utcnow)
    subscription_end = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    # Notifications
    notifications_enabled = Column(Boolean, default=True)
    quiet_hours_start = Column(Integer, default=23)  # 23:00
    quiet_hours_end = Column(Integer, default=8)      # 08:00
    min_budget = Column(Integer, default=0)
    instant_notify = Column(Boolean, default=True)

    # Parser
    parser_active = Column(Boolean, default=False)

    # Stats
    orders_viewed = Column(Integer, default=0)
    responses_sent = Column(Integer, default=0)
    orders_won = Column(Integer, default=0)
    total_earned = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders = relationship("Order", back_populates="user")
    clients = relationship("Client", back_populates="user")
    payments = relationship("Payment", back_populates="user")

    @property
    def has_active_subscription(self) -> bool:
        now = datetime.utcnow()
        # Check trial
        if self.is_trial and self.trial_start:
            trial_end = self.trial_start + timedelta(days=1)
            if now < trial_end:
                return True
        # Check paid subscription
        if self.subscription_end and now < self.subscription_end:
            return True
        return False

    @property
    def subscription_status(self) -> str:
        now = datetime.utcnow()
        if self.is_trial and self.trial_start:
            trial_end = self.trial_start + timedelta(days=1)
            if now < trial_end:
                remaining = trial_end - now
                hours = int(remaining.total_seconds() // 3600)
                return f"🆓 Пробный период (осталось {hours}ч)"
        if self.subscription_end and now < self.subscription_end:
            remaining = self.subscription_end - now
            days = remaining.days
            return f"✅ Активна (осталось {days} дн.)"
        return "❌ Неактивна"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    external_id = Column(String(200), nullable=True)
    source = Column(String(50), nullable=False)  # kwork, fl, habr, etc.
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    budget = Column(String(100), nullable=True)
    budget_value = Column(Float, nullable=True)
    url = Column(String(1000), nullable=True)
    category = Column(String(50), nullable=True)
    client_name = Column(String(200), nullable=True)
    deadline = Column(String(200), nullable=True)

    # CRM fields
    status = Column(String(50), default="new")  # new, responded, in_progress, completed, cancelled
    my_price = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    response_text = Column(Text, nullable=True)
    priority = Column(Integer, default=0)  # 0-low, 1-medium, 2-high

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="orders")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(200), nullable=False)
    source = Column(String(50), nullable=True)
    profile_url = Column(String(500), nullable=True)
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, default=0)
    orders_count = Column(Integer, default=0)
    avg_budget = Column(Float, nullable=True)
    is_verified = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    trust_score = Column(Integer, default=50)  # 0-100
    total_spent = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="clients")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    yookassa_id = Column(String(200), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="RUB")
    status = Column(String(50), default="pending")  # pending, succeeded, cancelled
    payment_url = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="payments")


class ParsedOrder(Base):
    """Глобальная таблица всех спарсенных заказов (без дублей)"""
    __tablename__ = "parsed_orders"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(200), nullable=True)
    source = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    budget = Column(String(100), nullable=True)
    budget_value = Column(Float, nullable=True)
    url = Column(String(1000), nullable=True)
    category = Column(String(50), nullable=True)
    client_name = Column(String(200), nullable=True)
    deadline = Column(String(200), nullable=True)
    hash = Column(String(64), unique=True, nullable=False, index=True)  # для дедупликации
    created_at = Column(DateTime, default=datetime.utcnow)