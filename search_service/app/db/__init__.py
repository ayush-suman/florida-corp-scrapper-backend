import psycopg
from psycopg.rows import dict_row, DictRow
from app.db.entity import IEntityDao
from app.models.entity import EntityDao
from typing import Optional
import asyncio
import os
from app.utils.singleton import Singleton


class DB(metaclass=Singleton):
    __conn: psycopg.AsyncConnection[DictRow] = None
    __loop: Optional[asyncio.AbstractEventLoop] = None
    is_connected: bool = False

    def __init__(self, conn_str: Optional[str] = None):
        if self.__conn is None:
            if conn_str is None:
                conn_str = os.getenv("DATABASE_URL")
            
    async def connect(self, conn_str: str):
        if not self.is_connected:
            self.__conn = await psycopg.AsyncConnection.connect(conn_str, row_factory=dict_row)
            self.is_connected = True

    @property
    def entity_dao(self) -> EntityDao:
        if not self.is_connected:
            raise Exception("Database connection has not been established")
        return IEntityDao(self.__conn)
    

    async def dispose(self):
        self.__conn.close()
        self.__conn = None
        Singleton.dispose()
        self.__loop.stop()
        while self.__loop.is_running():
            await asyncio.sleep(0.1)
        self.__loop.close()