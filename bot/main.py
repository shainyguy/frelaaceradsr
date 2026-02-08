import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from bot.config import config
from bot.database import init_db, async_session
from bot.handlers import get_all_routers
from bot.services.scheduler import scheduler_service
from bot.webapp.app import webapp_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot setup
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Register all routers
for router in get_all_routers():
    dp.include_router(router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / Shutdown"""
    # Startup
    logger.info("🚀 Starting Freelance Radar Bot...")
    await init_db()
    logger.info("✅ Database initialized")

    # Start scheduler
    scheduler_service.start(bot)
    logger.info("✅ Scheduler started")

    # Set webhook or start polling
    if config.WEBHOOK_URL:
        webhook_url = f"{config.WEBHOOK_URL}/webhook"
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "inline_query"]
        )
        logger.info(f"✅ Webhook set: {webhook_url}")
    else:
        asyncio.create_task(start_polling())
        logger.info("✅ Polling started")

    yield

    # Shutdown
    scheduler_service.stop()
    if config.WEBHOOK_URL:
        await bot.delete_webhook()
    await bot.session.close()
    logger.info("👋 Bot stopped")


async def start_polling():
    """Polling mode for local development"""
    await asyncio.sleep(1)
    await dp.start_polling(bot, skip_updates=True)


# FastAPI app
app = FastAPI(title="Freelance Radar", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
import os
static_dir = os.path.join(os.path.dirname(__file__), "webapp", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include webapp router
app.include_router(webapp_router)


@app.post("/webhook")
async def webhook_handler(request: Request):
    """Telegram webhook endpoint"""
    try:
        update_data = await request.json()
        from aiogram.types import Update
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot=bot, update=update)
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse({"ok": False, "error": str(e)})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Freelance Radar Bot"}


@app.get("/")
async def root():
    return {"message": "Freelance Radar Bot API", "docs": "/docs"}


# YooKassa webhook для автоматического подтверждения оплаты
@app.post("/payment/webhook")
async def payment_webhook(request: Request):
    """Webhook от ЮKassa"""
    try:
        data = await request.json()
        event = data.get("event")
        payment_obj = data.get("object", {})
        payment_id = payment_obj.get("id")
        status = payment_obj.get("status")

        logger.info(f"Payment webhook: {event} - {payment_id} - {status}")

        if event == "payment.succeeded" and status == "succeeded":
            metadata = payment_obj.get("metadata", {})
            user_id = metadata.get("user_id")

            if user_id:
                from bot.models import User, Payment
                from sqlalchemy import select
                from datetime import datetime, timedelta

                async with async_session() as session:
                    # Обновляем платёж
                    pay_result = await session.execute(
                        select(Payment).where(Payment.yookassa_id == payment_id)
                    )
                    payment = pay_result.scalar_one_or_none()
                    if payment:
                        payment.status = "succeeded"

                    # Обновляем пользователя
                    user_result = await session.execute(
                        select(User).where(User.id == int(user_id))
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        user.is_trial = False
                        user.subscription_end = datetime.utcnow() + timedelta(days=config.SUBSCRIPTION_DAYS)

                        # Уведомляем пользователя
                        try:
                            await bot.send_message(
                                user.telegram_id,
                                "🎉 <b>Оплата получена!</b>\n\n"
                                f"Подписка активирована на {config.SUBSCRIPTION_DAYS} дней.\n"
                                "Запустите парсер и получайте заказы! 🚀"
                            )
                        except Exception:
                            pass

                    await session.commit()

        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Payment webhook error: {e}")
        return JSONResponse({"ok": False})


def main():
    """Entry point"""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()