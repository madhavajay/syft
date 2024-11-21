from utils import CBORModel


class User(CBORModel):
    id: int
    name: str


TypeRegistry = {"User": User}
