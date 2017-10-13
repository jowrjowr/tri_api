import flask as _flask

blueprint = _flask.Blueprint("core2", __name__, url_prefix="/core2")

from .moons import moons_get, moons_post, moons_get_scanners, moons_get_coverage
from .user import user_endpoint
