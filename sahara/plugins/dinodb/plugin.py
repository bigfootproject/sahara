# Copyright (c) 2015 P. Michiardi, D. Venzano
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

from sahara import context
from sahara.i18n import _
from sahara.plugins import exceptions as pex
from sahara.plugins.dinodb import edp_engine
from sahara.plugins import provisioning as p
from sahara.plugins import utils as plugin_utils


class DinoDBPluginProvider(p.ProvisioningPluginBase):

    def get_title(self):
        return "DinoDB Plugin"

    def get_description(self):
        return _("This plugin provisions DinoDB clusters.")

    def get_versions(self):
        return ["0.1"]

    def get_node_processes(self, hadoop_version):
        return {
            "DinoDB": ["client", "node"],
            "HDFS": ["namenode", "datanode"]
        }

    def get_configs(self, hadoop_version):
        # TODO
        return []

    def configure_cluster(self, cluster):
        with context.ThreadGroup() as tg:
            for instance in plugin_utils.get_instances(cluster):
                tg.spawn('dinodb-configure-%s' % instance.id,
                         self._config_ops, instance)

    def start_cluster(self, cluster):
        with context.ThreadGroup() as tg:
            for instance in plugin_utils.get_instances(cluster):
                tg.spawn('dinodb-start-%s' % instance.id,
                         self._start_ops, instance)

    # No scaling for DinoDB
    def scale_cluster(self, cluster, instances):
        pass

    def decommission_nodes(self, cluster, instances):
        # TODO
        pass

    def _config_ops(self, instance):
        # TODO
        # with instance.remote() as r:
        #     # check typical SSH command
        #     r.execute_command('echo "Hello, world!"')
        #     # check write file
        #     data_1 = "sp@m"
        #     r.write_file_to('test_data', data_1, run_as_root=True)
        #     # check append file
        #     data_2 = " and eggs"
        #     r.append_to_file('test_data', data_2, run_as_root=True)
        #     # check replace string
        #     r.replace_remote_string('test_data', "eggs", "pony")
        pass

    def _start_ops(self, instance):
        # TODO
        #with instance.remote() as r:
        #    actual_data = r.read_file_from('test_data', run_as_root=True)
        pass

    # No EDP for DinoDB
    def get_edp_engine(self, cluster, job_type):
        return edp_engine.NullJobEngine()

    def get_edp_job_types(self, versions=[]):
        return {}

    def get_edp_config_hints(self, job_type, version):
        if version in self.get_versions():
            return edp_engine.NullJobEngine.get_possible_job_config(job_type)
