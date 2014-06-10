# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from keystoneclient.middleware import auth_token
from oslo.config import cfg

from sahara.openstack.common import log

LOG = log.getLogger(__name__)
CONF = cfg.CONF

AUTH_OPT_GROUP_NAME = 'keystone_authtoken'

# Keystone auth uri that could be used in other places in Sahara
AUTH_URI = None


def register_auth_opts(conf):
    """Register keystoneclient auth_token middleware options."""

    conf.register_opts(auth_token.opts, group=AUTH_OPT_GROUP_NAME)
    auth_token.CONF = conf


register_auth_opts(CONF)


def wrap(app, conf):
    """Wrap wsgi application with ACL check."""

    auth_cfg = dict(conf.get(AUTH_OPT_GROUP_NAME))
    auth_protocol = auth_token.AuthProtocol(app, conf=auth_cfg)

    # store auth uri in global var to be able to use it in runtime
    global AUTH_URI
    AUTH_URI = auth_protocol.auth_uri

    return auth_protocol
