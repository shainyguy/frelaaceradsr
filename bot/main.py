import asyncio
import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from aiogram import Bot, Dispatcher
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

# ============ LOAD HANDLERS ============
logger.info("📦 Loading handlers directly...")
loaded_routers = []

handler_modules = [
    ("start", "bot.handlers.start"),
    ("profile", "bot.handlers.profile"),
    ("categories", "bot.handlers.categories"),
    ("parser_control", "bot.handlers.parser_control"),
    ("crm", "bot.handlers.crm"),
    ("calculator", "bot.handlers.calculator"),
    ("notifications", "bot.handlers.notifications"),
    ("subscription", "bot.handlers.subscription"),
    ("client_check", "bot.handlers.client_check"),
]

for name, module_path in handler_modules:
    try:
        import importlib
        module = importlib.import_module(module_path)
        router = getattr(module, "router")
        loaded_routers.append(router)
        logger.info(f"  ✅ {name}")
    except Exception as e:
        logger.error(f"  ❌ {name}: {e}")

logger.info(f"📦 Total: {len(loaded_routers)}/9 handlers")

# ============ BOT ============
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

for router in loaded_routers:
    dp.include_router(router)

logger.info(f"✅ {len(loaded_routers)} routers registered")


# ============ FASTAPI ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Freelance Radar Bot...")

    # DB
    try:
        await init_db()
        logger.info("✅ Database ready")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")

    # Scheduler
    try:
        from bot.services.scheduler import scheduler_service
        scheduler_service.start(bot)
        logger.info("✅ Scheduler started")
    except Exception as e:
        logger.error(f"❌ Scheduler error: {e}")

    # Webhook
    if config.WEBHOOK_URL:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("🗑 Old webhook deleted")

            webhook_url = f"{config.WEBHOOK_URL}/webhook"
            await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
            logger.info(f"✅ Webhook set: {webhook_url}")

            info = await bot.get_webhook_info()
            logger.info(f"📡 Webhook confirmed: url={info.url}")
            if info.last_error_message:
                logger.warning(f"⚠️ Last webhook error: {info.last_error_message}")
        except Exception as e:
            logger.error(f"❌ Webhook error: {e}, falling back to polling")
            asyncio.create_task(start_polling())
    else:
        asyncio.create_task(start_polling())
        logger.info("✅ Polling mode")

    logger.info("🟢 BOT IS READY!")
    yield

    # Shutdown
    logger.info("🔴 Shutting down...")
    try:
        from bot.services.scheduler import scheduler_service
        scheduler_service.stop()
    except Exception:
        pass
    try:
        await bot.delete_webhook()
    except Exception:
        pass
    await bot.session.close()


async def start_polling():
    await asyncio.sleep(2)
    try:
        logger.info("🔄 Starting polling...")
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

# Static
static_dir = os.path.join(os.path.dirname(__file__), "webapp", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# WebApp
try:
    from bot.webapp.app import webapp_router
    app.include_router(webapp_router)
    logger.info("✅ WebApp router loaded")
except Exception as e:
    logger.error(f"❌ WebApp: {e}")


# ============ ENDPOINTS ============
@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        update_data = await request.json()
        logger.info(f"📨 Update received: {list(update_data.keys())}")
        from aiogram.types import Update
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot=bot, update=update)
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return JSONResponse({"ok": False, "error": str(e)})


@app.get("/health")
async def health():
    return {"status": "ok", "handlers": len(loaded_routers)}


@app.get("/")
async def root():
    return {"message": "Freelance Radar Bot", "status": "running"}


@app.get("/debug/webhook")
async def debug_webhook():
    try:
        info = await bot.get_webhook_info()
        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": str(info.last_error_date) if info.last_error_date else None,
            "last_error_message": info.last_error_message,
            "max_connections": info.max_connections,
        }
    except Exception as e:
        return {"error": str(e)}


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
                    pay_r = await session.execute(
                        select(Payment).where(Payment.yookassa_id == payment_id)
                    )
                    pay = pay_r.scalar_one_or_none()
                    if pay:
                        pay.status = "succeeded"

                    user_r = await session.execute(
                        select(User).where(User.id == int(user_id))
                    )
                    user = user_r.scalar_one_or_none()
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
        logger.error(f"Payment error: {e}")
        return JSONResponse({"ok": False})


def main():
    uvicorn.run(app, host="0.0.0.0", port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
