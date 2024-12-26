from psycopg import AsyncConnection
from typing import List, Awaitable, AsyncIterator
from app.models.entity import EntityDao, EntityDetail
from psycopg.rows import DictRow
import json


class IEntityDao(EntityDao):
    def __init__(self, conn: AsyncConnection[DictRow]):
        self.__conn = conn
        self.__registered_search_terms = []


    async def search(self, name: str) -> List[EntityDetail]:
        sql = """
SELECT
    id,
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
    document_images,
    created_at,
    updated_at
FROM entity_details
WHERE entity_name ILIKE %s
ORDER BY created_at DESC;
"""

        wildcard = f"%{name}%"
        async with self.__conn.cursor() as cur:
            await cur.execute(sql, (wildcard,))
            rows = await cur.fetchall()
            return [EntityDetail(**row) for row in rows]
        

    async def register_notifier(self, search_term: str) -> None:
        term = '_'.join(search_term.lower().split(' '))
        create_notifier_function = f"""
CREATE OR REPLACE FUNCTION notify_{term}_search() 
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify(entity_{term}_changes, new_to_json(NEW)::text);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;"""
        
        create_trigger = f"""
CREATE OR REPLACE TRIGGER {term}_search_notifier
AFTER INSERT ON entity_details FOR EACH ROW
WHEN (NEW.entity_name ILIKE '{search_term}')
EXECUTE FUNCTION notify_{term}_search();"""
        
        async with self.__conn.cursor() as cur:
            await cur.execute(create_notifier_function)
            await cur.execute(create_trigger)
            self.__registered_search_terms.append(search_term)
        await self.__conn.commit()
        

    async def remove_notifier(self, search_term: str) -> None:
        term = '_'.join(search_term.lower().split(' '))
        drop_trigger = f"DROP TRIGGER IF EXISTS {term}_search_notifier ON entity_details;"
        drop_function = f"DROP FUNCTION IF EXISTS notify_{term}_search();"
        async with self.__conn.cursor() as cur:
            await cur.execute(drop_trigger)
            await cur.execute(drop_function)
            self.__registered_search_terms.remove(search_term)
        await self.__conn.commit()

    
    async def listen(self, search_term: str) -> AsyncIterator[EntityDetail]:
        term = '_'.join(search_term.lower().split(' '))
        async with self.__conn.cursor() as cur:
            await cur.execute(f"LISTEN entity_{term}_changes;")
        await self.__conn.commit()
        print("Created listener for: ", search_term)
        async for msg in self.__conn.notifies(timeout=10):
            if search_term in self.__registered_search_terms:
                yield EntityDetail(**json.loads(msg.payload))
            else:
                break
        async with self.__conn.cursor() as cur:
            await cur.execute(f"UNLISTEN entity_{term}_changes;")
        await self.__conn.commit()
        print("Listener removed for: ", search_term)