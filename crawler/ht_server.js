"use strict";
const io = require('socket.io')().listen(8855);
const htcap = require('htcrawl');
const Mutex = require('async-mutex').Mutex;
const {GetLinks, IsObjectEmpty} = require('./mylibs')

const options = {
  headlessChrome:1,
  navigationTimeout: 100000,
  triggerEvents: true
};
const mutex_newdom = new Mutex();
console.log("server started!");
// блокируем мьютекс
mutex_newdom.acquire().then();

async function send_discovered(socket, url, type, current_url) {
    socket.emit("discovered", {url, type, current_url});
}

async function send_links_collected(socket, urls) {
    socket.emit("links_collected", {urls});
}

async function send_initial_html(socket, full_html) {
    socket.emit("initial_html", {full_html});
}

async function send_new_dom(socket, selectors, events, current_url, full_html) {
    socket.emit("new_dom", {selectors, events, current_url, full_html});
}

async function send_events_and_selectors(socket, selectors, events, current_url, full_html) {
    socket.emit("want_to_analise", {selectors, events, current_url, full_html});
}

async function send_current_event_and_selector(socket, selector, event, current_url, full_html) {
    socket.emit("started_analise", {selector, event, current_url, full_html});
}

async function send_failed_analise(socket, selector, current_url) {
    socket.emit("failed_analise", {selector, current_url});
}

function send_finish(socket) {
    console.log("finish")
    socket.emit("finish", {});
}

// Навешиваем обработчик на подключение нового клиента
var true_socket = [];  // hack for correct restoring
// todo correct work with sockets
io.sockets.on('connection', async function (socket) {
  true_socket.push(socket)
  var events_whitelist = {} // url -> element -> event
  console.log('connection');
  socket.on('continue', async function (data) {
    console.log("continue signal");
    events_whitelist = data;
    mutex_newdom.release();
  });
  socket.on('new_task', async function (task) {
    if (task.events_whitelist) {
      events_whitelist = task.events_whitelist;
    }
    let process_communication = async function(e, crawler) {
        console.log(e.params.request.type + " to " + e.params.request.url);
        await send_discovered(true_socket[true_socket.length - 1], e.params.request.url, e.params.request.type, crawler.page().url());
    }
    let get_html = async function(crawler) {
      return await crawler.page().evaluate(() => document.body.innerHTML)
    }

    console.log('new_task')
    try {
      htcap.launch(task.url, options).then(crawler => {
        // TODO DEAL WITH SHADOW_ROOTS AND FRAMES
        // send out the url of ajax calls
        crawler.on("xhr", process_communication);
        crawler.on("fetch", process_communication);
        crawler.on("jsonp", process_communication);
        crawler.on("websocket", process_communication);

        crawler.on("pageInitialized", async (e, crawler) => {
          console.log("page initialized");
          try {
            let links = await GetLinks(crawler.page());
            await send_links_collected(true_socket[true_socket.length - 1], links);
            await send_initial_html(true_socket[true_socket.length - 1], await get_html(crawler));
          } catch (e) {
            console.log(e);
          }
          console.log("page initialized finished!");
        });
        crawler.on("start", async e => {
          console.log("crawler started");
        });
        crawler.on("dommodified", async (e, crawler) => {
          // it is time to create a checkpoint
          await send_links_collected(true_socket[true_socket.length - 1], await GetLinks(crawler.page()));
          await send_new_dom(true_socket[true_socket.length - 1], e.params.selectors, e.params.events, crawler.page().url(), await get_html(crawler));
          // console.log(crawler.page.remoteAddress().ip);
          await mutex_newdom.acquire();
          console.log("new dom");
        });
        crawler.on("navigation", async (e, crawler) => {
          console.log("navigation event");
        });
        crawler.on("redirect", async (e, crawler) => {
          console.log("redirect event");
        });


        crawler.on("want_to_analise", async (e, crawler) => {
          // here we need to restore and analise detached event
          console.log("want_to_analise event");
          await send_events_and_selectors(true_socket[true_socket.length - 1], e.params.selectors, e.params.events, crawler.page().url(), await get_html(crawler));
        });
        crawler.on("earlydetach", async (e, crawler) => {
          console.log("earlydetach event"); // todo correct it, becouse we dont know when it was detached
          await send_failed_analise(true_socket[true_socket.length - 1], e.params.node, crawler.page().url());
        });
        crawler.on("triggerevent", async (e, crawler) => {
          // here we need to jump to event that we want
          await send_current_event_and_selector(true_socket[true_socket.length - 1], e.params.node, e.params.event, crawler.page().url(), await get_html(crawler));
          if (IsObjectEmpty(events_whitelist)) {
            console.log("triggerevent event empty whitelist", e.params.event, e.params.node);
            return true;
          } else {
            let url = crawler.page().url()
            if (url in events_whitelist) {
              if (e.params.node in events_whitelist[url]) {
                if (events_whitelist[url][e.params.node].findIndex(x=> x === e.params.event) !== -1) {
                  console.log("triggerevent event in whitelist", e.params.event, e.params.node);
                  return true;
                }
              }
            } else {
              console.log("triggerevent event no url in whitelist", e.params.event, e.params.node);
              return true;
            }
            console.log("triggerevent canceled", e.params.event, e.params.node);
            return false;
          }
        });

        // Start crawling!
        crawler.start().then(() => send_finish(true_socket[true_socket.length - 1])).catch(() => send_finish(true_socket[true_socket.length - 1]));
      });
    } catch (e) {
      console.log(e);
    }
  });

  socket.emit("ready", {});

  socket.on('disconnect', async function() {
    console.log('loose connection');
  });
});
