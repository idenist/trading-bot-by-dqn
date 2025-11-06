from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from psycopg import errors as pg_errors

class UserNotFound(Exception):
    def __init__(self, message: str = "User not found"):
        self.message = message
        super().__init__(self.message)


async def fetch_user_by_email(db: AsyncConnectionPool.connection, email: str) -> dict | None:
    """
    이메일로 사용자 조회
    :param db: 데이터베이스 연결
    :param email: 사용자 이메일
    :return: 사용자 정보 딕셔너리. 에러 없이 리턴하는 경우 None이 아님을 보장.
    """
    query = "SELECT id, email, user_name, password_hash, token_version FROM users WHERE email = %s"
    async with db.cursor() as cur:
        await cur.execute(query, (email,))
        user = await cur.fetchone()
    if user is None:
        raise UserNotFound()
    return user

async def is_user_exists(db: AsyncConnectionPool.connection, email: str) -> bool:
    """이메일로 사용자가 존재하는지 확인합니다."""
    query = "SELECT 1 FROM users WHERE email = %s"
    async with db.cursor() as cur:
        await cur.execute(query, (email,))
        user = await cur.fetchone()
        print(user)
    return user is not None

async def update_user_token_version(db: AsyncConnectionPool.connection, user_id: int, new_token_version: int) -> None:
    """사용자의 토큰 버전을 업데이트합니다."""
    query = "UPDATE users SET token_version = %s WHERE id = %s"
    async with db.cursor() as cur:
        await cur.execute(query, (new_token_version, user_id))

async def create_user(db: AsyncConnectionPool.connection, email: str, user_name: str, password_hash: str) -> int:
    """새 사용자를 생성합니다."""
    query = """
    INSERT INTO users (email, user_name, password_hash, token_version)
    VALUES (%s, %s, %s, %s)
    RETURNING id
    """
    async with db.cursor() as cur:
        await cur.execute(query, (email, user_name, password_hash, 0))
        user_id = await cur.fetchone()
        return user_id['id']

async def delete_user(db: AsyncConnectionPool.connection, email: int) -> None:
    """사용자를 삭제합니다."""
    query = "DELETE FROM users WHERE email = %s"
    async with db.cursor() as cur:
        await cur.execute(query, (email,))