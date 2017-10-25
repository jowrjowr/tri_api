import flask as _flask

blueprint = _flask.Blueprint("core2", __name__, url_prefix="/core2")

from .moons import moons_get, moons_get_systems, moons_get_consts, moons_get_regions, moons_post, moons_get_conflicts
from .moons import moons_get_missing, moons_post_conflicts_resolve, moons_get_scanners
from .user import user_get
