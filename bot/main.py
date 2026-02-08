import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Проверяем что мы можем импортировать основные модули
logger.info("🔧 Loading config...")
from bot.config import config

logger.info("🔧 Loading database...")
from bot.database import init_db, async_session

logger.info("🔧 Loading handlers...")
from bot.handlers import get_all_routers

logger.info("🔧 Loading scheduler...")
from bot.services.scheduler import scheduler_service

logger.info("🔧 Loading webapp...")
from bot.webapp.app import webapp_router

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ============ BOT SETUP ============
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Register routers
logger.info("📦 Registering handlers...")
all_routers = get_all_routers()
for router in all_routers:
    dp.include_router(router)
logger.info(f"✅ {len(all_routers)} handlers registered")


# ============ FASTAPI SETUP ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown"""
    # === STARTUP ===
    logger.info("🚀 Starting Freelance Radar Bot...")

    # Init database
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database init failed: {e}")

    # Start scheduler
    try:
        scheduler_service.start(bot)
        logger.info("✅ Scheduler started")
    except Exception as e:
        logger.error(f"❌ Scheduler start failed: {e}")

    # Webhook or polling
    if config.WEBHOOK_URL:
        try:
            webhook_url = f"{config.WEBHOOK_URL}/webhook"
            await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
            logger.info(f"✅ Webhook set: {webhook_url}")
        except Exception as e:
            logger.error(f"❌ Webhook failed: {e}")
            # Fallback to polling
            asyncio.create_task(start_polling())
    else:
        asyncio.create_task(start_polling())
        logger.info("✅ Polling mode started")

    logger.info("🟢 Bot is ready!")

    yield

    # === SHUTDOWN ===
    logger.info("🔴 Shutting down...")
    scheduler_service.stop()
    if config.WEBHOOK_URL:
        try:
            await bot.delete_webhook()
        except Exception:
            pass
    await bot.session.close()
    logger.info("👋 Bot stopped")


async def start_polling():
    """Polling mode fallback"""
    await asyncio.sleep(2)
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Polling error: {e}")


# Create FastAPI app
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
static_dir = os.path.join(os.path.dirname(__file__), "webapp", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"✅ Static files: {static_dir}")
else:
    logger.warning(f"⚠️ Static dir not found: {static_dir}")

# Webapp API routes
app.include_router(webapp_router)


# ============ ENDPOINTS ============
@app.post("/webhook")
async def webhook_handler(request: Request):
    """Telegram webhook"""
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
    return {
        "status": "ok",
        "service": "Freelance Radar Bot",
        "handlers": len(all_routers),
    }


@app.get("/")
async def root():
    return {
        "message": "🎯 Freelance Radar Bot API",
        "health": "/health",
        "webapp": "/webapp",
        "docs": "/docs",
    }


@app.post("/payment/webhook")
async def payment_webhook(request: Request):
    """YooKassa payment webhook"""
    try:
        data = await request.json()
        event = data.get("event")
        payment_obj = data.get("object", {})
        payment_id = payment_obj.get("id")
        status = payment_obj.get("status")

        logger.info(f"💳 Payment webhook: {event} - {payment_id} - {status}")

        if event == "payment.succeeded" and status == "succeeded":
            metadata = payment_obj.get("metadata", {})
            user_id = metadata.get("user_id")

            if user_id:
                from bot.models import User, Payment
                from sqlalchemy import select
                from datetime import datetime, timedelta

                async with async_session() as session:
                    # Update payment
                    pay_result = await session.execute(
                        select(Payment).where(Payment.yookassa_id == payment_id)
                    )
                    payment = pay_result.scalar_one_or_none()
                    if payment:
                        payment.status = "succeeded"

                    # Update user subscription
                    user_result = await session.execute(
                        select(User).where(User.id == int(user_id))
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        user.is_trial = False
                        user.subscription_end = datetime.utcnow() + timedelta(
                            days=config.SUBSCRIPTION_DAYS
                        )

                        try:
                            await bot.send_message(
                                user.telegram_id,
                                "🎉 <b>Оплата получена!</b>\n\n"
                                f"Подписка активирована на {config.SUBSCRIPTION_DAYS} дней.\n"
                                "Запустите парсер и ловите заказы! 🚀"
                            )
                        except Exception:
                            pass

                    await session.commit()
                    logger.info(f"✅ Subscription activated for user {user_id}")

        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Payment webhook error: {e}")
        return JSONResponse({"ok": False})


# ============ ENTRY POINT ============
def main():
    port = config.PORT
    logger.info(f"🌐 Starting server on port {port}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
