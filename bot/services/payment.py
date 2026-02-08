import uuid
from yookassa import Configuration, Payment as YooPayment
from bot.config import config

Configuration.account_id = config.YOOKASSA_SHOP_ID
Configuration.secret_key = config.YOOKASSA_SECRET_KEY


class PaymentService:

    @staticmethod
    async def create_payment(user_id: int, amount: int = None) -> dict:
        """Создание платежа через ЮKassa"""
        if amount is None:
            amount = config.SUBSCRIPTION_PRICE

        idempotence_key = str(uuid.uuid4())

        payment = YooPayment.create({
            "amount": {
                "value": f"{amount}.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f"https://t.me/your_bot?start=payment_success"
            },
            "capture": True,
            "description": f"Подписка Freelance Radar — {config.SUBSCRIPTION_DAYS} дней",
            "metadata": {
                "user_id": str(user_id)
            }
        }, idempotence_key)

        return {
            "id": payment.id,
            "url": payment.confirmation.confirmation_url,
            "status": payment.status
        }

    @staticmethod
    async def check_payment(payment_id: str) -> dict:
        """Проверка статуса платежа"""
        payment = YooPayment.find_one(payment_id)
        return {
            "id": payment.id,
            "status": payment.status,
            "paid": payment.paid,
            "metadata": payment.metadata
        }


payment_service = PaymentService()