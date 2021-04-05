const {trim, uniq, startsWith, includes} = require("lodash");
const { parse } = require('url');

function resolve(from, to) {
  const resolvedUrl = new URL(to, new URL(from, 'resolve://'));
  if (resolvedUrl.protocol === 'resolve:') {
    // `from` is a relative URL.
    const { pathname, search, hash } = resolvedUrl;
    return pathname + search + hash;
  }
  return resolvedUrl.toString();
}


/**
* @param {!string} url
* @param {!string} baseUrl
* @return {!string}
*/
function resolveUrl(url, baseUrl) {
    url = trim(url);
    if (!url) return null;
    if (startsWith(url, '#')) return null;
    const { protocol } = parse(url);
    if (includes(['http:', 'https:'], protocol)) {
      return url.split('#')[0];
    } else if (!protocol) { // eslint-disable-line no-else-return
      return resolve(baseUrl, url).split('#')[0];
    }
    return null;
}

let GetElementsHandlers = async function* (ArrayJsHandle, page) {
    let arrayLen = await page.evaluate(a => a.length, ArrayJsHandle);
    for (let i = 0; i < arrayLen; i++) {
        yield await page.evaluateHandle(function (arr, i) {
            return arr[i];
        }, ArrayJsHandle, i)
    }
}

function collectAllElementsDeep(selector = null) {
    const allElements = [];

    const findAllElements = function(nodes) {
        for (let i = 0, el; el = nodes[i]; ++i) {
            allElements.push(el);
            // If the element has a shadow root, dig deeper.
            if (el.shadowRoot) {
                findAllElements(el.shadowRoot.querySelectorAll('*'));
            }
        }
    };

    findAllElements(document.querySelectorAll('*'));

    return selector ? allElements.filter(el => el.matches(selector)) : allElements;
}

let GetLinks = async function (page) {
    const current_url = page.url()
    let JsArrayHandle;
    try {
        JsArrayHandle = await page.evaluateHandle(collectAllElementsDeep, 'a');
    } catch (e) {
        // there was a page navigation
        return [];
    }

    const elementHandlesGenerator = await GetElementsHandlers(JsArrayHandle, page);
    const elementHandles = [];
    for await (let dom of elementHandlesGenerator) {
        elementHandles.push(dom);
    }

    const propertyJsHandles = await Promise.all(
        elementHandles.map(handle => handle.getProperty('href'))
    );
    const hrefs = await Promise.all(
        propertyJsHandles.map(handle => handle.jsonValue())
    );

    let filtered = hrefs.filter(function (el) {
        return el != null && el != "";
    });
    let resultUrls = filtered.map(href => resolveUrl(href, current_url))
    return uniq(resultUrls);
}

var hasOwnProperty = Object.prototype.hasOwnProperty;

function IsObjectEmpty(obj) {

    // null and undefined are "empty"
    if (obj == null) return true;

    // Assume if it has a length property with a non-zero value
    // that that property is correct.
    if (obj.length > 0)    return false;
    if (obj.length === 0)  return true;

    // If it isn't an object at this point
    // it is empty, but it can't be anything *but* empty
    // Is it empty?  Depends on your application.
    if (typeof obj !== "object") return true;

    // Otherwise, does it have any properties of its own?
    // Note that this doesn't handle
    // toString and valueOf enumeration bugs in IE < 9
    for (var key in obj) {
        if (hasOwnProperty.call(obj, key)) return false;
    }

    return true;
}



module.exports = {
    GetLinks,
    IsObjectEmpty
}
