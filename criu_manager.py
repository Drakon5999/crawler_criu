import asyncio
import subprocess
import os
from collections import defaultdict
import time
import re
import html_utils


class CRIUElement:
    def __init__(self, cur_url, criu_dump_id, html_hash):
        self.html_hash = html_hash
        self.criu_dump_id = criu_dump_id
        self.cur_url = cur_url


# todo save database to file
class CRIUDataBase:
    def __init__(self):
        self.index_cur_url = defaultdict(list)
        self.index_html = defaultdict(list)
        self.index_html_plus_url = defaultdict(dict)
        self.index_dump_id = {}

    async def add(self, elem: CRIUElement):
        self.index_cur_url[elem.cur_url].append(elem)
        self.index_html[elem.html_hash].append(elem)
        self.index_dump_id[elem.criu_dump_id] = elem
        self.index_html_plus_url[elem.html_hash][elem.cur_url] = elem


class CRIUController:  # todo manage multiple pids
    CRIU_BASE_DIR = "/mnt/ramfs-folder"

    def __init__(self):
        self.proc_running = False
        self.is_restored = False
        self.current_proc = None
        self.current_dump = 0
        self.current_restored_parent = 0
        self.current_restored = 0

    async def run_new_crawler(self):
        self.is_restored = False
        assert not self.proc_running
        subprocess.call("rm -rf errlog.txt log.txt", shell=True)
        # todo try with asyncio.subprocess
        proc = subprocess.Popen("/usr/bin/node crawler/ht_server.js".split(), stdout=open("log.txt", "ab"),
                                stderr=open("errlog.txt", "ab"), stdin=open("hints.txt", "r"), start_new_session=True)
        await asyncio.sleep(0.1)  # todo remove it
        self.current_proc = proc.pid
        self.proc_running = True

    async def dump_process(self, keep_alive=False):
        dump_t = time.time()
        self.current_dump += 1
        track = False
        # if self.current_restored_parent != 0:
        #     track = True

        dirname = os.path.join(self.CRIU_BASE_DIR, str(self.current_dump))
        os.makedirs(dirname, mode=0o777, exist_ok=False)

        # destroy external sockets
        otp = (subprocess.check_output(['lsof', '+E', '-aUc', 'chrome'])).decode("utf-8")
        res = re.findall('(chrome.*dbus-daem)', otp)
        if res:
            external = res[0].split()[-4]
        else:
            external = None
            # print(res[-4])

        # --action-script "./tmp-files.sh ./user-dir/*"
        command = '{command} dump --tree {tree} --images-dir {dir} --shell-job --tcp-established --ext-unix-sk --ghost 1900M {keep} --track-mem {track} --file-locks {external}'.format(
                command='./criu-ns' if self.is_restored else 'criu',
                tree=self.current_proc,
                dir=dirname,
                keep="" if not keep_alive else "--leave-running",
                track="" if not track else "--prev-images-dir ../{}/".format(self.current_restored_parent),
                external="--external unix[{}]".format(external) if external else ''
            )
        print(command)
        returncode = subprocess.call(command.split())
        print("!!!!!!!DUMPTIME", time.time() - dump_t)
        # if returncode != 0:
        #     raise ChildProcessError("CRIU PROCESS ERROR!")
        self.current_restored_parent = self.current_restored
        self.current_restored = self.current_dump
        print("CRIU RETURN CODE", returncode)
        if not keep_alive:
            self.proc_running = False
        return self.current_restored, self.current_restored_parent

    async def kill(self):
        self.proc_running = False
        subprocess.call("kill -9 {}".format(self.current_proc), shell=True)
        subprocess.call("pkill -f node", shell=True)  # todo make it more accurate
        subprocess.call("pkill -f /usr/bin/node", shell=True)

    async def clean_images(self):
        self.proc_running = False
        return subprocess.call("rm -rf {}/*".format(self.CRIU_BASE_DIR), shell=True)

    async def restore_dump(self, dump_ids):
        dump_id, parent_id = dump_ids
        print("restoring!!!!")
        if self.proc_running:
            await self.kill()
        track = False
        # if parent_id:
        #     track = True
        subprocess.Popen(
            './criu-ns restore --images-dir {dir} --shell-job --tcp-established --ext-unix-sk --ghost 1900M --track-mem {track} --file-locks --tcp-close'.format(
                dir=os.path.join(self.CRIU_BASE_DIR, str(dump_id)),
                track="" if not track else "--prev-images-dir ../{}/".format(parent_id)
            ).split())

        self.is_restored = True
        self.current_restored = dump_id
        self.current_restored_parent = parent_id
        await asyncio.sleep(0.1)  # todo remove it
        # todo check that restored correctly
        self.proc_running = True
