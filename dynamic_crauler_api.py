from collections import defaultdict

import socketio
import asyncio

import html_utils
from url import Url
import criu_manager


class DynamicAPI:
    def __init__(self, criu=False):
        self.criu = criu
        if self.criu:
            self.CRIUDataBase = criu_manager.CRIUDataBase()
            self.CRIUController = criu_manager.CRIUController()
            self.initial_dump = None

        self.CompletedTasks = []
        self.sio = socketio.AsyncClient()
        self.finished = False

        self.ServerReadyLock = asyncio.Lock()
        self.TaskCompleteLock = asyncio.Lock()
        self.AnalysedLock = asyncio.Lock()
        self.FirstReady = True
        self.connected = False
        self.PendingUrls = set()
        self.DiscoveredUrls = defaultdict(set)  # ajax calls etc
        self.UrlsCollected = set()  # <a> from page
        self.UrlsCollectedRaw = set()
        self.IsServerReady = asyncio.Event()
        self.IsTaskComplete = asyncio.Event()
        self.WhiteListEvents = defaultdict(lambda: defaultdict(list))  # url -> selector -> event
        self.CRIUWhiteListEvents = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # html -> url ...
        self.AnalysedEvents = defaultdict(lambda: defaultdict(list))
        self.sio.on("connect", self._connect)
        self.sio.on("disconnect", self._disconnect)
        self.sio.on("message", self._message)
        self.sio.on("ready", self._ready)
        self.sio.on("error", self._error)
        self.sio.on("discovered", self._discovered)
        self.sio.on("links_collected", self._links_collected)
        self.sio.on("new_dom", self._new_dom)
        self.sio.on("want_to_analise", self._want_to_analise)
        self.sio.on("started_analise", self._started_analise)
        self.sio.on("failed_analise", self._failed_analise)
        self.sio.on("initial_html", self._initial_html)
        self.sio.on("finish", self._finish)

    async def init(self):
        if self.criu:
            await self.CRIUController.clean_images()
            await self.CRIUController.run_new_crawler()

        while not self.connected:
            try:
                await self.sio.connect('http://localhost:8855', wait_timeout=10)
                if self.criu:
                    self.initial_dump = await self.CRIUController.dump_process(keep_alive=True)
            except:
                await asyncio.sleep(1)
                print("another connect try")
        return self

    async def _collect_url(self, url):
        self.UrlsCollected.add(await (Url()).from_string(url))
        self.UrlsCollectedRaw.add(url)

    async def _initial_html(self, data):
        # todo realize it
        pass

    async def _add_to_whitelist(self, current_url, selectors, events, full_html):
        # print(current_url, current_url in self.AnalysedEvents, events)
        async with self.AnalysedLock:
            for sel in selectors:
                for ev in events[sel]:
                    if ev not in self.AnalysedEvents[current_url][sel]:
                        if ev not in self.WhiteListEvents[current_url][sel]:
                            self.WhiteListEvents[current_url][sel].append(ev)
                            if self.criu:
                                full_html = html_utils.get_html_hash(full_html)
                                self.CRIUWhiteListEvents[full_html][current_url][sel].append(ev)

    async def _finish(self, data):
        print("got finish")
        self.finished = True
        self.IsTaskComplete.set()
        self.PendingUrls.clear()

    async def _links_collected(self, data):
        for url in data['urls']:
            await self._collect_url(url)

    async def _new_dom(self, data):
        await self._collect_url(data['current_url'])
        await self._add_to_whitelist(**data)
        print('NEW DOM!')
        html_utils.get_html_hash(data['full_html'])
        if self.criu:
            dump_id = await self.CRIUController.dump_process(keep_alive=True)
            criu_el = criu_manager.CRIUElement(
                cur_url=data['current_url'],
                criu_dump_id=dump_id,
                html_hash=html_utils.get_html_hash(data['full_html'])
            )
            await self.CRIUDataBase.add(criu_el)

        await self.send_continue()

    async def _want_to_analise(self, data):
        await self._collect_url(data['current_url'])
        await self._add_to_whitelist(**data)

    async def _started_analise(self, data):
        # print(data)
        async with self.AnalysedLock:
            self.AnalysedEvents[data['current_url']][data['selector']].append(data['event'])
            if data['event'] in self.WhiteListEvents[data['current_url']][data['selector']]:
                self.WhiteListEvents[data['current_url']][data['selector']].remove(data['event'])
                if self.criu:
                    full_html = html_utils.get_html_hash(data['full_html'])
                    self.CRIUWhiteListEvents[full_html][data['current_url']][data['selector']].remove(data['event'])

    async def _failed_analise(self, data):
        # todo we will return to it later
        pass

    async def _connect(self):
        self.connected = True
        print('connection established')

    async def _disconnect(self):
        async with self.ServerReadyLock:
            self.IsServerReady.clear()
        # TODO: realize task resending
        print('disconnected from server, we are trying to reconnect')

    async def _message(self, data):
        print('message received with ', data)

    async def _ready(self, data):
        print('Server is ready!')
        async with self.ServerReadyLock:
            self.IsServerReady.set()
            if self.FirstReady:
                self.FirstReady = False
                return
        print("going to send url", self.PendingUrls)
        async with self.TaskCompleteLock:
            for url in self.PendingUrls:
                await self._add_url(url)

    async def _error(self, data):
        print('some error')

    async def _discovered(self, data):
        cur_url = data['current_url']
        del data['current_url']
        self.DiscoveredUrls[cur_url].add(data['url'])

    async def add_task(self, task):
        self.finished = False
        await self.IsServerReady.wait()
        async with self.ServerReadyLock:
            if self.IsServerReady.is_set():
                task['events_whitelist'] = self.WhiteListEvents
                await self.sio.emit('new_task', task)

    async def get_results(self):
        await self.IsTaskComplete.wait()
        async with self.TaskCompleteLock:
            if self.IsTaskComplete.is_set():
                completed_tasks = self.CompletedTasks
                self.CompletedTasks = []
                self.IsTaskComplete.clear()
                return completed_tasks

    async def destroy(self):
        await self.sio.disconnect()
        if self.criu:
            await self.CRIUController.kill()

    async def add_url(self, url):
        async with self.TaskCompleteLock:
            self.PendingUrls.add(url)
            await self._add_url(url)

    async def add_criu(self, task):
        html_hash, url = task
        assert len(self.PendingUrls) == 0
        if not self.criu:
            return

        if url in self.CRIUDataBase.index_html_plus_url[html_hash]:
            await self.CRIUController.restore_dump(self.CRIUDataBase.index_html_plus_url[html_hash][url].criu_dump_id)
            await self.send_continue()
        else:
            await self.CRIUController.restore_dump(self.initial_dump)
            print("ADDING URL", url)
            await self.add_url(url)

    async def _add_url(self, url):
        await self.add_task(await self.create_task(url))

    async def create_task(self, url):
        return {'url': url}

    async def send_continue(self):
        async with self.AnalysedLock:
            await self.sio.emit("continue", self.WhiteListEvents)
            pass

    async def get_whitelist_not_empty(self):
        if self.criu:
            for html in self.CRIUWhiteListEvents:
                for url in self.WhiteListEvents:
                    for el in self.WhiteListEvents[url]:
                        if len(self.WhiteListEvents[url][el]) > 0:
                            return html, url
            return None, None
        else:
            for url in self.WhiteListEvents:
                for el in self.WhiteListEvents[url]:
                    if len(self.WhiteListEvents[url][el]) > 0:
                        return url

            return None


async def test_main():
    # api = await (DynamicAPI().init())
    # await api.add_task({"url": "https://translate.yandex.ru"})
    # # await api.add_task({"url": "https://security-crawl-maze.app/javascript/frameworks/angular/"})
    # # await asyncio.sleep(5)
    # # print("send continue")
    # # await api.send_continue()
    # # print("wait")
    # results = await api.get_results()
    # # print("got it")
    # # await asyncio.sleep(50)
    #
    # # # print(results)
    # # print("restoring...")
    # # print("send continue")
    # # await api.sio.wait()
    # await api.destroy()

    pass


if __name__ == '__main__':
    asyncio.run(test_main())
