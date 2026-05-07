from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.base import Base

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _sqlite_enable_foreign_keys(dbapi_connection, connection_record) -> None:
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models.center  # noqa: F401
    import app.models.customer  # noqa: F401
    import app.models.customer_attachment  # noqa: F401
    import app.models.invoice  # noqa: F401
    import app.models.invoice_email_activity  # noqa: F401
    import app.models.generated_invoice  # noqa: F401
    import app.models.invoice_upload  # noqa: F401
    import app.models.product_and_service  # noqa: F401
    import app.models.user  # noqa: F401

    Base.metadata.create_all(bind=engine)
