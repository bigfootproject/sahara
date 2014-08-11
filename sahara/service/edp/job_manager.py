# Copyright (c) 2013 Mirantis Inc.
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

import datetime

from oslo.config import cfg

from sahara import conductor as c
from sahara import context
from sahara import exceptions as e
from sahara.i18n import _
from sahara.i18n import _LE
from sahara.openstack.common import log
from sahara.service.edp import job_utils
from sahara.service.edp.oozie import engine as oozie_engine
from sahara.service.edp.spark import engine as spark_engine
from sahara.utils import edp


LOG = log.getLogger(__name__)

CONF = cfg.CONF

conductor = c.API


def _make_engine(name, job_types, engine_class):
    return {"name": name,
            "job_types": job_types,
            "engine": engine_class}

default_engines = [_make_engine("oozie",
                                [edp.JOB_TYPE_HIVE,
                                 edp.JOB_TYPE_JAVA,
                                 edp.JOB_TYPE_MAPREDUCE,
                                 edp.JOB_TYPE_MAPREDUCE_STREAMING,
                                 edp.JOB_TYPE_PIG],
                                oozie_engine.OozieJobEngine),
                   _make_engine("spark",
                                [edp.JOB_TYPE_JAVA,
                                 edp.JOB_TYPE_SPARK],
                                spark_engine.SparkJobEngine)
                   ]


def _get_job_type(job_execution):
    return conductor.job_get(context.ctx(), job_execution.job_id).type


def _get_job_engine(cluster, job_execution):
    return job_utils.get_plugin(cluster).get_edp_engine(cluster,
                                                        _get_job_type(
                                                            job_execution),
                                                        default_engines)


def _write_job_status(job_execution, job_info):
    update = {"info": job_info}
    if job_info['status'] in edp.JOB_STATUSES_TERMINATED:
        update['end_time'] = datetime.datetime.now()
    return conductor.job_execution_update(context.ctx(),
                                          job_execution,
                                          update)


def _update_job_status(engine, job_execution):
    job_info = engine.get_job_status(job_execution)
    if job_info is not None:
        job_execution = _write_job_status(job_execution, job_info)
    return job_execution


def _update_job_execution_extra(cluster, job_execution):
    if CONF.use_namespaces and not CONF.use_floating_ips:
        info = cluster.node_groups[0].instances[0].remote().get_neutron_info()
        extra = job_execution.extra.copy()
        extra['neutron'] = info

        job_execution = conductor.job_execution_update(
            context.ctx(), job_execution.id, {'extra': extra})
    return job_execution


def _run_job(job_execution_id):
    ctx = context.ctx()
    job_execution = conductor.job_execution_get(ctx, job_execution_id)
    cluster = conductor.cluster_get(ctx, job_execution.cluster_id)
    if cluster.status != 'Active':
        return

    eng = _get_job_engine(cluster, job_execution)
    if eng is None:
        raise e.EDPError(_("Cluster does not support job type %s")
                         % _get_job_type(job_execution))
    job_execution = _update_job_execution_extra(cluster, job_execution)

    # Job id is a string
    # Status is a string
    # Extra is a dictionary to add to extra in the job_execution
    jid, status, extra = eng.run_job(job_execution)

    # Set the job id and the start time
    # Optionally, update the status and the 'extra' field
    update_dict = {'oozie_job_id': jid,
                   'start_time': datetime.datetime.now()}
    if status:
        update_dict['info'] = {'status': status}
    if extra:
        curr_extra = job_execution.extra.copy()
        curr_extra.update(extra)
        update_dict['extra'] = curr_extra

    job_execution = conductor.job_execution_update(
        ctx, job_execution, update_dict)


def run_job(job_execution_id):
    try:
        _run_job(job_execution_id)
    except Exception as ex:
        LOG.exception(
            _LE("Can't run job execution '%(job)s' (reason: %(reason)s)"),
            {'job': job_execution_id, 'reason': ex})

        conductor.job_execution_update(
            context.ctx(), job_execution_id,
            {'info': {'status': edp.JOB_STATUS_FAILED},
             'start_time': datetime.datetime.now(),
             'end_time': datetime.datetime.now()})


def cancel_job(job_execution_id):
    ctx = context.ctx()
    job_execution = conductor.job_execution_get(ctx, job_execution_id)
    cluster = conductor.cluster_get(ctx, job_execution.cluster_id)
    if cluster is not None:
        engine = _get_job_engine(cluster, job_execution)
        if engine is not None:
            try:
                job_info = engine.cancel_job(job_execution)
            except Exception as e:
                job_info = None
                LOG.exception(
                    _LE("Error during cancel of job execution %(job)s: "
                        "%(error)s"), {'job': job_execution.id, 'error': e})
            if job_info is not None:
                job_execution = _write_job_status(job_execution, job_info)
    return job_execution


def get_job_status(job_execution_id):
    ctx = context.ctx()
    job_execution = conductor.job_execution_get(ctx, job_execution_id)
    cluster = conductor.cluster_get(ctx, job_execution.cluster_id)
    if cluster is not None and cluster.status == 'Active':
        engine = _get_job_engine(cluster, job_execution)
        if engine is not None:
            job_execution = _update_job_status(engine,
                                               job_execution)
    return job_execution


def update_job_statuses():
    ctx = context.ctx()
    for je in conductor.job_execution_get_all(ctx, end_time=None):
        try:
            get_job_status(je.id)
        except Exception as e:
            LOG.exception(
                _LE("Error during update job execution %(job)s: %(error)s"),
                {'job': je.id, 'error': e})


def get_job_config_hints(job_type):
    # TODO(tmckay) We need plugin-specific config hints
    # (not a new problem). At the moment we don't have a plugin
    # or cluster argument in this call so we can only go by
    # job type.

    # Since we currently have a single engine for each
    # job type (Spark will support Java only temporarily)
    # we can just key off of job type

    for eng in default_engines:
        if job_type in eng["job_types"]:
            return eng["engine"].get_possible_job_config(job_type)
