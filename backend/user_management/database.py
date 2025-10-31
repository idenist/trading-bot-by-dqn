class DatabaseConfig:
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "user"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "user_management_db"

class DatabaseConnection:
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None

    async def connect(self):
        # 실제 데이터베이스 연결 로직 구현
        # 예: self.connection = await asyncpg.connect(...)
        pass

    async def disconnect(self):
        # 실제 데이터베이스 연결 종료 로직 구현
        # 예: await self.connection.close()
        pass