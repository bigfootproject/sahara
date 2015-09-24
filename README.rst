OpenStack Data Processing ("Sahara") project (Spark experimental fork)
======================================================================

This repository is a fork of the main `OpenStack Sahara repo <https://github.com/openstack/sahara>`_. This fork relates mainly to the Spark plugin development, with bug fixes, optimizations and updates related to the work of the Bigfoot project: http://bigfootproject.eu/

To use this version of Sahara, you will need images created with this fork of the image builder: https://github.com/bigfootproject/sahara-image-elements

The main changes from the standard Sahara are:

- Support for more recent Spark versions, currently we are supporting Spark 1.5.0
- Spark Notebook (https://github.com/andypetrella/spark-notebook) support. You can create a Spark cluster with notebooks already available and configured. Like iPython, but with Spark! The Spark Notebook is listed in the processes list when creating a new node group template. You can have at maximum one notebook process per cluster. Once the cluster has been started, a link to the notebook can be found at the bottom of the cluster information page.
- Relaxed checks to let the user create HDFS-only and Spark-only clusters: this allows the concept of storage-only clusters, relatively static, and compute-only clusters that come and go.
- Spark clusters can be configured with a default HDFS location
- Data locality: by using the cluster-level "HDFS storage cluster" option a compute cluster will be co-located on the same physical hosts on which the datanodes for that storage cluster are found
- Swift data source for Spark, with fixes for Spark 1.3
- Smaller fixes and workarounds for bugs, while waiting for a proper fix in upstream Sahara

This repository is periodically merged with the upstream Sahara master branch.

Virtual Machine image
---------------------

Images ready to be used with this version of Sahara can be found here:
https://drive.google.com/folderview?id=0B2TbBvh6BGVcfkVIaWhZRXZ4dVRYUjBCWkV0WTAxWENxeUMteVowd1JSXzNDb3gza0U5MXM&usp=sharing

Contact us
----------

This fork of Sahara is developed and maintained by the Distributed Systems Group at Eurecom (http://www.eurecom.fr).

* Pietro Michiardi (http://www.eurecom.fr/~michiard/)
* Daniele Venzano (http://www.eurecom.fr/en/people/venzano-daniele)

License
-------

Apache License Version 2.0 http://www.apache.org/licenses/LICENSE-2.0
