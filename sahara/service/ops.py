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

import uuid

from oslo.config import cfg
from oslo import messaging

from sahara import conductor as c
from sahara import context
from sahara.openstack.common import log as logging
from sahara.plugins import base as plugin_base
from sahara.service.edp import job_manager
from sahara.service import trusts
from sahara.utils import general as g
from sahara.utils import rpc as rpc_utils


conductor = c.API
CONF = cfg.CONF
LOG = logging.getLogger(__name__)


INFRA = None


def setup_ops(engine):
    global INFRA

    INFRA = engine


class LocalOps(object):
    def provision_cluster(self, cluster_id):
        context.spawn("cluster-creating-%s" % cluster_id,
                      _provision_cluster, cluster_id)

    def provision_scaled_cluster(self, cluster_id, node_group_id_map):
        context.spawn("cluster-scaling-%s" % cluster_id,
                      _provision_scaled_cluster, cluster_id, node_group_id_map)

    def terminate_cluster(self, cluster_id):
        context.spawn("cluster-terminating-%s" % cluster_id,
                      _terminate_cluster, cluster_id)

    def run_edp_job(self, job_execution_id):
        context.spawn("Starting Job Execution %s" % job_execution_id,
                      _run_edp_job, job_execution_id)


class RemoteOps(rpc_utils.RPCClient):
    def __init__(self):
        target = messaging.Target(topic='sahara-ops', version='1.0')
        super(RemoteOps, self).__init__(target)

    def provision_cluster(self, cluster_id):
        self.cast('provision_cluster', cluster_id=cluster_id)

    def provision_scaled_cluster(self, cluster_id, node_group_id_map):
        self.cast('provision_scaled_cluster', cluster_id=cluster_id,
                  node_group_id_map=node_group_id_map)

    def terminate_cluster(self, cluster_id):
        self.cast('terminate_cluster', cluster_id=cluster_id)

    def run_edp_job(self, job_execution_id):
        self.cast('run_edp_job', job_execution_id=job_execution_id)


class OpsServer(rpc_utils.RPCServer):
    def __init__(self):
        target = messaging.Target(topic='sahara-ops', server=uuid.uuid4(),
                                  version='1.0')
        super(OpsServer, self).__init__(target)

    def provision_cluster(self, cluster_id):
        _provision_cluster(cluster_id)

    def provision_scaled_cluster(self, cluster_id, node_group_id_map):
        _provision_scaled_cluster(cluster_id, node_group_id_map)

    def terminate_cluster(self, cluster_id):
        _terminate_cluster(cluster_id)

    def run_edp_job(self, job_execution_id):
        _run_edp_job(job_execution_id)


def _prepare_provisioning(cluster_id):
    ctx = context.ctx()
    cluster = conductor.cluster_get(ctx, cluster_id)
    plugin = plugin_base.PLUGINS.get_plugin(cluster.plugin_name)

    for nodegroup in cluster.node_groups:
        conductor.node_group_update(
            ctx, nodegroup,
            {"image_username": INFRA.get_node_group_image_username(nodegroup)})

    cluster = conductor.cluster_get(ctx, cluster_id)

    return ctx, cluster, plugin


def _provision_cluster(cluster_id):
    ctx, cluster, plugin = _prepare_provisioning(cluster_id)

    if CONF.use_identity_api_v3 and cluster.is_transient:
        trusts.create_trust(cluster)

    # updating cluster infra
    cluster = conductor.cluster_update(ctx, cluster,
                                       {"status": "InfraUpdating"})
    LOG.info(g.format_cluster_status(cluster))
    plugin.update_infra(cluster)

    # creating instances and configuring them
    cluster = conductor.cluster_get(ctx, cluster_id)
    INFRA.create_cluster(cluster)

    # configure cluster
    cluster = conductor.cluster_update(ctx, cluster, {"status": "Configuring"})
    LOG.info(g.format_cluster_status(cluster))
    try:
        plugin.configure_cluster(cluster)
    except Exception as ex:
        LOG.exception("Can't configure cluster '%s' (reason: %s)",
                      cluster.name, ex)
        cluster = conductor.cluster_update(ctx, cluster, {"status": "Error"})
        LOG.info(g.format_cluster_status(cluster))
        return

    # starting prepared and configured cluster
    cluster = conductor.cluster_update(ctx, cluster, {"status": "Starting"})
    LOG.info(g.format_cluster_status(cluster))
    try:
        plugin.start_cluster(cluster)
    except Exception as ex:
        LOG.exception("Can't start services for cluster '%s' (reason: %s)",
                      cluster.name, ex)
        cluster = conductor.cluster_update(ctx, cluster, {"status": "Error"})
        LOG.info(g.format_cluster_status(cluster))
        return

    # cluster is now up and ready
    cluster = conductor.cluster_update(ctx, cluster, {"status": "Active"})
    LOG.info(g.format_cluster_status(cluster))

    # schedule execution pending job for cluster
    for je in conductor.job_execution_get_all(ctx, cluster_id=cluster.id):
        job_manager.run_job(je.id)


def _provision_scaled_cluster(cluster_id, node_group_id_map):
    ctx, cluster, plugin = _prepare_provisioning(cluster_id)

    # Decommissioning surplus nodes with the plugin

    cluster = conductor.cluster_update(ctx, cluster,
                                       {"status": "Decommissioning"})
    LOG.info(g.format_cluster_status(cluster))

    instances_to_delete = []

    for node_group in cluster.node_groups:
        new_count = node_group_id_map[node_group.id]
        if new_count < node_group.count:
            instances_to_delete += node_group.instances[new_count:
                                                        node_group.count]

    if instances_to_delete:
        plugin.decommission_nodes(cluster, instances_to_delete)

    # Scaling infrastructure
    cluster = conductor.cluster_update(ctx, cluster, {"status": "Scaling"})
    LOG.info(g.format_cluster_status(cluster))

    instances = INFRA.scale_cluster(cluster, node_group_id_map)

    # Setting up new nodes with the plugin

    if instances:
        cluster = conductor.cluster_update(ctx, cluster,
                                           {"status": "Configuring"})
        LOG.info(g.format_cluster_status(cluster))
        try:
            instances = g.get_instances(cluster, instances)
            plugin.scale_cluster(cluster, instances)
        except Exception as ex:
            LOG.exception("Can't scale cluster '%s' (reason: %s)",
                          cluster.name, ex)
            cluster = conductor.cluster_update(ctx, cluster,
                                               {"status": "Error"})
            LOG.info(g.format_cluster_status(cluster))
            return

    cluster = conductor.cluster_update(ctx, cluster, {"status": "Active"})
    LOG.info(g.format_cluster_status(cluster))


def _terminate_cluster(cluster_id):
    ctx = context.ctx()
    cluster = conductor.cluster_get(ctx, cluster_id)
    plugin = plugin_base.PLUGINS.get_plugin(cluster.plugin_name)

    plugin.on_terminate_cluster(cluster)

    INFRA.shutdown_cluster(cluster)

    if CONF.use_identity_api_v3:
        trusts.delete_trust(cluster)

    conductor.cluster_destroy(ctx, cluster)


def _run_edp_job(job_execution_id):
    job_manager.run_job(job_execution_id)
