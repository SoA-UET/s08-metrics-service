# NOTE: you can modify this file as appropriate.

from flask import Blueprint
from flask_restx import Api

v1 = Blueprint("v1", __name__, url_prefix="/api/v1/core")

_api = Api(
    v1,
    title='Version 1',
    version='1',
    description='The first stable version.',
)

from .metrics import api as metrics_api

_api.add_namespace(metrics_api)
