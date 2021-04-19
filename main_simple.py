import asyncio
import time
from queue import Queue
from dynamic_crauler_api import DynamicAPI
from pprint import pprint


async def main():
    speedtest_timer = time.time()
    api = await (DynamicAPI().init())
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
        print("Scanning", url)
        await api.add_url(url)
        await api.get_results()
        visited_urls.add(url)

        for link in api.UrlsCollectedRaw:
            link = str(link)
            # print(link,link.startswith('https://security-crawl-maze.app'))
            if link.startswith(FILTER):
                if link not in visited_urls and link not in to_visit_urls:
                    urls_queue.put(link)
                    to_visit_urls.add(link)

        if urls_queue.empty():
            addition_url = await api.get_whitelist_not_empty()
            if addition_url is not None and addition_url.startswith(FILTER):
                urls_queue.put(addition_url)

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
