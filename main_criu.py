import asyncio
import time
from queue import Queue
from dynamic_crauler_api import DynamicAPI
from pprint import pprint

from url import Url


async def main():
    api = await (DynamicAPI(criu=True).init())
    speedtest_timer = time.time()
    visited_urls = set()
    to_visit_urls = set()
    urls_queue = Queue()

    start_url = 'https://music.yandex.ru'
    FILTER = 'https://music.yandex.ru'
    urls_queue.put(start_url)
    visited_urls.add(start_url)
    limitoj = 5
    while limitoj and not urls_queue.empty():
        limitoj -= 1
        url = urls_queue.get()
        if isinstance(url, str):
            print("Scanning", url)
            await api.add_url(url)
        else:
            print("restoring criu", url)
            await api.add_criu(url)
            url = url[1]

        await api.get_results()
        visited_urls.add(url)

        if urls_queue.empty():
            addition_url = await api.get_whitelist_not_empty()
            if addition_url[1] is not None and addition_url[1].startswith(FILTER):
                urls_queue.put(addition_url)
                continue

        for link in api.UrlsCollectedRaw:
            link = str(link)

            # print(link,link.startswith('https://security-crawl-maze.app'))
            if link.startswith(FILTER):
                if link not in visited_urls and link not in to_visit_urls:
                    urls_queue.put(link)
                    to_visit_urls.add(link)
    print()
    print("urls collected")
    pprint(api.UrlsCollectedRaw)
    print()
    print("urls discovered")
    pprint(api.DiscoveredUrls)
    print()
    print("events whitelist")
    pprint(api.WhiteListEvents)
    print()
    print("analysed events")
    pprint(api.AnalysedEvents)
    print("Result timer ", time.time() - speedtest_timer)
    await api.destroy()


if __name__ == '__main__':
    asyncio.run(main())
