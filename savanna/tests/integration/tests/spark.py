'''
Created on Jan 1, 2014

@author: DO Huy-Hoang
'''
from savanna.openstack.common import excutils
from savanna.tests.integration.tests import base


class SparkTest(base.ITestCase):

    def __check_spark_up(self):
        ret_code, stdout, stderr = self.execute_command('cat /opt/spark/logs/*')
        print stdout
        ret_code, stdout, stderr = self.execute_command('sudo netstat -lnpt | grep 7077')
        print stdout

    def __gethostname(self):
        ret_code, stdout, stderr = self.execute_command('cat /etc/hostname')
        # Remove '\n' character
        hostname = stdout[:-1]
        return hostname

    def __run_RL_job(self, master_hostname, masternode_port):

        self.execute_command(
                'bash /opt/spark/run-example org.apache.spark.examples.SparkLR spark://%s:%s'
                % (master_hostname, masternode_port))

    @base.skip_test('SKIP__TEST',
                    message='Test for Spark was skipped.')
    def __run_HdfsLR_job(self, master_hostname, namenode_ip, namenode_port, master_port, filename):

        self.execute_command(
                'bash /opt/spark/run-example org.apache.spark.examples.JavaHdfsLR spark://%s:%s hdfs://%s:%s/%s'
                % (master_hostname, master_port, namenode_ip, namenode_port, filename))

    def __copy_data_to_Hdfs(self, local_file_name, remote_file_name):
        self.execute_command('sudo hdfs dfs -copyFromLocal %s %s' %
                             {local_file_name, remote_file_name})

    def _spark_testing(self, cluster_info):
        plugin_config = cluster_info['plugin_config']
        namenode_ip = cluster_info['node_info']['namenode_ip']
        masternode_ip = cluster_info['node_info']['master_ip']
        namenode_port = cluster_info['plugin_config']['HADOOP_PROCESSES_WITH_PORTS']['namenode']
        masternode_port = cluster_info['plugin_config']['SPARK_MASTER_PORT']

        # Get hostname of master node and print out info
        self.open_ssh_connection(masternode_ip, plugin_config.NODE_USERNAME)
        self.__check_spark_up()
        master_hostname = self.__gethostname()
        self.close_ssh_connection()

        # Test standalone Spark job (without HDFS)
        self.open_ssh_connection(masternode_ip, plugin_config.NODE_USERNAME)
        self.__run_RL_job(master_hostname, masternode_port)
        self.close_ssh_connection()

        # Test Spark job with HDFS data
        self.open_ssh_connection(masternode_ip, plugin_config.NODE_USERNAME)
        self.__copy_data_to_Hdfs('/opt/spark/lr_data.txt', '/')
        self.__run_HdfsLR_job(master_hostname, namenode_ip,
                              namenode_port, masternode_port, 'lr_data.txt')
        self.close_ssh_connection()
