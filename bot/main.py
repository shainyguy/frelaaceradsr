import asyncio
import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from bot.config import config
from bot.database import init_db, async_session

# ============ LOAD HANDLERS DIRECTLY ============
logger.info("📦 Loading handlers directly...")

loaded_routers = []

try:
    from bot.handlers.start import router as r1
    loaded_routers.append(r1)
    logger.info("  ✅ start")
except Exception as e:
    logger.error(f"  ❌ start: {e}")

try:
    from bot.handlers.profile import router as r2
    loaded_routers.append(r2)
    logger.info("  ✅ profile")
except Exception as e:
    logger.error(f"  ❌ profile: {e}")

try:
    from bot.handlers.categories import router as r3
    loaded_routers.append(r3)
    logger.info("  ✅ categories")
except Exception as e:
    logger.error(f"  ❌ categories: {e}")

try:
    from bot.handlers.parser_control import router as r4
    loaded_routers.append(r4)
    logger.info("  ✅ parser_control")
except Exception as e:
    logger.error(f"  ❌ parser_control: {e}")

try:
    from bot.handlers.crm import router as r5
    loaded_routers.append(r5)
    logger.info("  ✅ crm")
except Exception as e:
    logger.error(f"  ❌ crm: {e}")

try:
    from bot.handlers.calculator import router as r6
    loaded_routers.append(r6)
    logger.info("  ✅ calculator")
except Exception as e:
    logger.error(f"  ❌ calculator: {e}")

try:
    from bot.handlers.notifications import router as r7
    loaded_routers.append(r7)
    logger.info("  ✅ notifications")
except Exception as e:
    logger.error(f"  ❌ notifications: {e}")

try:
    from bot.handlers.subscription import router as r8
    loaded_routers.append(r8)
    logger.info("  ✅ subscription")
except Exception as e:
    logger.error(f"  ❌ subscription: {e}")

try:
    from bot.handlers.client_check import router as r9
    loaded_routers.append(r9)
    logger.info("  ✅ client_check")
except Exception as e:
    logger.error(f"  ❌ client_check: {e}")

logger.info(f"📦 Total handlers loaded: {len(loaded_routers)}/9")

# ============ BOT SETUP ============
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

for router in loaded_routers:
    dp.include_router(router)

logger.info(f"✅ {len(loaded_routers)} routers registered in dispatcher")


# ============ FASTAPI ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Freelance Radar Bot...")

    try:
        await init_db()
        logger.info("✅ Database ready")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")

    try:
        from bot.services.scheduler import scheduler_service
        scheduler_service.start(bot)
        logger.info("✅ Scheduler started")
    except Exception as e:
        logger.error(f"❌ Scheduler error: {e}")

    if config.WEBHOOK_URL:
        try:
            webhook_url = f"{config.WEBHOOK_URL}/webhook"
            await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
            logger.info(f"✅ Webhook: {webhook_url}")
        except Exception as e:
            logger.error(f"❌ Webhook error: {e}")
            asyncio.create_task(start_polling())
    else:
        asyncio.create_task(start_polling())
        logger.info("✅ Polling mode")

    logger.info("🟢 BOT IS READY!")
    yield

    logger.info("🔴 Shutting down...")
    try:
        from bot.services.scheduler import scheduler_service
        scheduler_service.stop()
    except Exception:
        pass
    try:
        if config.WEBHOOK_URL:
            await bot.delete_webhook()
    except Exception:
        pass
    await bot.session.close()


async def start_polling():
    await asyncio.sleep(2)
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Polling error: {e}")


app = FastAPI(title="Freelance Radar", lifespan=lifespan)

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

# Webapp routes
try:
    from bot.webapp.app import webapp_router
    app.include_router(webapp_router)
    logger.info("✅ WebApp router loaded")
except Exception as e:
    logger.error(f"❌ WebApp router error: {e}")


@app.post("/webhook")
async def webhook_handler(request: Request):
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
    return {"status": "ok", "handlers": len(loaded_routers)}


@app.get("/")
async def root():
    return {"message": "Freelance Radar Bot", "handlers": len(loaded_routers)}


@app.post("/payment/webhook")
async def payment_webhook(request: Request):
    try:
        data = await request.json()
        event = data.get("event")
        obj = data.get("object", {})
        payment_id = obj.get("id")
        status = obj.get("status")

        if event == "payment.succeeded" and status == "succeeded":
            metadata = obj.get("metadata", {})
            user_id = metadata.get("user_id")

            if user_id:
                from bot.models import User, Payment
                from sqlalchemy import select
                from datetime import datetime, timedelta

                async with async_session() as session:
                    pay_result = await session.execute(
                        select(Payment).where(Payment.yookassa_id == payment_id)
                    )
                    payment = pay_result.scalar_one_or_none()
                    if payment:
                        payment.status = "succeeded"

                    user_result = await session.execute(
                        select(User).where(User.id == int(user_id))
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        user.is_trial = False
                        user.subscription_end = datetime.utcnow() + timedelta(days=config.SUBSCRIPTION_DAYS)
                        try:
                            await bot.send_message(
                                user.telegram_id,
                                "🎉 <b>Оплата получена!</b>\n\n"
                                f"Подписка на {config.SUBSCRIPTION_DAYS} дней активирована! 🚀"
                            )
                        except Exception:
                            pass

                    await session.commit()

        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Payment webhook error: {e}")
        return JSONResponse({"ok": False})


def main():
    uvicorn.run(app, host="0.0.0.0", port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
