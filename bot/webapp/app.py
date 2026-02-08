import json
import hashlib
import hmac
from datetime import datetime

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select

from bot.config import config
from bot.database import async_session
from bot.models import User, Order, Client, ParsedOrder
from bot.parsers.manager import parser_manager
from bot.services.gigachat import gigachat_service

webapp_router = APIRouter(prefix="/webapp", tags=["webapp"])


def verify_telegram_data(init_data: str) -> dict | None:
    """Проверка данных от Telegram Mini App"""
    try:
        parsed = dict(x.split("=", 1) for x in init_data.split("&"))
        check_hash = parsed.pop("hash", None)
        if not check_hash:
            return None

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )

        secret_key = hmac.new(
            b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if calculated_hash == check_hash:
            user_data = json.loads(parsed.get("user", "{}"))
            return user_data
        return None
    except Exception:
        return None


@webapp_router.get("/", response_class=HTMLResponse)
async def webapp_index():
    """Mini App главная страница"""
    import os
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@webapp_router.get("/api/user")
async def get_user(telegram_id: int = Query(...)):
    """Получить данные пользователя"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

    if not user:
        return JSONResponse({"error": "User not found"}, status_code=404)

    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "full_name": user.full_name,
        "bio": user.bio,
        "portfolio_url": user.portfolio_url,
        "hourly_rate": user.hourly_rate,
        "experience_years": user.experience_years,
        "categories": user.categories or [],
        "subscription_status": user.subscription_status,
        "has_subscription": user.has_active_subscription,
        "parser_active": user.parser_active,
        "notifications_enabled": user.notifications_enabled,
        "min_budget": user.min_budget,
        "orders_viewed": user.orders_viewed,
        "responses_sent": user.responses_sent,
        "orders_won": user.orders_won,
        "total_earned": user.total_earned,
    }


@webapp_router.get("/api/orders")
async def get_orders(telegram_id: int = Query(...), status: str = Query(None)):
    """Получить заказы пользователя из CRM"""
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        query = select(Order).where(Order.user_id == user.id)
        if status and status != "all":
            query = query.where(Order.status == status)
        query = query.order_by(Order.created_at.desc()).limit(50)

        orders_result = await session.execute(query)
        orders = orders_result.scalars().all()

    return [
        {
            "id": o.id,
            "title": o.title,
            "description": (o.description or "")[:200],
            "source": o.source,
            "budget": o.budget,
            "budget_value": o.budget_value,
            "url": o.url,
            "status": o.status,
            "my_price": o.my_price,
            "notes": o.notes,
            "client_name": o.client_name,
            "priority": o.priority,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]


@webapp_router.post("/api/orders/{order_id}/status")
async def update_order_status(order_id: int, request: Request):
    """Обновить статус заказа"""
    data = await request.json()
    new_status = data.get("status")

    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order:
            order.status = new_status
            await session.commit()
            return {"ok": True}
    return JSONResponse({"error": "Order not found"}, status_code=404)


@webapp_router.post("/api/orders/{order_id}/note")
async def update_order_note(order_id: int, request: Request):
    """Обновить заметку заказа"""
    data = await request.json()

    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order:
            order.notes = data.get("notes", "")[:1000]
            order.my_price = data.get("my_price", order.my_price)
            order.priority = data.get("priority", order.priority)
            await session.commit()
            return {"ok": True}
    return JSONResponse({"error": "Order not found"}, status_code=404)


@webapp_router.get("/api/feed")
async def get_feed(telegram_id: int = Query(...)):
    """Лента свежих заказов"""
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        result = await session.execute(
            select(ParsedOrder)
            .order_by(ParsedOrder.created_at.desc())
            .limit(30)
        )
        orders = result.scalars().all()

    return [
        {
            "id": o.id,
            "title": o.title,
            "description": (o.description or "")[:200],
            "source": o.source,
            "budget": o.budget,
            "budget_value": o.budget_value,
            "url": o.url,
            "client_name": o.client_name,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "hash": o.hash[:32],
        }
        for o in orders
    ]


@webapp_router.post("/api/generate-response")
async def generate_response_api(request: Request):
    """Генерация отклика через API"""
    data = await request.json()
    telegram_id = data.get("telegram_id")
    title = data.get("title", "")
    description = data.get("description", "")

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

    if not user or not user.has_active_subscription:
        return JSONResponse({"error": "Subscription required"}, status_code=403)

    try:
        response = await gigachat_service.generate_response(
            order_title=title,
            order_description=description,
            user_bio=user.bio or "",
            user_experience=user.experience_years or 0
        )
        return {"response": response}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@webapp_router.post("/api/calculate-price")
async def calculate_price_api(request: Request):
    """Калькулятор цены через API"""
    data = await request.json()
    description = data.get("description", "")
    category = data.get("category", "general")

    try:
        result = await gigachat_service.calculate_price(description, category)
        return {"result": result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@webapp_router.post("/api/check-client")
async def check_client_api(request: Request):
    """Проверка заказчика через API"""
    data = await request.json()
    client_info = data.get("info", "")

    try:
        result = await gigachat_service.analyze_client("Заказчик", client_info)
        return {"result": result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@webapp_router.get("/api/stats")
async def get_stats(telegram_id: int = Query(...)):
    """Статистика пользователя"""
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        orders_result = await session.execute(
            select(Order).where(Order.user_id == user.id)
        )
        orders = orders_result.scalars().all()

    statuses = {}
    for o in orders:
        statuses[o.status] = statuses.get(o.status, 0) + 1

    sources = {}
    for o in orders:
        sources[o.source] = sources.get(o.source, 0) + 1

    return {
        "orders_viewed": user.orders_viewed,
        "responses_sent": user.responses_sent,
        "orders_won": user.orders_won,
        "total_earned": user.total_earned,
        "total_orders": len(orders),
        "by_status": statuses,
        "by_source": sources,
        "parser_status": parser_manager.get_stats(),
    }


@webapp_router.post("/api/profile/update")
async def update_profile(request: Request):
    """Обновление профиля"""
    data = await request.json()
    telegram_id = data.get("telegram_id")

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        if "full_name" in data:
            user.full_name = data["full_name"][:200]
        if "bio" in data:
            user.bio = data["bio"][:1000]
        if "portfolio_url" in data:
            user.portfolio_url = data["portfolio_url"][:500]
        if "hourly_rate" in data:
            try:
                user.hourly_rate = float(data["hourly_rate"])
            except (ValueError, TypeError):
                pass
        if "experience_years" in data:
            try:
                user.experience_years = int(data["experience_years"])
            except (ValueError, TypeError):
                pass
        if "categories" in data:
            user.categories = data["categories"]

        await session.commit()
        return {"ok": True}


@webapp_router.post("/api/parser/toggle")
async def toggle_parser(request: Request):
    """Включить/выключить парсер"""
    data = await request.json()
    telegram_id = data.get("telegram_id")

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        user.parser_active = not user.parser_active
        await session.commit()
        return {"ok": True, "parser_active": user.parser_active}