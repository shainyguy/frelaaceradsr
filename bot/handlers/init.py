from aiogram import Router


def get_all_routers() -> list[Router]:
    """
    Ленивый импорт всех роутеров.
    Каждый импорт внутри функции — чтобы избежать
    циклических зависимостей при старте.
    """
    routers = []

    try:
        from bot.handlers.start import router as start_router
        routers.append(start_router)
        print("  ✅ start handler loaded")
    except Exception as e:
        print(f"  ❌ start handler failed: {e}")

    try:
        from bot.handlers.profile import router as profile_router
        routers.append(profile_router)
        print("  ✅ profile handler loaded")
    except Exception as e:
        print(f"  ❌ profile handler failed: {e}")

    try:
        from bot.handlers.categories import router as categories_router
        routers.append(categories_router)
        print("  ✅ categories handler loaded")
    except Exception as e:
        print(f"  ❌ categories handler failed: {e}")

    try:
        from bot.handlers.parser_control import router as parser_router
        routers.append(parser_router)
        print("  ✅ parser_control handler loaded")
    except Exception as e:
        print(f"  ❌ parser_control handler failed: {e}")

    try:
        from bot.handlers.crm import router as crm_router
        routers.append(crm_router)
        print("  ✅ crm handler loaded")
    except Exception as e:
        print(f"  ❌ crm handler failed: {e}")

    try:
        from bot.handlers.calculator import router as calculator_router
        routers.append(calculator_router)
        print("  ✅ calculator handler loaded")
    except Exception as e:
        print(f"  ❌ calculator handler failed: {e}")

    try:
        from bot.handlers.notifications import router as notifications_router
        routers.append(notifications_router)
        print("  ✅ notifications handler loaded")
    except Exception as e:
        print(f"  ❌ notifications handler failed: {e}")

    try:
        from bot.handlers.subscription import router as subscription_router
        routers.append(subscription_router)
        print("  ✅ subscription handler loaded")
    except Exception as e:
        print(f"  ❌ subscription handler failed: {e}")

    try:
        from bot.handlers.client_check import router as client_check_router
        routers.append(client_check_router)
        print("  ✅ client_check handler loaded")
    except Exception as e:
        print(f"  ❌ client_check handler failed: {e}")

    print(f"\n📦 Loaded {len(routers)}/9 handlers")
    return routers
