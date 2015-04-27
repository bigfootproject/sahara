OpenStack Data Processing ("Sahara") project (Spark experimental fork)
======================================================================

This repository is a fork of the main `OpenStack Sahara repo <https://github.com/openstack/sahara>`_. This fork relates mainly to the Spark plugin development, with bug fixes, optimizations and updates related to the work of the Bigfoot project: http://bigfootproject.eu/

To use this version of Sahara, you will need images created with this fork of the image builder: https://github.com/bigfootproject/savanna-image-elements

The main changes from the standard Sahara are:

- Support for more recent Spark versions, currently we are supporting Spark 1.3.0
- Relaxed checks to let the user create HDFS-only and Spark-only clusters: this allows the concept of storage-only clusters, relatively static, and compute-only clusters that come and go.
- Spark clusters can be configured with a default HDFS location
- Data locality: by using the cluster-level "HDFS storage cluster" option a compute cluster will be co-located on the same physical hosts on which the datanodes for that storage cluster are found
- Swift data source for Spark, with fixes for Spark 1.3
- Smaller fixes and workarounds for bugs, while waiting for a proper fix in upstream Sahara

This repository is periodically merged with the upstream Sahara master branch.


License
-------

Apache License Version 2.0 http://www.apache.org/licenses/LICENSE-2.0
