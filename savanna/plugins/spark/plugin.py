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

from savanna import conductor
from savanna import context
from savanna.openstack.common import log as logging
from savanna.plugins.general import exceptions as ex
from savanna.plugins.general import utils
from savanna.plugins import provisioning as p
from savanna.plugins.spark import config_helper as c_helper
from savanna.plugins.spark import run_scripts as run
from savanna.plugins.spark import scaling as sc
from savanna.topology import topology_helper as th
from savanna.utils import files as f
from savanna.utils import remote


conductor = conductor.API
LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class SparkProvider(p.ProvisioningPluginBase):
    def __init__(self):
        self.processes = {
            "HDFS": ["namenode", "datanode", "secondarynamenode"],
            "SPARK": ["master", "slave"]
        }

    def get_title(self):
        return "Spark Apache Hadoop"

    def get_description(self):
        return (
            "This plugin provides an ability to launch Spark 0.8.0 on Hadoop "
            "2.0.0-cdh4.5.0 cluster without any management consoles.")

    def get_versions(self):
        return ['2.0.0_cdh4.5.0']

    def get_configs(self, hadoop_version):
        return c_helper.get_plugin_configs()

    def get_hdfs_user(self):
        return 'hadoop'

    def get_node_processes(self, hadoop_version):
        return self.processes

    def validate(self, cluster):
        nn_count = sum([ng.count for ng
                        in utils.get_node_groups(cluster, "namenode")])
        if nn_count != 1:
            raise ex.NotSingleNameNodeException(nn_count)

        # validate Spark Master Node and Spark Slaves
        sm_count = sum([ng.count for ng
                        in utils.get_node_groups(cluster, "master")])

        if sm_count != 1:
            raise ex.NotSingleMasterNodeException(sm_count)

        sl_count = sum([ng.count for ng
                        in utils.get_node_groups(cluster, "slave")])

        if sl_count < 1:
            raise ex.NotSlaveNodeException(sl_count)
        # --------------------------------------------------

    def update_infra(self, cluster):
        pass

    def configure_cluster(self, cluster):
        instances = utils.get_instances(cluster)

        self._setup_instances(cluster, instances)

    def start_cluster(self, cluster):
        instances = utils.get_instances(cluster)
        nn_instance = utils.get_namenode(cluster)
        sm_instance = utils.get_masternode(cluster)
        with remote.get_remote(nn_instance) as r:
            #run.clean_port_hadoop(r)
            run.format_namenode(r)
            run.start_processes(r, "namenode")

        for snn in utils.get_secondarynamenodes(cluster):
            run.start_processes(remote.get_remote(snn), "secondarynamenode")

        #actually, just start datanode
        self._start_slave_datanode_processes(instances)

        LOG.info("Hadoop services in cluster %s have been started" %
                 cluster.name)

        # start spark master node
        if sm_instance:
            with remote.get_remote(sm_instance) as r:
                #run.stop_spark(r)
                run.start_spark_master(r)
                LOG.info("Spark service at '%s' has been started",
                         sm_instance.hostname())

        LOG.info('Cluster %s has been started successfully' % cluster.name)
        self._set_cluster_info(cluster)

    def _extract_configs_to_extra(self, cluster):
        nn = utils.get_namenode(cluster)
        sp_master = utils.get_masternode(cluster)
        sp_slaves = utils.get_slavenodes(cluster)

        extra = dict()

        # Generate and add Spark config
        master_port = cluster.cluster_configs.SPARK.SPARK_MASTER_PORT
        master_web_port = cluster.cluster_configs.SPARK.SPARK_MASTER_WEBUI_PORT
        worker_cores = cluster.cluster_configs.SPARK.SPARK_WORKER_CORES
        worker_memory = cluster.cluster_configs.SPARK.SPARK_WORKER_MEMORY
        worker_port = cluster.cluster_configs.SPARK.SPARK_WORKER_PORT
        worker_web_port = cluster.cluster_configs.SPARK.SPARK_WORKER_WEBUI_PORT
        worker_instances = cluster.cluster_configs.SPARK.SPARK_WORKER_INSTANCES

        config_master = config_slaves = ''
        if sp_master is not None:
            config_master = c_helper.generate_spark_env_configs(
                sp_master.hostname(), master_port,
                master_web_port, worker_cores,
                worker_memory, worker_port,
                worker_web_port, worker_instances)

        if sp_slaves is not None:
            slavenames = []
            for slave in sp_slaves:
                slavenames.append(slave.hostname())
            config_slaves = c_helper.generate_spark_slaves_configs(slavenames)
        else:
            config_slaves = "\n"

        for ng in cluster.node_groups:
            extra[ng.id] = {
                'xml': c_helper.generate_xml_configs(
                    ng.configuration(),
                    ng.storage_paths(),
                    nn.hostname(), None,
                ),
                'setup_script': c_helper.generate_setup_script(
                    ng.storage_paths(),
                    c_helper.extract_environment_confs(ng.configuration())
                ),
                'sp_master': config_master,
                'sp_slaves': config_slaves
            }

        if c_helper.is_data_locality_enabled(cluster):
            topology_data = th.generate_topology_map(
                cluster, CONF.enable_hypervisor_awareness)
            extra['topology_data'] = "\n".join(
                [k + " " + v for k, v in topology_data.items()]) + "\n"

        return extra

    def decommission_nodes(self, cluster, instances):
        sls = utils.get_slavenodes(cluster)
        dns = utils.get_datanodes(cluster)
        decommission_dns = False
        decommission_sls = False

        for i in instances:
            if 'datanode' in i.node_group.node_processes:
                dns.remove(i)
                decommission_dns = True
            if 'slave' in i.node_group.node_processes:
                sls.remove(i)
                decommission_sls = True

        nn = utils.get_namenode(cluster)
        spark_master = utils.get_masternode(cluster)

        if decommission_sls:
            sc.decommission_sl(spark_master, instances, sls)
        if decommission_dns:
            sc.decommission_dn(nn, instances, dns)

    def validate_scaling(self, cluster, existing, additional):
        self._validate_existing_ng_scaling(cluster, existing)
        self._validate_additional_ng_scaling(cluster, additional)

    def scale_cluster(self, cluster, instances):
        self._setup_instances(cluster, instances)

        run.refresh_nodes(remote.get_remote(
            utils.get_namenode(cluster)), "dfsadmin")

        self._start_slave_datanode_processes(instances)

    def _start_slave_datanode_processes(self, instances):
            #sl_dn_names = ["datanode", "slave"]
            sl_dn_names = ["datanode"]

            with context.ThreadGroup() as tg:
                for i in instances:
                    processes = set(i.node_group.node_processes)
                    sl_dn_procs = processes.intersection(sl_dn_names)

                    if sl_dn_procs:
                        tg.spawn('spark-start-sl-dn-%s' % i.instance_name,
                                 self._start_slave_datanode, i,
                                 list(sl_dn_procs))

    def _start_slave_datanode(self, instance, sl_dn_procs):
            with instance.remote() as r:
                run.start_processes(r, *sl_dn_procs)

    def _setup_instances(self, cluster, instances):
        extra = self._extract_configs_to_extra(cluster)
        self._push_configs_to_nodes(cluster, extra, instances)

    def _push_configs_to_nodes(self, cluster, extra, new_instances):
        all_instances = utils.get_instances(cluster)
        with context.ThreadGroup() as tg:
            for instance in all_instances:
                if instance in new_instances:
                    tg.spawn('spark-configure-%s' % instance.instance_name,
                             self._push_configs_to_new_node, cluster,
                             extra, instance)
                else:
                    tg.spawn('spark-reconfigure-%s' % instance.instance_name,
                             self._push_configs_to_existing_node, cluster,
                             extra, instance)

    def _push_configs_to_new_node(self, cluster, extra, instance):
        ng_extra = extra[instance.node_group.id]

        files_hadoop = {
            '/etc/hadoop/conf/core-site.xml': ng_extra['xml']['core-site'],
            '/etc/hadoop/conf/hdfs-site.xml': ng_extra['xml']['hdfs-site'],
        }

        files_spark = {
            '/opt/spark/conf/spark-env.sh': ng_extra['sp_master'],
            '/opt/spark/conf/slaves': ng_extra['sp_slaves']
        }

        files_init = {
            '/tmp/savanna-hadoop-init.sh': ng_extra['setup_script'],
            'id_rsa': cluster.management_private_key,
            'authorized_keys': cluster.management_public_key
        }

        # pietro: This is required because the (secret) key is not stored in
        # .ssh which hinders password-less ssh required by spark scripts
        key_cmd = 'sudo cp /home/ubuntu/id_rsa /home/ubuntu/.ssh/; '\
            'sudo chown ubuntu:ubuntu /home/ubuntu/.ssh/id_rsa; '\
            'sudo chmod 600 /home/ubuntu/.ssh/id_rsa'

        for ng in cluster.node_groups:
            dn_path = c_helper.extract_hadoop_path(ng.storage_paths(),
                                                   '/dfs/dn')
            nn_path = c_helper.extract_hadoop_path(ng.storage_paths(),
                                                   '/dfs/nn')
            hdfs_dir_cmd = 'sudo mkdir -p %s %s;'\
                'sudo chown -R hdfs:hdfs %s %s;'\
                'sudo chmod go-rx %s %s;'\
                % (nn_path, dn_path,
                   nn_path, dn_path,
                   nn_path, dn_path)

        with remote.get_remote(instance) as r:
            # TODO(aignatov): sudo chown is wrong solution. But it works.
            r.execute_command(
                'sudo chown -R $USER:$USER /etc/hadoop'
            )
            r.write_files_to(files)
            r.execute_command(
                'sudo chmod 0500 /tmp/savanna-hadoop-init.sh'
            )
            r.execute_command(
                'sudo /tmp/savanna-hadoop-init.sh '
                '>> /tmp/savanna-hadoop-init.log 2>&1')

            r.execute_command(hdfs_dir_cmd)
            # pietro: executing the key_cmd commands
            r.execute_command(key_cmd)
            
            if c_helper.is_data_locality_enabled(cluster):
                r.write_file_to(
                    '/etc/hadoop/topology.sh',
                    f.get_file_text(
                        'plugins/spark/resources/topology.sh'))
                r.execute_command(
                    'sudo chmod +x /etc/hadoop/topology.sh'
                )

            self._write_topology_data(r, cluster, extra)
            self._push_master_configs(r, cluster, extra, instance)

    def _push_configs_to_existing_node(self, cluster, extra, instance):
        node_processes = instance.node_group.node_processes
        need_update_hadoop = (c_helper.is_data_locality_enabled(cluster) or
                              'namenode' in node_processes or
                              'master' in node_processes or
                              'slave' in node_processes)
        need_update_spark = ('master' in node_processes or
                             'slave' in node_processes)

        if need_update_spark:
            ng_extra = extra[instance.node_group.id]
            files = {
                '/opt/spark/conf/spark-env.sh': ng_extra['sp_master'],
                '/opt/spark/conf/slaves': ng_extra['sp_slaves'],
            }
            r = remote.get_remote(instance)
            r.write_files_to(files)
        if need_update_hadoop:
            with remote.get_remote(instance) as r:
                self._write_topology_data(r, cluster, extra)
                self._push_master_configs(r, cluster, extra, instance)

    def _write_topology_data(self, r, cluster, extra):
        if c_helper.is_data_locality_enabled(cluster):
            topology_data = extra['topology_data']
            r.write_file_to('/etc/hadoop/topology.data', topology_data)

    def _push_master_configs(self, r, cluster, extra, instance):
#        ng_extra = extra[instance.node_group.id]
        node_processes = instance.node_group.node_processes

        if 'namenode' in node_processes:
            self._push_namenode_configs(cluster, r)
        #need to do anything with spark here?

    def _push_namenode_configs(self, cluster, r):
        r.write_file_to('/etc/hadoop/dn.incl',
                        utils.generate_fqdn_host_names(
                            utils.get_datanodes(cluster)))

    def _set_cluster_info(self, cluster):
        nn = utils.get_namenode(cluster)
        sp_master = utils.get_masternode(cluster)
        info = {}

        if nn:
            address = c_helper.get_config_value(
                'HDFS', 'dfs.http.address', cluster)
            port = address[address.rfind(':') + 1:]
            info['HDFS'] = {
                'Web UI': 'http://%s:%s' % (nn.management_ip, port)
            }
            info['HDFS']['NameNode'] = 'hdfs://%s:8020' % nn.hostname()

        if sp_master:
            port = c_helper.get_config_value(
                'SPARK', 'SPARK_MASTER_WEBUI_PORT', cluster)
            #port = address[address.rfind(':') + 1:]
            if (port is not None):
                info['SPARK'] = {
                    'Web UI': 'http://%s:%s' % (sp_master.management_ip, port)
                }
        ctx = context.ctx()
        conductor.cluster_update(ctx, cluster, {'info': info})

    def _get_scalable_processes(self):
        return ["datanode", "slave"]

    def _get_by_id(self, lst, id):
        for obj in lst:
            if obj.id == id:
                return obj
        return None

    def _validate_additional_ng_scaling(self, cluster, additional):
        master = utils.get_masternode(cluster)
        scalable_processes = self._get_scalable_processes()

        for ng_id in additional:
            ng = self._get_by_id(cluster.node_groups, ng_id)
            if not set(ng.node_processes).issubset(scalable_processes):
                raise ex.NodeGroupCannotBeScaled(
                    ng.name, "Spark plugin cannot scale nodegroup"
                             " with processes: " +
                             ' '.join(ng.node_processes))
            if not master and 'slave' in ng.node_processes:
                raise ex.NodeGroupCannotBeScaled(
                    ng.name, "Spark plugin cannot scale node group with "
                             "processes which have no master-processes run "
                             "in cluster")

    def _validate_existing_ng_scaling(self, cluster, existing):
        scalable_processes = self._get_scalable_processes()
        dn_to_delete = 0
        for ng in cluster.node_groups:
            if ng.id in existing:
                if ng.count > existing[ng.id] and "datanode" in \
                        ng.node_processes:
                    dn_to_delete += ng.count - existing[ng.id]
                if not set(ng.node_processes).issubset(scalable_processes):
                    raise ex.NodeGroupCannotBeScaled(
                        ng.name, "Spark plugin cannot scale nodegroup"
                                 " with processes: " +
                                 ' '.join(ng.node_processes))

        dn_amount = len(utils.get_datanodes(cluster))
        rep_factor = c_helper.determine_cluster_config(cluster, 'HDFS',
                                                       "dfs.replication")

        if dn_to_delete > 0 and dn_amount - dn_to_delete < rep_factor:
            raise ex.ClusterCannotBeScaled(
                cluster.name, "Spark plugin cannot shrink cluster because "
                              "it would be not enough nodes for replicas "
                              "(replication factor is %s)" % rep_factor)
