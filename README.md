BrocadeQuantum
==============

openstack-quantum
=================

Brocade Openstack Quantum Plugin
================================

http://wiki.openstack.org/brocade-quantum-plugin

Opentack Brocade Quantum Plugin implements the Quantum v2.0 API.

It is meant for orchestrating Brocade VCS switches running NOS, examples of these are:

   1. VDX 67xx series of switches
   2. VDX 87xx series of switches


Brocade Quantum plugin implements the Q v2.0 API. It uses NETCONF at the backend
to configure the Brocade switch.


             +------------+        +------------+          +-------------+
             |            |        |            |          |             |
             |            |        |            |          |   Brocade   |
             | Openstack  |  v2.0  |  Brocade   |  NETCONF |  VCS Switch |
             | Quantum    +--------+  Quantum   +----------+             |
             |            |        |  Plugin    |          |  VDX 67xx   |
             |            |        |            |          |  VDX 87xx   |
             |            |        |            |          |             |
             |            |        |            |          |             |
             +------------+        +------------+          +-------------+


Configuration
=============

1. Specify to Quantum that you will be using the Brocade Plugin, this is done
by setting the parameter core_plugin in Quantum

   core_plugin = quantum.plugins.brocade.QuantumPlugin.BrcdPluginV2<br><br>


2. Switch and brocade specific database configuration is specified in the config file located
on the setup at:

   /etc/quantum/plugins/brocade/brocade.ini<br>

   [SWITCH]<br>
   username = admin<br>
   password = password<br>
   address  = <switch mgmt ip address><br>
   ostype   = NOS<br>
<br>
   [DATABASE]<br>
   sql_connection = mysql://root:pass@localhost/brcd_quantum?charset=utf8<br>

   (please see list of more configurable parameters in the brocade.ini file)


Devstack
========

Please see special notes for devstack at:
http://wiki.openstack.org/brocade-quantum-plugin

