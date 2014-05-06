Apache Spark and HDFS Configurations for Sahara
===============================================

This directory contains default XML configuration files and Spark scripts:

* core-default.xml,
* hdfs-default.xml,
* spark-env.sh.template,
* topology.sh

These files are used by Sahara's plugin for Apache Spark and Cloudera HDFS.

XML configs are used to expose default Hadoop configurations to the users through
Sahara's REST API. It allows users to override some config values which will be
pushed to the provisioned VMs running Hadoop services as part of appropriate xml
config.
