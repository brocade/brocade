# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2012 Brocade Communications System, Inc.
# All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# Authors:
# Shiv Haris (sharis@brocade.com)
# Varma Bhupatiraju (vbhupati@#brocade.com)
#
import ConfigParser
import json
import hashlib
import logging
import netaddr
import os
import sys
import traceback
import urllib
import uuid

import sqlalchemy as sa

from quantum.api.v2 import attributes
from quantum.common import exceptions as exception
from quantum.db import api as db
from quantum.db import db_base_plugin_v2
from quantum.db import models_v2
from quantum.common import topics

from quantum.openstack.common import cfg
from quantum.openstack.common import context
from quantum.openstack.common import rpc
from quantum.openstack.common.rpc import dispatcher
from quantum.openstack.common.rpc import proxy

from quantum.db import model_base
from quantum.plugins.brocade.db import models as brcd_db
from quantum.plugins.brocade.nos import nosdriver as nos

CONFIG_FILE = "brocade.ini"
CONFIG_FILE_PATH = "/etc/quantum/plugins/brocade/"
LOG = logging.getLogger(__name__)
#LOG = logging.getLogger("QuantumPlugin")


def parse_config():
    """Parse config file
    """
    return


class LinuxBridgeRpcCallbacks():

    # Set RPC API version to 1.0 by default.
    RPC_API_VERSION = '1.0'
    # Device names start with "vnet0"
    prefix_len = 3
    TAP_PREFIX_LEN = 3

    def __init__(self, rpc_context):
        self.rpc_context = rpc_context

    def create_rpc_dispatcher(self):
        '''Get the rpc dispatcher for this manager.

        If a manager would like to set an rpc API version, or support more than
        one class as the target of rpc messages, override this method.
        '''
        return dispatcher.RpcDispatcher([self])

    def get_device_details(self, rpc_context, **kwargs):
        """Agent requests device details"""

        agent_id = kwargs.get('agent_id')
        device = kwargs.get('device')
        LOG.debug("Device %s details requested from %s", device, agent_id)

        port = brcd_db.get_port(device[self.prefix_len:])
        if port:
            entry = {'device': device,
                     'vlan_id': port.vlan_id,
                     'network_id': port.network_id,
                     'port_id': port.port_id,
                     'physical_network': port.physical_interface,
                     'admin_state_up': port.admin_state_up
                     }

            # Set the port status to UP

            #db.set_port_status(port['id'], q_const.PORT_STATUS_ACTIVE)
        else:
            entry = {'device': device}
            LOG.debug("%s can not be found in database", device)
        return entry

    def update_device_down(self, rpc_context, **kwargs):
        """Device no longer exists on agent"""
        # (TODO) garyk - live migration and port status
        agent_id = kwargs.get('agent_id')
        device = kwargs.get('device')
        LOG.debug("Device %s no longer exists on %s", device, agent_id)
        port = db.get_port_from_device(device[self.TAP_PREFIX_LEN:])
        if port:
            entry = {'device': device,
                     'exists': True}
            # Set port status to DOWN
            db.set_port_status(port['id'], q_const.PORT_STATUS_DOWN)
        else:
            entry = {'device': device,
                     'exists': False}
            LOG.debug("%s can not be found in database", device)
        return entry


class AgentNotifierApi(proxy.RpcProxy):
    '''Agent side of the linux bridge rpc API.

    API version history:
        1.0 - Initial version.

    '''

    BASE_RPC_API_VERSION = '1.0'

    def __init__(self, topic):
        super(AgentNotifierApi, self).__init__(
            topic=topic, default_version=self.BASE_RPC_API_VERSION)
        self.topic_network_delete = topics.get_topic_name(topic,
                                                          topics.NETWORK,
                                                          topics.DELETE)
        self.topic_port_update = topics.get_topic_name(topic,
                                                       topics.PORT,
                                                       topics.UPDATE)

    def network_delete(self, context, network_id):
        self.fanout_cast(context,
                         self.make_msg('network_delete',
                                       network_id=network_id),
                         topic=self.topic_network_delete)

    def port_update(self, context, port, physical_network, vlan_id):
        self.fanout_cast(context,
                         self.make_msg('port_update',
                                       port=port,
                                       physical_interface=physical_network,
                                       vlan_id=vlan_id),
                         topic=self.topic_port_update)


class BrcdPluginV2(db_base_plugin_v2.QuantumDbPluginV2):
    """
    BrcdluginV2 is a Quantum plugin that provides L2 Virtual Network
    functionality using VDX.
    """

    def __init__(self, loglevel=None):

        config = ConfigParser.ConfigParser()
        configfile = CONFIG_FILE_PATH + CONFIG_FILE
        LOG.debug("Using BQP configuration file: %s" % configfile)
        config.read(configfile)

        self._switch = {}
        self._switch['address'] = config.get('SWITCH', 'address')
        self._switch['port'] = config.get('SWITCH', 'port')
        self._switch['username'] = config.get('SWITCH', 'username')
        self._switch['password'] = config.get('SWITCH', 'password')

        self.physical_interface = config.get('PHYSICAL_INTERFACE',
                                             'physical_interface')

        sql_connection = config.get('DATABASE', 'sql_connection')
        sql_dbpool_enable = False
        options = {"sql_connection": sql_connection,
                   "sql_dbpool_enable": sql_dbpool_enable
                   }
        db.configure_db(options)

        self._drv = nos.NOSdriver()
        self._vbm = VlanBitmap()

        self.agent_rpc = True
        self._setup_rpc()

    def _setup_rpc(self):
        # RPC support
        self.topic = topics.PLUGIN
        self.rpc_context = context.RequestContext('quantum', 'quantum',
                                                  is_admin=False)
        self.conn = rpc.create_connection(new=True)
        self.callbacks = LinuxBridgeRpcCallbacks(self.rpc_context)
        self.dispatcher = self.callbacks.create_rpc_dispatcher()
        self.conn.create_consumer(self.topic, self.dispatcher,
                                  fanout=False)
        # Consume from all consumers in a thread
        self.conn.consume_in_thread()
        self.notifier = AgentNotifierApi(topics.AGENT)

    def get_all_networks(self, tenant_id, **kwargs):
        networks = []
        return networks

    def create_network(self, context, network, policy=None):

        net = network['network']
        tenant_id = net['tenant_id']
        network_name = net['name']

        net_uuid = str(uuid.uuid4())
        vlan_id = self._vbm.getNextVlan(None)
        sw = self._switch
        self._drv.create_network(sw['address'],
                                 sw['username'],
                                 sw['password'],
                                 vlan_id)
        network['network']['id'] = net_uuid
        brcd_db.create_network(net_uuid, vlan_id)
        return super(BrcdPluginV2, self).create_network(context, network)

    def delete_network(self, context, id):

        # Not tested
        net = brcd_db.get_network(id)
        vlan_id = net['vlan']

        sw = self._switch
        try:
            self._drv.delete_network(sw['address'],
                                     sw['username'],
                                     sw['password'],
                                     vlan_id)
        except Exception as ex:
            raise

        brcd_db.delete_network(id)
        self._vbm.releaseVlan(int(vlan_id))
        result = super(BrcdPluginV2, self).delete_network(context, id)
        return result

    def get_networks(self, context, filters=None, fields=None):

        LOG.warning("BrcdPluginV2:get_networks() called")

        if filters.get("shared") == [True]:
            return []

        nets = super(BrcdPluginV2, self).get_networks(context)
        for net in nets:
            bnet = brcd_db.get_network(net['id'])
            net['vlan'] = bnet['vlan']
        return nets

    def get_network(self, context, id, fields=None):
        net = super(BrcdPluginV2, self).get_network(context, id, None)

        bnet = brcd_db.get_network(id)
        net['vlan'] = bnet['vlan']

        return net

    def update_network(self, context, id, network):
        LOG.debug("BrcdPluginV2:update_anetwork() called")

    def create_port(self, context, port):

        LOG.warning("BrcdPluginV2:create_port() called")
        port_id = str(uuid.uuid4())
        port_id = port_id[0:8]
        port['port']['id'] = port_id
        admin_state_up = True

        port_update = {"port": {"admin_state_up": admin_state_up}}
        tenant_id = port['port']['tenant_id']
        network_id = port['port']['network_id']
        port_state = "UP"

        physical_interface = self.physical_interface

        bnet = brcd_db.get_network(network_id)
        vlan_id = bnet['vlan']

        try:
            quantum_db = super(BrcdPluginV2, self).create_port(context, port)
        except Exception as e:
            raise e

        network = self.get_network(context, network_id)
        interface_mac = quantum_db['mac_address']

        sw = self._switch

        # Transform mac format: XX:XX:XX:XX:XX:XX -> XXXX.XXXX.XXXX
        mac = interface_mac.replace(":", "")
        mac = mac[0:4] + "." + mac[4:8] + "." + mac[8:12]
        self._drv.associate_mac_to_network(sw['address'],
                                           sw['username'],
                                           sw['password'],
                                           vlan_id,
                                           mac)
        p = super(BrcdPluginV2, self).update_port(context,
                                                  port["port"]["id"],
                                                  port_update)
        p['vlan'] = vlan_id
        brcd_db.create_port(port_id, network_id, physical_interface,
                            vlan_id, tenant_id, admin_state_up)
        return p

    def update_port(self, context, id, port):
        LOG.warning("BrcdPluginV2:update_port() called")
        return super(BrcdPluginV2, self).update_port(context, id, port)

    def delete_port(self, context, id):
        LOG.warning("BrcdPluginV2:delete_port() called")
        return super(BrcdPluginV2, self).delete_port(context, id)

    def get_port(self, context, id, fields=None):
        LOG.warning("BrcdPluginV2:get_port() called")
        quantum_db = super(BrcdPluginV2, self).get_port(context, id, fields)
        return quantum_db

    def get_plugin_version(self):
        return PLUGIN_VERSION


class VlanBitmap(object):

    vlans = {}

    def __init__(self):
        for x in xrange(2, 4094):
            self.vlans[x] = None
        nets = brcd_db.get_networks()
        for net in nets:
            uuid = net['id']
            vlan = net['vlan']
            if vlan is not None:
                self.vlans[int(vlan)] = 1
        return

    def getNextVlan(self, vlan_id):
        if vlan_id is None:
            for x in xrange(2, 4094):
                if self.vlans[x] is None:
                    self.vlans[x] = 1
                    return x
        else:
            if self.vlans[vlan_id] is None:
                self.vlans[vlan_id] = 1
                return vlan_id
            else:
                return None

    def releaseVlan(self, vlan_id):

        if self.vlans[vlan_id] is not None:
            self.vlans[vlan_id] = None

        return
