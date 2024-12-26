from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Any
from abc import ABC, abstractmethod

@dataclass
class EntityDetail:
    id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_name: Optional[str] = None
    document_number: Optional[str] = None
    fe_ein_number: Optional[str] = None

    date_filed: Optional[date] = None
    effective_date: Optional[date] = None
    state: Optional[str] = None
    status: Optional[str] = None
    last_event: Optional[str] = None

    principal_address: Optional[str] = None
    principal_address_changed: Optional[date] = None
    principal_name_changed: Optional[date] = None
    mailing_address: Optional[str] = None
    mailing_address_changed: Optional[date] = None
    mailing_name_changed: Optional[date] = None

    registered_agent_name: Optional[str] = None
    registered_agent_address: Optional[str] = None
    registered_agent_address_changed: Optional[date] = None
    registered_agent_name_changed: Optional[date] = None
    
    authorized_persons: List[Any] = field(default_factory=list)
    annual_reports: List[Any] = field(default_factory=list)
    document_images: List[Any] = field(default_factory=list)

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EntityDao(ABC):
    @abstractmethod
    async def insert(self, entity: EntityDetail) -> int:
        pass

    @abstractmethod
    async def is_not_indexed(self, document_number: str) -> bool:
        pass