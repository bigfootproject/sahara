Apache Spark and HDFS Configurations for Savanna
================================================

This directory contains default XML configuration files and Spark scripts:

* core-default.xml,
* hdfs-default.xml,
* spark-env.sh.template,
* topology.sh

These files are applied for Savanna's plugin of Apache Spark version 0.8.1,
and Cloudera HDFS CDH 4.5.

Files were taken from here:
https://github.com/apache/hadoop-common/blob/release-1.2.1/src/hdfs/hdfs-default.xml
https://github.com/apache/hadoop-common/blob/release-1.2.1/src/core/core-default.xml

XML configs are used to expose default Hadoop configurations to the users through
the Savanna's REST API. It allows users to override some config values which will
be pushed to the provisioned VMs running Hadoop services as part of appropriate
xml config.
