import flask as _flask

blueprint = _flask.Blueprint("core2", __name__, url_prefix="/core2")

from .user import user_endpoint