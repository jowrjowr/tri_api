import flask as _flask

blueprint = _flask.Blueprint("core2", __name__, url_prefix="/core2")

from .moons import moons_get, moons_post
from .user import user_endpoint
