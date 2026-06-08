import asyncio
import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.database import get_db
import app.db.database as db_module  # Import the module to override its sessionmaker globally
from app.models.models import Base, Organization, User, DocumentType
from app.main import app
from app.core.security import get_password_hash
import uuid

# SQLite in-memory async database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

TestingSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Apply global sessionmaker override so that background tasks / agents use SQLite
db_module.async_session_maker = TestingSessionLocal

@pytest.fixture(scope="session", autouse=True)
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Initialize database tables once for the test session and seed core types."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    
    async def run_setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        async with TestingSessionLocal() as session:
            # Seed Org
            org = Organization(name="Test Org")
            session.add(org)
            await session.commit()
            await session.refresh(org)
            
            # Seed User
            user = User(
                id=uuid.UUID("77777777-7777-7777-7777-777777777777"),
                organization_id=org.id,
                email="test@acme.com",
                hashed_password=get_password_hash("test1234"),
                role="admin",
                is_active=True
            )
            session.add(user)
            
            # Seed Document Type
            doc_type = DocumentType(
                id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                organization_id=org.id,
                name="Invoice",
                schema_definition={"fields": [{"name": "invoice_number", "type": "string", "required": True}]}
            )
            session.add(doc_type)
            
            await session.commit()
            
    loop.run_until_complete(run_setup())
    loop.close()
    
    yield
    
    loop = asyncio.get_event_loop_policy().new_event_loop()
    async def run_teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    loop.run_until_complete(run_teardown())
    loop.close()

async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide scoped test DB session."""
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Apply the dependency override to the app
app.dependency_overrides[get_db] = override_get_db
