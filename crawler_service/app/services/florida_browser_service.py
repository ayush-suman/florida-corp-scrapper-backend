from playwright.async_api import async_playwright, Playwright, Page, ElementHandle
from app.utils.singleton import Singleton
from typing import Optional, List, Callable, Awaitable, AsyncIterator
import asyncio
from app.models.entity import EntityDetail
from collections import deque
import time


class _PagePool:
    def __init__(self, max_count: int, page_factory: Callable[[], Awaitable[Page]], on_close: Callable[[], Awaitable[None]]):
        self.__pages: deque[Page] = deque([],  max_count)
        self.__max_count = max_count
        self.__page_count = 0
        self.__page_factory = page_factory
        self.is_closed = False
        self.__on_close = on_close
        self.__mutex = asyncio.Lock()


    def __await_for_page(self) -> Page:
        while(len(self.__pages) == 0):
            time.sleep(0.1)
        return self.__pages.pop()
    

    def resize_pool(self, max_count: int):
        if max_count < self.__max_count:
            raise ValueError("Cannot resize pool to a smaller size")
        self.__max_count = max_count
    

    async def get_page(self, start_url: str) -> Page:
        await self.__mutex.acquire()
        if self.__page_count < self.__max_count and len(self.__pages) == 0:
            page = await self.__page_factory()
            self.__page_count += 1
            self.__pages.append(page)
        self.__mutex.release()
        page = await asyncio.to_thread(self.__await_for_page)
        await page.goto(start_url, wait_until='domcontentloaded')
        return page


    def return_page(self, page: Page):
        self.__pages.append(page)


    async def close(self):
        for page in self.__pages:
            await page.close()
        await self.__on_close()
        self.is_closed = True



class FloridaBrowserService(metaclass=Singleton):
    BASE_URL = "https://search.sunbiz.org"
    BASE_SEARCH_URL = "https://search.sunbiz.org/Inquiry/CorporationSearch/ByName"
    is_ready: bool = False
    __page_pool: Optional[_PagePool] = None
    __loop: Optional[asyncio.AbstractEventLoop] = None

    def __init__(self, pool_size: int = 10):
        self.__page_pool_size = pool_size

    async def ensure_ready(self):
        if not self.is_ready:
            ctx_manager: Playwright = await async_playwright().start()
            browser = await ctx_manager.chromium.launch(headless=False)
            self.__page_pool = _PagePool(self.__page_pool_size, page_factory=browser.new_page, on_close=browser.close)
            self.is_ready = True


    async def __extract_address_block(page: Page, block_title: str) -> dict:
        result = {
            f"{block_title.lower().replace(' ', '_')}": None,
            f"{block_title.lower().replace(' ', '_')}_changed": None,
        }

        sections = await page.query_selector_all("div.detailSection")
        for section in sections:
            heading_span = await section.query_selector("span")
            if heading_span:
                heading_text = (await heading_span.inner_text()).strip()
                if heading_text == block_title:
                    spans = await section.query_selector_all("span")
                    if len(spans) > 1:
                        address_html = await spans[1].inner_html()
                        address_text = await spans[1].inner_text()
                        result[f"{block_title.lower().replace(' ', '_')}"] = address_text.strip()

                    changed_span = await section.query_selector('span:has-text("Changed:")')
                    if changed_span:
                        changed_text = await changed_span.inner_text()
                        changed_date = changed_text.replace("Changed:", "").strip()
                        result[f"{block_title.lower().replace(' ', '_')}_changed"] = changed_date
                    break

        return result
    
    
    async def __extract_registered_agent(page: Page) -> dict:
        result = {
            "registered_agent_name": None,
            "registered_agent_address": None,
            "registered_agent_address_changed": None,
            "registered_agent_name_changed": None
        }
        sections = await page.query_selector_all("div.detailSection")
        for section in sections:
            heading_span = await section.query_selector("span")
            if heading_span:
                heading_text = (await heading_span.inner_text()).strip()
                if "Registered Agent Name & Address" in heading_text:
                    print("Found registered agent section")
                    spans = await section.query_selector_all("span")
                    print("Got spans")
                    if len(spans) > 2:
                        agent_name = await spans[1].inner_text()
                        result["registered_agent_name"] = agent_name.strip()
                        print("Got agent name", agent_name.strip())

                        agent_addr_text = await spans[2].inner_text()
                        result["registered_agent_address"] = agent_addr_text.strip()
                        print("Got agent address", agent_addr_text.strip())
                
                    name_changed_span = await section.query_selector('span:has-text("Name Changed:")')
                    if name_changed_span:
                        print("Found name changed span")
                        changed_text = await name_changed_span.inner_text()
                        changed_date = changed_text.replace("Name Changed:", "").strip()
                        result["registered_agent_name_changed"] = changed_date
                        print("Got agent name changed date", changed_date)

                    address_changed_span = await section.query_selector('span:has-text("Address Changed:")')
                    if address_changed_span:
                        print("Found address changed span")
                        changed_text = await address_changed_span.inner_text()
                        changed_date = changed_text.replace("Address Changed:", "").strip()
                        result["registered_agent_address_changed"] = changed_date
                        print("Got agent address changed date", changed_date)

                    break
        return result
    

    async def __extract_annual_reports(page: Page) -> list:
        reports = []
        sections = await page.query_selector_all("div.detailSection")
        for section in sections:
            heading_span = await section.query_selector("span")
            if heading_span:
                heading_text = (await heading_span.inner_text()).strip()
                if "Annual Reports" in heading_text:
                    table = await section.query_selector("table")
                    if table:
                        rows = await table.query_selector_all("tr")
                        for row in rows[1:]:
                            cols = await row.query_selector_all("td")
                            if len(cols) == 2:
                                year = (await cols[0].inner_text()).strip()
                                filed_date = (await cols[1].inner_text()).strip()
                                reports.append({"year": year, "filed_date": filed_date})
                    break
        return reports


    async def __extract_authorized_persons(page: Page) -> list:
        persons = []
        sections = await page.query_selector_all("div.detailSection")
        for section in sections:
            heading_span = await section.query_selector("span")
            if heading_span:
                heading_text = (await heading_span.inner_text()).strip()
                if "Authorized Person(s) Detail" in heading_text or "Officer/Director Detail" in heading_text:
                    print("Found authorized persons section")
                    title_spans = await section.query_selector_all('span:has-text("Title")')
                    for span in title_spans:
                        title_text = await span.inner_text()
                        print("Title text: ", title_text)
                        name_text = await span.evaluate('el => el.nextSibling.nextSibling.nextSibling ? el.nextSibling.nextSibling.nextSibling.nodeValue : ""')
                        print("Name text: ", name_text)
                        address_span = await span.evaluate_handle('el => el.nextElementSibling.nextElementSibling.nextElementSibling && el.nextElementSibling.nextElementSibling.nextElementSibling.tagName === "SPAN" ? el.nextElementSibling.nextElementSibling.nextElementSibling : NONE')
                        if address_span != "NONE":
                            print("Address span: ", address_span)
                            address_span_text = await address_span.inner_text()
                            print("Address text: ", address_span_text)
                        else:
                            address_span_text = ""

                        title_str = title_text.replace("Title", "").strip()
                        persons.append({
                            "title": title_str,
                            "name": name_text or "",
                            "address": address_span_text.strip()
                        })
                    break
        return persons
    

    async def __extract_document_images(page: Page) -> list:
        docs = []
        sections = await page.query_selector_all("div.detailSection")
        for section in sections:
            heading_span = await section.query_selector("span")
            if heading_span:
                heading_text = (await heading_span.inner_text()).strip()
                if "Document Images" in heading_text:
                    table = await section.query_selector("table")
                    if table:
                        rows = await table.query_selector_all("tr")
                        for row in rows:
                            tds = await row.query_selector_all("td")
                            if tds:
                                link_el = await tds[0].query_selector("a")
                                if link_el:
                                    title = (await link_el.inner_text()).strip()
                                    href = await link_el.get_attribute("href")
                                    absolute_link = page.url.rsplit("/", 1)[0] + "/" + href.lstrip("/")
                                    docs.append({
                                        "title": title,
                                        "link": absolute_link
                                    })
                    break
        return docs


    async def search(self, name: str, should_index: Callable[[str], Awaitable[bool]]) -> AsyncIterator[EntityDetail]:
        if not self.is_ready:
            raise ValueError("Service is not ready. Await ensure_ready() first")
        page: Page = await self.__page_pool.get_page(self.BASE_SEARCH_URL)
        await page.wait_for_selector("input#SearchTerm")
        await page.locator('input#SearchTerm').fill(name)
        await page.click('input[type="submit"]')
        has_next = True
        while has_next:
            await page.wait_for_selector("div#search-results table")
            rows = await page.query_selector_all("div#search-results table tbody tr")
            queue: asyncio.Queue = asyncio.Queue()

        
            async def get_details(row: ElementHandle):
                cells = await row.query_selector_all("td")
                corp_name_el = await cells[0].query_selector("a")
                print(corp_name_el)
                if corp_name_el:
                    document_number = await cells[1].inner_text()
                    if not await should_index(document_number):
                        print("Document already indexed. Skipping...")
                        await queue.put(None)
                        return
                    print("Document not indexed. Proceeding")
                    status = await cells[2].inner_text()
                    detail_href = await corp_name_el.get_attribute("href")
                    detail_url = self.BASE_URL + detail_href
                    new_page = await self.__page_pool.get_page(detail_url)
                    await new_page.wait_for_selector("div.searchResultDetail")
                    entity_type_selector = "div.detailSection.corporationName p:nth-of-type(1)"
                    entity_name_selector = "div.detailSection.corporationName p:nth-of-type(2)"
                    entity_type = await new_page.inner_text(entity_type_selector)
                    entity_name = await new_page.inner_text(entity_name_selector)

                    async def get_labeled_data(label: str) -> Optional[str]:
                        label_selector = f'label:has-text("{label}")'
                        label_el = await new_page.query_selector(label_selector)
                        if not label_el:
                            return None
                        span_el = await label_el.evaluate_handle('el => el.nextElementSibling')
                        if span_el:
                            data = await span_el.inner_text()
                            return data.strip()
                        return None
                    try:
                        doc_number = await get_labeled_data("Document Number")
                        fei_ein_number = await get_labeled_data("FEI/EIN Number")
                        date_filed = await get_labeled_data("Date Filed")
                        state = await get_labeled_data("State")
                        status = await get_labeled_data("Status")
                        last_event = await get_labeled_data("Last Event")
                        effective_date = await get_labeled_data("Effective Date Filed")

                        principal_address_data = await FloridaBrowserService.__extract_address_block(new_page, "Principal Address")
                        mailing_address_data = await FloridaBrowserService.__extract_address_block(new_page, "Mailing Address")
                        registered_agent_data = await FloridaBrowserService.__extract_registered_agent(new_page)
                        authorized_persons = await FloridaBrowserService.__extract_authorized_persons(new_page)
                        annual_reports = await FloridaBrowserService.__extract_annual_reports(new_page)
                        document_images = await FloridaBrowserService.__extract_document_images(new_page)
                    
                        entity_detail = EntityDetail(
                            entity_type=entity_type,
                            entity_name=entity_name,
                            document_number=doc_number,
                            fe_ein_number=fei_ein_number,
                            date_filed=date_filed,
                            effective_date=effective_date,
                            state=state,
                            status=status,
                            last_event=last_event,
                            **principal_address_data,
                            **mailing_address_data,
                            **registered_agent_data,
                            authorized_persons=authorized_persons,
                            annual_reports=annual_reports,
                            document_images=document_images
                        )
                    except Exception as e:
                        print("Error creating entity detail: ", e.with_traceback())
                        entity_detail = None
                    await queue.put(entity_detail)
                    self.__page_pool.return_page(new_page)

            for row in rows:
                asyncio.create_task(get_details(row))

            for _ in range(len(rows)):
                entity = await queue.get()
                yield entity
                queue.task_done()
            next = await page.query_selector("a:has-text('Next List')")
            if next:
                await next.click()
            else:
                has_next = False
        self.__page_pool.return_page(page)
    

    async def close(self):
        await self.__page_pool.close()
        self.__loop.stop()
        while self.__loop.is_running():
            await asyncio.sleep(0.1)
        self.__loop.close()
    



        