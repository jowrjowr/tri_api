#!/usr/bin/python3

from flask import Flask, Blueprint, Response
import common.logger as _logger
import os
import uwsgi

app = Flask(__name__)

# initialize logging
logdir = "/srv/api/logs"
filename = "api"
try:
    loglevel = uwsgi.opt['loglevel'].decode('utf-8')
except Exception as e:
    loglevel = 'info'

_logger.LogSetup(loglevel, filename, logdir)

# secret_key is a random seed value for http sessions
app.secret_key = os.urandom(24)

# the transport to nginx is https but nginx<-->uwsgi is not

app.config.update({
    'OAUTH1_PROVIDER_ENFORCE_SSL': False
})
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import tri_api.views
import tri_api.endpoints.core2

app.register_blueprint(tri_api.endpoints.core2.blueprint)
