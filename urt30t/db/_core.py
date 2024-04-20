import sqlalchemy.ext.asyncio

from .. import settings

engine = sqlalchemy.ext.asyncio.create_async_engine(
    url=settings.bot.db_url,
    echo=settings.bot.db_debug,
    echo_pool=settings.bot.db_debug,
)

session_maker = sqlalchemy.ext.asyncio.async_sessionmaker(
    engine, expire_on_commit=False
)
