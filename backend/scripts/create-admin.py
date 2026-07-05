"""Идемпотентное создание/обновление админ-аккаунта для BI-дашборда /admin/bi.

Запуск (в контейнере backend):
    python /app/scripts/create-admin.py <email> <password>

Если пользователь с таким email уже существует — обновляет пароль.
Email должен присутствовать в settings.admin_emails, иначе аккаунт
создастся, но доступа к /admin/bi не получит (скрипт предупредит).
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models import EmailCredential  # noqa: E402
from app.services.identity.passwords import hash_password, normalize_email  # noqa: E402
from app.services.identity.service import register_email  # noqa: E402


async def main() -> None:
    if len(sys.argv) != 3:
        print("usage: create-admin.py <email> <password>")
        sys.exit(1)
    email, password = sys.argv[1], sys.argv[2]
    norm = normalize_email(email)

    allowed = {e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()}
    if norm not in allowed:
        print(f"WARNING: {norm} отсутствует в RUSTATS_ADMIN_EMAILS — доступа к /admin/bi не будет")

    async with async_session() as db:
        cred = await db.scalar(
            select(EmailCredential).where(EmailCredential.email == norm)
        )
        if cred is not None:
            cred.password_hash = hash_password(password)
            await db.commit()
            print(f"OK: пароль обновлён для существующего пользователя {norm}")
            return
        user = await register_email(db, norm, password)
        await db.commit()
        print(f"OK: создан пользователь {norm} (id={user.id})")


if __name__ == "__main__":
    asyncio.run(main())
