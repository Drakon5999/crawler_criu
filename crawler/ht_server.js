"use strict";
let io = require('socket.io')().listen(8855);
let htcap = require('htcrawl');
let Mutex = require('async-mutex').Mutex;

const options = {
  headlessChrome:1,
  navigationTimeout: 100000,
  triggerEvents: true
};
const mutex_newdom = new Mutex();
console.log("server started!");
// блокируем мьютекс
mutex_newdom.acquire().then();

// Навешиваем обработчик на подключение нового клиента
io.sockets.on('connection', async function (socket) {
  console.log('connection');
  // let ID = (socket.id).toString().substr(0, 5);
  //
  socket.on('continue', async function (data) {
    console.log("continue signal");
    mutex_newdom.release();
  });
  socket.on('new_task', async function (task) {
    try {
      console.time(task.url);
    } catch (err) {
      console.log("timer already exist");
    }

    console.log('new_task')
    htcap.launch(task.url, options).then(crawler => {
      // Print out the url of ajax calls
      crawler.on("xhr", e => {
        console.log("XHR to " + e.params.request.url);
      });
      crawler.on("pageInitialized", e => {
        console.log("page initialized");
      });
      crawler.on("start", e => {
        console.log("crawler started");
      });
      crawler.on("newdom", async (e, crawler) => {

        await mutex_newdom.runExclusive(async () => {
          console.log("new dom");
        });
      });

      // Start crawling!
      crawler.start();
    });
  });

  socket.emit("ready", {});

  socket.on('disconnect', async function() {
    console.log('loose connection');
  });
});
