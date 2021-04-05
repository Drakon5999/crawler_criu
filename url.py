from urllib3.util import parse_url


class Url(object):
    def __init__(self):
        self.scheme = None
        self.host = None
        self.port = None
        self.path = None
        self.query = None
        self._params_cache = None
        self.params_list = None
        self.fragment = None
        self._hash = None
        self._params_string_cache = None

    @property
    def _params_string(self):
        if self._params_string_cache is None:
            if self.params_list:
                self._params_string_cache = "?" + "&".join(self.params_list)
            else:
                self._params_string_cache = ""
        return self._params_string_cache

    @property
    def params(self):
        if self._params_cache is None and self.params_list is not None:
            self._params_cache = dict()
            for param in self.params_list:
                kv = param.split('=', 1)
                if len(kv) == 1:
                    self._params_cache[kv[0]] = None
                else:
                    self._params_cache[kv[0]] = self.params[kv[1]]
        else:
            self._params_cache = dict()
        return self._params_cache

    async def from_options(self, host, scheme=None, port=None, path=None, fragment=None, query=None):
        self.host = host.lower()
        self.scheme = scheme.lower() if scheme else 'http'
        self.port = port if port else ('443' if self.scheme == 'https' else '80')  # TODO: fix for other schemes
        self.path = path if path else '/'
        self.fragment = fragment
        if query:
            self.query = query
            self.params_list = query.split('&').sort()

        return self

    async def from_string(self, url_string):
        parsed = parse_url(url_string)
        return await self.from_named_tuple(parsed)

    async def from_named_tuple(self, parsed):
        return await self.from_options(parsed.host, parsed.scheme, parsed.port, parsed.path, parsed.fragment, parsed.query)

    def __eq__(self, other):
        if self.path == other.path and self.host == other.host and self.port == other.port:
            return True
        return False

    def __hash__(self):
        if not self._hash:
            self._hash = "{}:{}{}?".format(self.host, self.port, self.path, "".join(sorted(list(self.params.keys())))).__hash__()

        return self._hash

    def __str__(self):
        return "{}://{}:{}{}{}".format(self.scheme, self.host, self.port, self.path, self._params_string)
