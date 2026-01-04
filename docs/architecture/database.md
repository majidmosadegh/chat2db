# معماری ماژول Database

## نمای کلی (Overview)

ماژول **Database** لایه دسترسی به داده (Data Access Layer) پلتفرم SQL PT است که مسئولیت مدیریت اتصالات پایگاه داده، اجرای کوئری‌ها، و پیاده‌سازی الگوی Repository را بر عهده دارد. این ماژول با پیروی از اصول Clean Architecture، یک abstraction layer بین business logic و persistence layer فراهم می‌کند.

## معماری کلی (Architecture Overview)

```
┌─────────────────────────────────────────────────────────────┐
│                 Database Layer                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Repository Pattern                      │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │ Connections │ Snapshots   │   Schema        │    │    │
│  │  │ Repository  │ Repository  │   Repository    │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Connection Management                     │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │Engine Factory│  Connector  │   Dependencies │    │    │
│  │  │             │             │                 │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────────────┘
                      │
           ┌──────────┴──────────┐
           │   SQLAlchemy ORM    │
           │   (Persistence)     │
           └─────────────────────┘
```

## اجزاء اصلی (Core Components)

### 1. Repository Layer (الگوی Repository)

لایه abstraction برای دسترسی به داده‌ها:

#### ویژگی‌ها:
- **Domain Model Separation**: جداسازی مدل‌های دامنه از ORM models
- **Query Abstraction**: encapsulation منطق کوئری‌ها
- **Testability**: قابلیت تست مستقل از database
- **Consistency**: اعمال business rules در سطح data access

#### Repositoryهای اصلی:

##### **ConnectionsRepository**
```python
class ConnectionsRepository:
    async def get_by_id(self, session: AsyncSession, id: int) -> Optional[DatabaseConnection]
    async def get_active(self, session: AsyncSession) -> List[DatabaseConnection]
    async def create(self, session: AsyncSession, connection: DatabaseConnection) -> DatabaseConnection
    async def update(self, session: AsyncSession, id: int, connection: DatabaseConnection) -> DatabaseConnection
    async def delete(self, session: AsyncSession, id: int) -> bool
```

##### **SnapshotsRepository**
```python
class SnapshotsRepository:
    async def get_by_id(self, session: AsyncSession, id: int) -> Optional[Snapshot]
    async def get_by_connection(self, session: AsyncSession, connection_id: int) -> List[Snapshot]
    async def get_active(self, session: AsyncSession) -> List[Snapshot]
    async def create(self, session: AsyncSession, snapshot: SnapshotCreate) -> Snapshot
```

##### **SchemaRepository**
```python
class SchemaRepository:
    async def get_table_schema(self, session: AsyncSession, snapshot_id: int, table_name: str) -> Optional[TableSchema]
    async def get_all_tables(self, session: AsyncSession, snapshot_id: int) -> List[TableInfo]
    async def get_relationships(self, session: AsyncSession, snapshot_id: int) -> List[Relationship]
```

### 2. Connection Management

مدیریت اتصالات به پایگاه داده‌های مختلف:

#### Engine Factory
```python
class DatabaseEngineFactory:
    @staticmethod
    def create_engine(db_type: str, connection_string: str) -> Engine:
        """Create database engine based on type"""
        if db_type == "postgresql":
            return create_async_engine(connection_string, echo=False)
        elif db_type == "mysql":
            return create_async_engine(connection_string, echo=False)
        elif db_type == "sqlserver":
            return create_async_engine(connection_string, echo=False)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
```

#### Database Connector
```python
class DatabaseConnector:
    def __init__(self, snapshot_id: int):
        self.snapshot_id = snapshot_id
        self._engine = None
        self._connection = None

    async def connect(self, connection_params: Dict[str, Any]) -> None:
        """Establish database connection"""

    async def execute_query(self, sql: str, params: Optional[Dict] = None) -> QueryResult:
        """Execute SQL query safely"""

    async def close(self) -> None:
        """Close database connection"""
```

### 3. Dependency Injection

مدیریت وابستگی‌های database:

```python
def get_db_session() -> AsyncSession:
    """Database session dependency for FastAPI"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_repository(repo_class: Type[T]) -> T:
    """Generic repository dependency"""
    session = await get_db_session()
    return repo_class(session)
```

## مدل‌های داده (Data Models)

### Domain Models (مدل‌های دامنه)

مدل‌های Pydantic برای لایه business logic:

```python
class DatabaseConnection(BaseModel):
    id: int
    db_type: str  # postgresql, mysql, sqlserver
    host: str
    port: int
    username: str
    encrypted_password: str
    database_name: str
    is_active: bool = True

class Snapshot(BaseModel):
    id: int
    name: str
    database_connection_id: int
    created_at: datetime
    is_active: bool = False

class TableSchema(BaseModel):
    name: str
    columns: List[ColumnInfo]
    primary_key: Optional[str]
    indexes: List[str]
    constraints: List[str]
```

### ORM Models (مدل‌های SQLAlchemy)

مدل‌های persistence برای mapping به database:

```python
class DatabaseConnectionORM(Base):
    __tablename__ = "database_connections"

    id = Column(Integer, primary_key=True)
    db_type = Column(String(50), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(255), nullable=False)
    password_encrypted = Column(Text, nullable=False)
    database_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

## پشتیبانی از پایگاه داده‌ها (Database Support)

### PostgreSQL
```python
connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}"
engine = create_async_engine(connection_string, driver="asyncpg")
```

### MySQL
```python
connection_string = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
engine = create_async_engine(connection_string, driver="aiomysql")
```

### SQL Server
```python
connection_string = f"mssql+aioodbc://{username}:{password}@{host}:{port}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
engine = create_async_engine(connection_string, driver="aioodbc")
```

### SQLite (برای development)
```python
connection_string = "sqlite+aiosqlite:///./sqlpt.db"
engine = create_async_engine(connection_string, driver="aiosqlite")
```

## امنیت (Security)

### 1. **Encryption Management**
- رمزگذاری پسوردها با Fernet
- ذخیره امن connection strings
- Runtime decryption تنها

### 2. **SQL Injection Prevention**
- استفاده از parameterized queries
- Validation و sanitization ورودی‌ها
- Safe SQL generation

### 3. **Connection Security**
- SSL/TLS support
- Secure credential management
- Connection pool isolation

## Transaction Management

### Unit of Work Pattern
```python
class UnitOfWork:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.session.rollback()
        else:
            await self.session.commit()
```

### استفاده در business logic:
```python
async def create_connection(connection_data: DatabaseConnectionCreate):
    async with UnitOfWork(session) as uow:
        # Validate data
        # Create connection record
        # Update related entities
        # Automatic commit on success
        # Automatic rollback on failure
```

## Query Optimization

### 1. **Connection Pooling**
```python
engine = create_async_engine(
    connection_string,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600
)
```

### 2. **Query Result Caching**
```python
from functools import lru_cache
from typing import Dict, Any

@lru_cache(maxsize=100)
def get_table_schema_cache(snapshot_id: int, table_name: str) -> Dict[str, Any]:
    # Cache expensive schema queries
    pass
```

### 3. **Lazy Loading**
```python
# Only load related data when needed
snapshot = await snapshots_repo.get_by_id(session, snapshot_id)
if snapshot and include_schema:
    schema = await schema_repo.get_full_schema(session, snapshot_id)
```

## مانیتورینگ و Logging

### Database Metrics:
- Connection pool utilization
- Query execution times
- Transaction success rates
- Error rates by database type

### Logging:
```python
logger.info(f"DB_QUERY | Type: {db_type} | Duration: {duration}ms | SQL: {sql[:100]}...")
logger.warning(f"DB_CONNECTION_FAILED | Type: {db_type} | Host: {host} | Error: {error}")
logger.error(f"DB_TRANSACTION_ROLLBACK | Reason: {rollback_reason}")
```

## قابلیت توسعه (Extensibility)

### افزودن Database جدید:
```python
class NewDatabaseAdapter(DatabaseAdapter):
    def get_connection_string(self, params: Dict[str, Any]) -> str:
        return f"newdb://{params['username']}:{params['password']}@{params['host']}:{params['port']}/{params['database']}"

    def get_engine_config(self) -> Dict[str, Any]:
        return {"driver": "newdb_driver", "pool_size": 5}

    def validate_connection(self, connection) -> bool:
        # Custom validation logic
        pass
```

### افزودن Repository جدید:
```python
class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_operation(self, operation: str, user_id: int, details: Dict) -> None:
        audit_log = AuditLog(
            operation=operation,
            user_id=user_id,
            details=json.dumps(details),
            timestamp=datetime.utcnow()
        )
        self.session.add(audit_log)
```

## تنظیمات و Configuration

### Environment Variables:
```
DATABASE_URL=postgresql://user:pass@localhost:5432/sqlpt
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_ECHO_SQL=False
```

### Connection Configuration:
```python
db_config = {
    "postgresql": {
        "driver": "asyncpg",
        "pool_size": 10,
        "max_overflow": 20
    },
    "mysql": {
        "driver": "aiomysql",
        "pool_size": 5,
        "max_overflow": 10
    },
    "sqlserver": {
        "driver": "aioodbc",
        "pool_size": 3,
        "max_overflow": 5
    }
}
```

## مزایای معماری (Architecture Benefits)

### 1. **Abstraction**
- جداسازی business logic از persistence details
- قابلیت تغییر database بدون تغییر کد business
- Clean interfaces برای testing

### 2. **Performance**
- Connection pooling و optimization
- Query result caching
- Asynchronous operations

### 3. **Reliability**
- Transaction management
- Error handling و recovery
- Connection health monitoring

### 4. **Maintainability**
- Clear separation of concerns
- Repository pattern برای data access
- Type safety با Pydantic models

## چالش‌ها و محدودیت‌ها (Challenges & Limitations)

### 1. **N+1 Query Problem**
- نیاز به eager loading در complex queries
- Optimization برای related data loading

### 2. **Connection Pool Management**
- Resource limits در high-concurrency scenarios
- Connection timeout handling

### 3. **Schema Evolution**
- Database migration management
- Backward compatibility در schema changes

## بهبودهای آینده (Future Enhancements)

### 1. **Advanced Caching**
- Redis integration برای query caching
- In-memory cache برای metadata

### 2. **Read/Write Splitting**
- Separate read/write database connections
- Load balancing برای read operations

### 3. **Database Sharding**
- Horizontal scaling support
- Sharding strategy implementation

### 4. **Monitoring Enhancements**
- Real-time performance dashboards
- Slow query detection
- Automated optimization suggestions

---

**ماژول Database یک لایه data access قوی و scalable فراهم می‌کند که abstraction کاملی بین business logic و persistence layer ایجاد کرده و قابلیت توسعه و نگهداری آسان را تضمین می‌کند.**









