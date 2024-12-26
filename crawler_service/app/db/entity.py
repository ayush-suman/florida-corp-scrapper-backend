from psycopg import AsyncConnection
from typing import Awaitable
from app.models.entity import EntityDao, EntityDetail
from psycopg.rows import DictRow
from dataclasses import asdict
import json

class IEntityDao(EntityDao):
    def __init__(self, conn: AsyncConnection[DictRow]):
        self.__conn = conn

    async def insert(self, detail: EntityDetail) -> int:
        query = """
        INSERT INTO entity_details (
            entity_type,
            entity_name,
            document_number,
            fe_ein_number,
            date_filed,
            effective_date,
            state,
            status,
            principal_address,
            principal_address_changed,
            mailing_address,
            mailing_address_changed,
            registered_agent_name,
            registered_agent_address,
            registered_agent_address_changed,
            authorized_persons,
            annual_reports,
            document_images
        ) VALUES (
            %(entity_type)s,
            %(entity_name)s,
            %(document_number)s,
            %(fe_ein_number)s,
            %(date_filed)s,
            %(effective_date)s,
            %(state)s,
            %(status)s,
            %(principal_address)s,
            %(principal_address_changed)s,
            %(mailing_address)s,
            %(mailing_address_changed)s,
            %(registered_agent_name)s,
            %(registered_agent_address)s,
            %(registered_agent_address_changed)s,
            to_jsonb(%(authorized_persons)s::json),
            to_jsonb(%(annual_reports)s::json),
            to_jsonb(%(document_images)s::json)
        )
        RETURNING id;
        """

        async with self.__conn.cursor() as cur:
            data = asdict(detail)
            data["authorized_persons"] = json.dumps(data["authorized_persons"])
            data["annual_reports"] = json.dumps(data["annual_reports"])
            data["document_images"] = json.dumps(data["document_images"])
            print(data)
            await cur.execute(query, dict(data))
            row = await cur.fetchone()
            print("Inserted with id: ", row["id"])
            await self.__conn.commit()
            return row["id"]
        

    async def is_not_indexed(self, document_number: str) -> bool:
        sql = "SELECT id FROM entity_details WHERE document_number = %s;"
        async with self.__conn.cursor() as cur:
            await cur.execute(sql, (document_number,))
            return not bool(await cur.fetchone())