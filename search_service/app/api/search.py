from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.db import DB
from app.models.entity import EntityDao
import asyncio
from dataclasses import asdict
import json 


search: APIRouter = APIRouter()

@search.websocket("/ws")
async def ws(websocket: WebSocket): 
    entity_dao: EntityDao = DB().entity_dao
    host = websocket.client.host
    print("Websocket connected with: ", host)
    current_search_term = ""
    await websocket.accept()
    async def send_entities():
        await entity_dao.register_notifier(current_search_term)
        print("Registered notifier for ", current_search_term)
        async for entity in entity_dao.listen(current_search_term):
            await websocket.send_text(json.dumps({"search_term": current_search_term, "new_entity": asdict(entity)}, default=str))
    try:
        while True:
            payload = await websocket.receive_json()
            print("Received payload: ", payload)
            data = json.loads(payload)
            if current_search_term != data["search_term"]:
                print("Changing search term from ", current_search_term, " to ", data["search_term"])
                if current_search_term != "":
                    await entity_dao.remove_notifier(current_search_term)
                print("Removed notifier for ", current_search_term)
                current_search_term = data["search_term"]
                entities = await entity_dao.search(current_search_term)
                print("Entities: ", entities)
                await websocket.send_text(json.dumps({"search_term": current_search_term, "entities": [asdict(entity) for entity in entities]}, default=str))
                asyncio.create_task(send_entities())
    except WebSocketDisconnect as wsd:
        print("Client disconnected: ", host)
        await entity_dao.remove_notifier(current_search_term)
    except Exception as e:
        print("An error occurred", e)
    finally:
        await websocket.close()