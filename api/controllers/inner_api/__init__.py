from flask import Blueprint

from libs.external_api import ExternalApi

bp = Blueprint("inner_api", __name__, url_prefix="/inner/api")
api = ExternalApi(bp)

from .dev import dev_account, dev_init_update, dev_kbs, dev_plugins, dev_workspace
from .plugin import plugin
from .workspace import workspace
