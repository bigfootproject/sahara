'''
Created on Jan 4, 2014

@author: DO Huy-Hoang
'''
from savanna.openstack.common import excutils
from savanna.tests.integration.tests import base


class SparkTest(base.ITestCase):

    def __run_RL_job(self, hostname, port):

        self.execute_command(
                './spark/run-example org.apache.spark.examples.SparkLR spark://%s:%s'
                % {hostname, port})

    @base.skip_test('SKIP__TEST',
                    message='Test for Spark was skipped.')
    def __run_HdfsLR_job(self, master_ip, namenode_ip, namenode_port, master_port):

        self.execute_command(
                './spark/run-example org.apache.spark.examples.JavaHdfsLR spark://spark1:7077 hdfs://'
                % {master_ip, master_port})

    def __copy_data_to_Hdfs(self, local_file_name, remote_file_name):
        self.execute_command('hdfs fs -copyFromLocal %s %s' %
                             {local_file_name, remote_file_name})

    def _spark_testing(self, cluster_info):
        plugin_config = cluster_info['plugin_config']
        node_count = cluster_info['node_info']['node_count']
        namenode_ip = cluster_info['node_info']['namenode_ip']
        masternode_ip = cluster_info['node_info']['master_ip']
        namenode_port = cluster_info.HADOOP_PROCESSES_WITH_PORTS.namenode
        masternode_port = cluster_info.SPARK_MASTER_PORT

        # Test standalone Spark job (without HDFS)
        self.open_ssh_connection(masternode_ip, plugin_config.NODE_USERNAME)
        self.__run_RL_job(masternode_ip, masternode_port)
        self.close_ssh_connection()

        # Test Spark job with HDFS data
        self.open_ssh_connection(masternode_ip, plugin_config.NODE_USERNAME)
        self.__copy_data_to_Hdfs('/home/ubuntu/spark/lr_data.txt', '/')
        self.__run_HdfsLR_job(masternode_ip, namenode_ip,
                              namenode_port, masternode_port)
        self.close_ssh_connection()
