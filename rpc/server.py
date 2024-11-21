from utils import CBORModel

from rpc import Response, Server
from syftbox.lib import Client


class LoginResponse(CBORModel):
    username: str
    token: int = 123


client = Client.load()
print("client", client.email)
app = Server(app_name="test", client=client)


@app.get("/public/rpc/test/listen")
def login(request):
    print("r", request)
    r = request.dict()
    print("d", r)
    q = request.obj()
    print("o", q)

    result = LoginResponse(username=q.name, token=q.id)
    print("result", result)
    return Response(content=result, status_code=200)


app.run()
