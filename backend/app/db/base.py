from sqlalchemy.orm import DeclarativeBase
# Import all models so SQLAlchemy/Alembic can discover them.

class Base(DeclarativeBase):
    pass
