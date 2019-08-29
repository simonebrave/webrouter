import json
from .Sweb import EmulateWeb

def jsonify(**kwargs):
    content = json.dumps(kwargs)
    response = EmulateWeb.Response()
    response.content_type = 'application/json'
    response.body = "{}".format(content).encode()
    return response



