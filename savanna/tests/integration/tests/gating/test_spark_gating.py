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

import nose.plugins.attrib as attrib
import unittest2
import socket
import telnetlib
import time

from savanna.openstack.common import excutils
from savanna.tests.integration.configs import config as cfg
from savanna.tests.integration.tests import cluster_configs
from savanna.tests.integration.tests import edp
from savanna.tests.integration.tests import scaling
from savanna.tests.integration.tests import spark


class SparkGatingTest(cluster_configs.ClusterConfigTest,
                        scaling.ScalingTest, edp.EDPTest, spark.SparkTest):
    SKIP_CLUSTER_CONFIG_TEST = cfg.ITConfig().spark_config.SKIP_CLUSTER_CONFIG_TEST
    SKIP_EDP_TEST = cfg.ITConfig().spark_config.SKIP_EDP_TEST
    SKIP_SCALING_TEST = cfg.ITConfig().spark_config.SKIP_SCALING_TEST

    @attrib.attr(tags='spark')
    @unittest2.skipIf(cfg.ITConfig().spark_config.SKIP_ALL_TESTS_FOR_PLUGIN,
                      'All tests for Spark plugin were skipped')
    def test_spark_plugin_gating(self):

        node_group_template_id_list = []

#-------------------------------CLUSTER CREATION-------------------------------

#---------------------"slave-dn" node group template creation---------------------

        try:

            node_group_template_slave_dn_id = self.create_node_group_template(
                name='slave-dn',
                plugin_config=self.spark_config,
                description='test node group template',
                volumes_per_node=0,
                volume_size=0,
                node_processes=['slave', 'datanode'],
                node_configs={
                    'HDFS': cluster_configs.DN_CONFIG,
                }
            )
            node_group_template_id_list.append(node_group_template_slave_dn_id)

        except Exception as e:

            with excutils.save_and_reraise_exception():

                message = 'Failure while \'slave-dn\' node group ' \
                          'template creation: '
                self.print_error_log(message, e)

#-----------------------"slave" node group template creation----------------------

        try:

            node_group_template_slave_id = self.create_node_group_template(
                name='slave',
                plugin_config=self.spark_config,
                description='test node group template',
                volumes_per_node=0,
                volume_size=0,
                node_processes=['slave'],
                node_configs={
                }
            )
            node_group_template_id_list.append(node_group_template_slave_id)

        except Exception as e:

            with excutils.save_and_reraise_exception():

                self.delete_objects(
                    node_group_template_id_list=node_group_template_id_list
                )

                message = 'Failure while \'master\' node group template creation: '
                self.print_error_log(message, e)

#----------------------"dn" node group template creation-----------------------

        try:

            node_group_template_dn_id = self.create_node_group_template(
                name='dn',
                plugin_config=self.spark_config,
                description='test node group template',
                volumes_per_node=0,
                volume_size=0,
                node_processes=['datanode'],
                node_configs={
                    'HDFS': cluster_configs.DN_CONFIG
                }
            )
            node_group_template_id_list.append(node_group_template_dn_id)

        except Exception as e:

            with excutils.save_and_reraise_exception():

                self.delete_objects(
                    node_group_template_id_list=node_group_template_id_list
                )

                message = 'Failure while \'dn\' node group template creation: '
                self.print_error_log(message, e)

#---------------------------Cluster template creation--------------------------

        try:

            cluster_template_id = self.create_cluster_template(
                name='test-cluster-template',
                plugin_config=self.spark_config,
                description='test cluster template',
                cluster_configs={
                    'HDFS': cluster_configs.CLUSTER_HDFS_CONFIG,
                    'general': {'Enable Swift': False},
                    'SPARK': cluster_configs.CLUSTER_SPARK_CONFIG,
                },
                node_groups=[
                    dict(
                        name='master-nn',
                        flavor_id=self.flavor_id,
                        node_processes=['namenode', 'master'],
                        node_configs={
                            'HDFS': cluster_configs.NN_CONFIG,
                            #'MapReduce': cluster_configs.JT_CONFIG
                        },
                        count=1),
                    #dict(
                    #    name='sec-nn',
                    #    flavor_id=self.flavor_id,
                    #    node_processes=['secondarynamenode'],
                    #    node_configs={
                    #    },
                    #    count=1),
                    dict(
                        name='worker-node-slave-dn',
                        node_group_template_id=node_group_template_slave_dn_id,
                        count=1),
                    dict(
                        name='worker-node-dn',
                        node_group_template_id=node_group_template_dn_id,
                        count=1),
                    dict(
                        name='worker-node-slave',
                        node_group_template_id=node_group_template_slave_id,
                        count=1)
                ]
            )

        except Exception as e:

            with excutils.save_and_reraise_exception():

                self.delete_objects(
                    node_group_template_id_list=node_group_template_id_list
                )

                message = 'Failure while cluster template creation: '
                self.print_error_log(message, e)

#-------------------------------Cluster creation-------------------------------
        print '================= Cluster creation test ==============='
        try:

            cluster_info = self.create_cluster_and_get_info(
                plugin_config=self.spark_config,
                cluster_template_id=cluster_template_id,
                description='test cluster',
                cluster_configs={}
            )

        except Exception as e:

            with excutils.save_and_reraise_exception():

                self.delete_objects(
                    self.cluster_id, cluster_template_id,
                    node_group_template_id_list
                )

                message = 'Failure while cluster creation: '
                self.print_error_log(message, e)

#----------------------------CLUSTER CONFIG TESTING----------------------------
        try:
            self._cluster_config_testing(cluster_info)
        except Exception as e:

            with excutils.save_and_reraise_exception():

                self.delete_objects(
                    cluster_info['cluster_id'], cluster_template_id,
                    node_group_template_id_list
                )

                message = 'Failure while cluster config testing: '
                self.print_error_log(message, e)

#----------------------------SPARK JOBS TESTING----------------------------
        try:
            self._spark_testing(cluster_info)
        except Exception as e:

            with excutils.save_and_reraise_exception():

                self.delete_objects(
                    cluster_info['cluster_id'], cluster_template_id,
                    node_group_template_id_list
                )

                message = 'Failure while testing: '
                self.print_error_log(message, e)
#----------------------------DELETE CREATED OBJECTS----------------------------

        self.delete_objects(
            cluster_info['cluster_id'], cluster_template_id,
            node_group_template_id_list
        )

    def get_node_info(self, node_ip_list_with_node_processes, plugin_config):

        slave_count = 0
        datanode_count = 0
        node_count = 0

        for node_ip, processes in node_ip_list_with_node_processes.items():

            self.try_telnet(node_ip, '22')
            node_count += 1

            for process in processes:

                if process in plugin_config.HADOOP_PROCESSES_WITH_PORTS:

                    for i in range(self.common_config.TELNET_TIMEOUT * 60):

                        try:

                            time.sleep(1)
                            telnetlib.Telnet(
                                node_ip,
                                plugin_config.HADOOP_PROCESSES_WITH_PORTS[
                                    process]
                            )

                            break

                        except socket.error:

                            print(
                                'Connection attempt. NODE PROCESS: %s, '
                                'PORT: %s.'
                                % (process,
                                   plugin_config.HADOOP_PROCESSES_WITH_PORTS[
                                       process])
                            )

                    else:

                        self.try_telnet(
                            node_ip,
                            plugin_config.HADOOP_PROCESSES_WITH_PORTS[process]
                        )

            if plugin_config.PROCESS_NAMES['slave'] in processes:

                slave_count += 1

            if plugin_config.PROCESS_NAMES['dn'] in processes:

                datanode_count += 1

            if plugin_config.PROCESS_NAMES['nn'] in processes:

                namenode_ip = node_ip

            if plugin_config.PROCESS_NAMES['master'] in processes:

                master_ip = node_ip

        return {
            'namenode_ip': namenode_ip,
            'master_ip': master_ip,
            'slave_count': slave_count,
            'datanode_count': datanode_count,
            'node_count': node_count
        }

