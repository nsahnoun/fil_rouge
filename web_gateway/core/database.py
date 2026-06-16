from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    import web_gateway.models  # noqa: F401 register tables with Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_db():
    from ..models import Role
    from sqlalchemy import select
    async with async_session() as session:
        existing = await session.execute(select(Role).limit(1))
        if existing.scalar():
            return
        roles = [
            Role(name="admin", permissions='{"all":["*"]}'),
            Role(name="orthodontist", permissions='{"patients":["read","write","analyze"],"reports":["generate","sign"],"analyses":["full"]}'),
            Role(name="assistant", permissions='{"patients":["read","write"],"analyses":["read"],"reports":["read"]}'),
            Role(name="intern", permissions='{"patients":["read"],"analyses":["read"],"reports":["read"]}'),
        ]
        session.add_all(roles)
        await session.commit()
