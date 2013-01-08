BrocadeQuantum
==============

openstack-quantum
=================

Brocade Openstack Quantum Plugin
================================

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


Directory Structure
===================

Normally you will have your directory structure as follows:

         /opt/stack/nova/
         /opt/stack/horizon/
         ...
         /opt/stack/quantum/quantum/plugins/

This repository represents code that will be put as:

         /opt/stack/quantum/quantum/plugins/brocade


Running Setup.py
================

Running setup.py will approp. permissions will copy the default configuration
file to /etc/quantum/plugins/brocade/brocade.ini. This file MUST be edited to
suite your enviroment.

      % cd /opt/stack/quantum/quantum/plugins/brocade
      % python setup.py


Configuration
=============

1. Specify to Quantum that you will be using the Brocade Plugin, this is done
by setting the parameter core_plugin in Quantum

   core_plugin = quantum.plugins.brocade.QuantumPlugin.BrcdPluginV2<br><br>


2. Switch and brocade specific database configuration is specified in the config file located
on the setup at:

   /etc/quantum/plugins/brocade/brocade.ini<br>

   [SWITCH]
   username = admin
   password = password
   address  = <switch mgmt ip address>
   ostype   = NOS
   
   [DATABASE]<br>
   sql_connection = mysql://root:pass@localhost/brcd_quantum?charset=utf8<br>
   
   (please see list of more configurable parameters in the brocade.ini file)


Devstack
========

Please see special notes for devstack at:
http://wiki.openstack.org/brocade-quantum-plugin

