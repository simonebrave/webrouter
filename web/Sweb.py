import re
from webob import Request, Response, dec, exc

class DictObj:
    def __init__(self, d):
        if isinstance(d, (dict,)):
            self.__dict__['_dict'] = d
        else:
            self.__dict__['_dict'] = {}

    def __getattr__(self, item):
        try:
            return self._dict[item]
        except:
            raise AttributeError('Attribute {} Not Found'.format(item))

    def __setattr__(self, key, value):
        raise NotImplementedError

class Context(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError('Attribute {} not found!'.format(item))

    def __setattr__(self, key, value):
        self[key] = value

class NestedContext(Context):
    def __init__(self, globalcontext:Context = None):
        super().__init__()
        self.relate(globalcontext)

    def __getattr__(self, item):
        for item in self.keys():
            return self[item]
        return self.globalcontext[item]

    def relate(self, globalcontext:Context = None):
        self.globalcontext = globalcontext

class _Router:
    PATTERN = re.compile(r'/({[^{}:]+:?[^{}:]*})')
    TYPEPATTERN = {
        'str' : r'[^/]+',
        'int' : r'[+-]?\d+',
        'word' : r'\w+',
        'float' : r'[+-]?\d+.\d+',
        'any' : r'.+'
    }
    TYPECAST = {
        'str' : str,
        'word' : str,
        'int' : int,
        'float' : float,
        'any' : str
    }

    def _transfrom(self, kvstr:str):
        name, _, type = kvstr.strip('/{}').partition(':')
        return '/(?P<{}>{})'.format(name, self.TYPEPATTERN.get(type, r'\w+')), name, self.TYPECAST.get(type, str)

    def _parse(self, src:str):
        start = 0
        res = ''
        translator = {}
        while True:
            matcher = self.PATTERN.search(src, start)
            if matcher:
                res += matcher.string[start:matcher.start()]
                tmp = self._transfrom(matcher.string[matcher.start():matcher.end()])
                res += tmp[0]
                translator[tmp[1]] = tmp[2]
                start = matcher.end()
            else:
                break

        if res:
            return res, translator
        else:
            return src, translator


    def __init__(self, prefix = ''):
        self.__prefix = prefix.rstrip('/\\')
        self.__routable = []

        self.ctx = NestedContext()
        self.preinterceptor = []
        self.postinterceptor = []

    def register_preinterceptor(self, fn):
        self.preinterceptor.append(fn)
        return fn

    def register_postinterceptor(self, fn):
        self.postinterceptor.append(fn)
        return fn

    @property
    def prefix(self):
        return self.__prefix

    def route(self, src, *methods):
        def wrapper(handler):
            pattern, translator = self._parse(src)
            self.__routable.append((methods, re.compile(pattern), translator, handler))
            return handler
        return wrapper

    def matchpath(self, request:Request):
        if not request.path.startswith(self.__prefix):
            return None

        for fn in self.preinterceptor:
            request = fn(self.ctx, request)
        for methods, pattern, translator, handler in self.__routable:
            if not methods or request.method.upper() in methods:
                matcher = pattern.match(request.path.replace(self.__prefix, '', 1))
                if matcher:
                    #request.agrs = matcher.group()
                    #request.kwargs = DictObj(matcher.groupdict())
                    newdict = {}
                    for k, v in matcher.groupdict().items():
                        newdict[k] = translator[k](v)
                    request.vars = DictObj(newdict)
                    response = handler(self.ctx, request)
                    for fn in self.postinterceptor:
                        response = fn(self.ctx, request, response)
                    return


    def get(cls, pattern):
        return cls.route(pattern, 'GET')

    def post(cls, pattern):
        return cls.route(pattern, 'POST')

    def head(cls, pattern):
        return cls.route(pattern, 'HEAD')

class EmulateWeb:
    Router = _Router
    Request = Request
    Response = Response
    Context = Context
    NestedContext = NestedContext

    CTX = Context()
    PREINTERCEPTOR = []
    POSTINTERCEPTOR = []

    ROUTER = []
    GET = 'GET'
    POST = 'POST'

    @classmethod
    def register(cls, router:Router):
        cls.ROUTER.append(router)

    @classmethod
    def register_preinterceptor(cls, fn):
        cls.PREINTERCEPTOR.append(fn)
        return fn

    @classmethod
    def register_postinterceptor(cls, fn):
        cls.POSTINTERCEPTOR.append(fn)
        return fn

    @classmethod
    def extern(cls, name, ext):
        cls.CTX[name] = ext

    @dec.wsgify
    def __call__(self, request):
        for fn in self.PREINTERCEPTOR:
            request = fn(self.CTX, request)

        for router in self.ROUTER:
            response = router.matchpath(request)

            for fn in self.POSTINTERCEPTOR:
                response = fn(self.CTX, request, response)
            if response:
                return response
        raise exc.HTTPNotFound('Page not found!')

