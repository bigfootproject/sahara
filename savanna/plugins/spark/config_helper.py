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

from oslo.config import cfg

from savanna.openstack.common import log as logging
from savanna.plugins import provisioning as p
from savanna.swift import swift_helper as swift
from savanna.topology import topology_helper as topology
from savanna.utils import types as types
from savanna.utils import xmlutils as x


LOG = logging.getLogger(__name__)
CONF = cfg.CONF

CORE_DEFAULT = x.load_hadoop_xml_defaults(
    'plugins/spark/resources/core-default.xml')

HDFS_DEFAULT = x.load_hadoop_xml_defaults(
    'plugins/spark/resources/hdfs-default.xml')

XML_CONFS = {
    "HDFS": [CORE_DEFAULT, HDFS_DEFAULT]
}

SPARK_CONFS = {
    'SPARK': {
             "OPTIONS": ['SPARK_MASTER_PORT',
                    'SPARK_MASTER_WEBUI_PORT', 'SPARK_WORKER_CORES',
                   'SPARK_WORKER_MEMORY', 'SPARK_WORKER_PORT',
                   'SPARK_WORKER_WEBUI_PORT', 'SPARK_WORKER_INSTANCES'
                   ]
             }
}

# TODO(aignatov): Environmental configs could be more complex
ENV_CONFS = {
    "HDFS": {
        'Name Node Heap Size': 'HADOOP_NAMENODE_OPTS=\\"-Xmx%sm\\"',
        'Data Node Heap Size': 'HADOOP_DATANODE_OPTS=\\"-Xmx%sm\\"'
    }
}

ENABLE_SWIFT = p.Config('Enable Swift', 'general', 'cluster',
                        config_type="bool", priority=1,
                        default_value=True, is_optional=True)

ENABLE_DATA_LOCALITY = p.Config('Enable Data Locality', 'general', 'cluster',
                                config_type="bool", priority=1,
                                default_value=True, is_optional=True)

HIDDEN_CONFS = ['fs.defaultFS', 'dfs.namenode.name.dir',
                'dfs.datanode.data.dir', 'mapred.job.tracker',
                'mapred.system.dir', 'mapred.local.dir',
                'hadoop.proxyuser.hadoop.hosts',
                'hadoop.proxyuser.hadoop.groups']

CLUSTER_WIDE_CONFS = ['dfs.block.size', 'dfs.permissions', 'dfs.replication',
                      'dfs.replication.min', 'dfs.replication.max',
                      'io.file.buffer.size', 'mapreduce.job.counters.max',
                      'mapred.output.compress', 'io.compression.codecs',
                      'mapred.output.compression.codec',
                      'mapred.output.compression.type',
                      'mapred.compress.map.output',
                      'mapred.map.output.compression.codec']

PRIORITY_1_CONFS = ['dfs.datanode.du.reserved',
                    'dfs.datanode.failed.volumes.tolerated',
                    'dfs.datanode.max.xcievers', 'dfs.datanode.handler.count',
                    'dfs.namenode.handler.count', 'mapred.child.java.opts',
                    'mapred.jobtracker.maxtasks.per.job',
                    'mapred.job.tracker.handler.count',
                    'mapred.map.child.java.opts',
                    'mapred.reduce.child.java.opts',
                    'io.sort.mb', 'mapred.tasktracker.map.tasks.maximum',
                    'mapred.tasktracker.reduce.tasks.maximum']

# for now we have not so many cluster-wide configs
# lets consider all of them having high priority
PRIORITY_1_CONFS += CLUSTER_WIDE_CONFS


def _initialise_configs():
    configs = []
    for service, config_lists in XML_CONFS.iteritems():
        for config_list in config_lists:
            for config in config_list:
                if config['name'] not in HIDDEN_CONFS:
                    cfg = p.Config(config['name'], service, "node",
                                   is_optional=True, config_type="string",
                                   default_value=str(config['value']),
                                   description=config['description'])
                    if cfg.default_value in ["true", "false"]:
                        cfg.config_type = "bool"
                        cfg.default_value = (cfg.default_value == 'true')
                    elif types.is_int(cfg.default_value):
                        cfg.config_type = "int"
                        cfg.default_value = int(cfg.default_value)
                    if config['name'] in CLUSTER_WIDE_CONFS:
                        cfg.scope = 'cluster'
                    if config['name'] in PRIORITY_1_CONFS:
                        cfg.priority = 1
                    configs.append(cfg)

    for service, config_items in ENV_CONFS.iteritems():
        for name, param_format_str in config_items.iteritems():
            configs.append(p.Config(name, service, "node",
                                    default_value=1024, priority=1,
                                    config_type="int"))

    for service, config_items in SPARK_CONFS.iteritems():
        for name in config_items['OPTIONS']:
            cfg = p.Config(name, service, "cluster",
                        is_optional=True, priority=2)
            configs.append(cfg)

    configs.append(ENABLE_SWIFT)
    if CONF.enable_data_locality:
        configs.append(ENABLE_DATA_LOCALITY)

    return configs

# Initialise plugin Hadoop configurations
PLUGIN_CONFIGS = _initialise_configs()


def get_plugin_configs():
    return PLUGIN_CONFIGS


def get_general_configs(hive_hostname, passwd_hive_mysql):
    config = {
        ENABLE_SWIFT.name: {
            'default_value': ENABLE_SWIFT.default_value,
            'conf': extract_name_values(swift.get_swift_configs())
        }
    }
    if CONF.enable_data_locality:
        config.update({
            ENABLE_DATA_LOCALITY.name: {
                'default_value': ENABLE_DATA_LOCALITY.default_value,
                'conf': extract_name_values(topology.vm_awareness_all_config())
            }
        })
    return config


def get_config_value(service, name, cluster=None):
    if cluster:
        for ng in cluster.node_groups:
            if (ng.configuration.get(service) and
                    ng.configuration[service].get(name)):
                return ng.configuration[service][name]

    for c in PLUGIN_CONFIGS:
        if c.applicable_target == service and c.name == name:
            return c.default_value

    raise RuntimeError("Unable get parameter '%s' from service %s",
                       name, service)


def generate_cfg_from_general(cfg, configs, general_config,
                              rest_excluded=False):
    if 'general' in configs:
        for nm in general_config:
            if nm not in configs['general'] and not rest_excluded:
                configs['general'][nm] = general_config[nm]['default_value']
        for name, value in configs['general'].items():
            if value:
                cfg = _set_config(cfg, general_config, name)
                LOG.info("Applying config: %s" % name)
    else:
        cfg = _set_config(cfg, general_config)
    return cfg


def generate_xml_configs(configs, storage_path, nn_hostname, hadoop_port
                         ):
    # inserting common configs depends on provisioned VMs and HDFS placement
    # TODO(aignatov): should be moved to cluster context
    """
    dfs.name.dir': extract_hadoop_path(storage_path,
                                            '/lib/hadoop/hdfs/namenode'),
    'dfs.data.dir': extract_hadoop_path(storage_path,
                                            '/lib/hadoop/hdfs/datanode'),
    'dfs.name.dir': storage_path + 'hdfs/name',
    'dfs.data.dir': storage_path + 'hdfs/data',

    'dfs.hosts': '/etc/hadoop/dn.incl',
    'dfs.hosts.exclude': '/etc/hadoop/dn.excl',
    """
    if hadoop_port == None:
        hadoop_port = 8020

    cfg = {
        'fs.defaultFS': 'hdfs://%s:%s' % (nn_hostname, str(hadoop_port)),
        'dfs.namenode.name.dir': extract_hadoop_path(storage_path,
                                            '/dfs/nn'),
        'dfs.datanode.data.dir': extract_hadoop_path(storage_path,
                                            '/dfs/dn'),
        'dfs.replication': 1,
    }

    # inserting user-defined configs
    for key, value in extract_xml_confs(configs):
        cfg[key] = value

    # invoking applied configs to appropriate xml files
    core_all = CORE_DEFAULT

    if CONF.enable_data_locality:
        cfg.update(topology.TOPOLOGY_CONFIG)
        # applying vm awareness configs
        core_all += topology.vm_awareness_core_config()

    xml_configs = {
        'core-site': x.create_hadoop_xml(cfg, core_all),
        'hdfs-site': x.create_hadoop_xml(cfg, HDFS_DEFAULT)
    }

    return xml_configs


def write_hadoop_configs_xml_file(xml_configs):
    f_core = open('core-site.xml', 'w')
    f_hdfs = open('hdfs-site.xml', 'w')

    f_core.writelines(xml_configs['core-site'])
    f_hdfs.writelines(xml_configs['hdfs-site'])

    f_hdfs.flush()
    f_core.flush()
    f_hdfs.close()
    f_core.close()

    return True


def generate_spark_env_configs(mastername, masterport, masterwebport=None,
                               workercores=None, workermemory=None,
                               workerport=None, workerwebport=None,
                               workerinstances=None):
    # Load configs template file
    #f = open('savanna/plugins/spark/resources/spark-env.sh.template', 'r')
    #default_config = f.read()
    # Write new configs
    #configs = [default_config]
    configs = []
    configs.append('SPARK_MASTER_IP=' + mastername)
    configs.append('SPARK_MASTER_PORT=' + str(masterport))
    if masterwebport != None:
        configs.append('SPARK_MASTER_WEBUI_PORT=' + str(masterwebport))
    # configure for workers
    if workercores != None:
        configs.append('SPARK_WORKER_CORES=' + str(workercores))
    if workermemory != None:
        configs.append('SPARK_WORKER_MEMORY=' + str(workermemory))
    if workerport != None:
        configs.append('SPARK_WORKER_PORT=' + str(workerport))
    if workerwebport != None:
        configs.append('SPARK_WORKER_WEBUI_PORT=' + str(workerwebport))
    if workerinstances != None:
        configs.append('SPARK_WORKER_INSTANCES=' + str(workerinstances))
    return '\n'.join(configs)


    #workernames need to be a list of woker names
def generate_spark_slaves_configs(workernames):
    #slaves = [str(worker) for worker in workernames]
    return '\n'.join(workernames)


def write_spark_configs(configs, filename):
    f = open(str(filename), 'w')
    f.write(configs)
    f.flush()
    f.close()
    return


def extract_environment_confs(configs):
    """Returns list of Hadoop parameters which should be passed via environment
    """
    lst = []
    for service, srv_confs in configs.items():
        if ENV_CONFS.get(service):
            for param_name, param_value in srv_confs.items():
                for cfg_name, cfg_format_str in ENV_CONFS[service].items():
                    if param_name == cfg_name and param_value is not None:
                        lst.append(cfg_format_str % param_value)
        else:
            LOG.warn("Plugin recieved wrong applicable target '%s' in "
                     "environmental configs" % service)
    return lst


def extract_xml_confs(configs):
    """Returns list of Hadoop parameters which should be passed into general
    configs like core-site.xml
    """
    lst = []
    for service, srv_confs in configs.items():
        if XML_CONFS.get(service):
            for param_name, param_value in srv_confs.items():
                for cfg_list in XML_CONFS[service]:
                    names = [cfg['name'] for cfg in cfg_list]
                    if param_name in names and param_value is not None:
                        lst.append((param_name, param_value))
        else:
            LOG.warn("Plugin recieved wrong applicable target '%s' for "
                     "xml configs" % service)
    return lst


def generate_setup_script(storage_paths, env_configs):
    script_lines = ["#!/bin/bash -x"]
    script_lines.append("echo -n > /tmp/hadoop-env.sh")
    for line in env_configs:
        if 'HADOOP' in line:
            script_lines.append('echo "%s" >> /tmp/hadoop-env.sh' % line)
    script_lines.append("cat /etc/hadoop/hadoop-env.sh >> /tmp/hadoop-env.sh")
    script_lines.append("cp /tmp/hadoop-env.sh /etc/hadoop/hadoop-env.sh")

    hadoop_log = storage_paths[0] + "/log/hadoop/\$USER/"
    script_lines.append('sed -i "s,export HADOOP_LOG_DIR=.*,'
                        'export HADOOP_LOG_DIR=%s," /etc/hadoop/hadoop-env.sh'
                        % hadoop_log)

    hadoop_log = storage_paths[0] + "/log/hadoop/hdfs"
    script_lines.append('sed -i "s,export HADOOP_SECURE_DN_LOG_DIR=.*,'
                        'export HADOOP_SECURE_DN_LOG_DIR=%s," '
                        '/etc/hadoop/hadoop-env.sh' % hadoop_log)

    for path in storage_paths:
        script_lines.append("chown -R hdfs:hdfs %s" % path)
        script_lines.append("chmod -R 700 %s" % path)
    return "\n".join(script_lines)


def extract_name_values(configs):
    return dict((cfg['name'], cfg['value']) for cfg in configs)


def extract_hadoop_path(lst, hadoop_dir):
    return ",".join([p + hadoop_dir for p in lst])


def determine_cluster_config(cluster, service, config_name):
    if service in cluster.cluster_configs:
        service_configs = cluster.cluster_configs.get(service)
        if config_name in service_configs:
            return service_configs.get(config_name)
    all_conf = get_plugin_configs()
    for conf in all_conf:
        if conf.name == config_name:
            return conf.default_value


def _set_config(cfg, gen_cfg, name=None):
    if name in gen_cfg:
        cfg.update(gen_cfg[name]['conf'])
    if name is None:
        for name in gen_cfg:
            cfg.update(gen_cfg[name]['conf'])
    return cfg


def _is_general_option_enabled(cluster, option):
    for ng in cluster.node_groups:
        conf = ng.configuration
        if 'general' in conf and option.name in conf['general']:
                return conf['general'][option.name]
    return option.default_value


def is_data_locality_enabled(cluster):
    if not CONF.enable_data_locality:
        return False
    return _is_general_option_enabled(cluster, ENABLE_DATA_LOCALITY)
