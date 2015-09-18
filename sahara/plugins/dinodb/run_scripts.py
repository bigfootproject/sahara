# Copyright (c) 2014 Hoang Do, Phuc Vo, P. Michiardi, D. Venzano
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

import os

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def start_processes(remote, *processes):
    for proc in processes:
        if proc == "namenode":
            remote.execute_command("sudo service hadoop-hdfs-namenode start")
        elif proc == "datanode":
            remote.execute_command("sudo service hadoop-hdfs-datanode start")
        else:
            remote.execute_command("screen -d -m sudo hadoop %s" % proc)


def refresh_nodes(remote, service):
    remote.execute_command("sudo -u hdfs hadoop %s -refreshNodes"
                           % service)


def format_namenode(nn_remote):
    nn_remote.execute_command("sudo -u hdfs hadoop namenode -format")


def clean_port_hadoop(nn_remote):
    nn_remote.execute_command(("sudo netstat -tlnp"
                               "| awk '/:8020 */"
                               "{split($NF,a,\"/\"); print a[1]}'"
                               "| xargs sudo kill -9"))


def start_spark_history_server(nn_remote, sp_home, eventlog):
    if eventlog.startswith("file://"):
        nn_remote.execute_command("mkdir " + eventlog[7:])
    nn_remote.execute_command("bash " + os.path.join(sp_home,
                                                     "sbin/start-history-server.sh " + eventlog))


def start_spark_master(nn_remote, sp_home):
    nn_remote.execute_command("bash " + os.path.join(sp_home,
                                                     "sbin/start-all.sh"))


def stop_spark(nn_remote, sp_home):
    nn_remote.execute_command("bash " + os.path.join(sp_home,
                                                     "sbin/stop-all.sh"))


def start_spark_notebook(nb_remote):
    nb_remote.execute_command("bash /tmp/sahara_notebook_start.sh")

def start_dinodb_node(din_remote, din_home, dimeta_home):
    din_remote.execute_command("cd " + din_home + "; bin/pg_ctl -D datadir")
    din_remote.execute_command("cd " + dimeta_home + "; nohup python dinodbnode.py &")

def start_dinodb_master(dim_remote, din_home, dim_home):
    dim_remote.execute_command("cd " + din_home + "; bin/pg_ctl -D datadir")
    dim_remote.execute_command("cd " + os.path.join(dim_home, "bin") + "; ./gs-server.sh")


