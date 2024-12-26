from app.services.florida_browser_service import FloridaBrowserService
from app.db import DB
from app.models.entity import EntityDao
from fastapi import APIRouter, Body
from typing import Annotated
import asyncio


crawler: APIRouter = APIRouter()
florida_browser_service: FloridaBrowserService = FloridaBrowserService()


@crawler.post("/initiate_crawl", status_code=201)
async def initiate_crawl(search_term: str = Body(..., embed=True)): 
    await florida_browser_service.ensure_ready()
    entity_dao: EntityDao = DB().entity_dao
    async def crawl():
        async for entity in florida_browser_service.search(search_term, entity_dao.is_not_indexed):
            if entity:
                await entity_dao.insert(entity)
    asyncio.create_task(crawl())
    return {"message": "Crawl initiated"}
