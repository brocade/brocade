# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 Brocade Communications System, Inc.
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
# (Some parts adapted from LinuxBridge Plugin)
# TODO (shiv) need support for security groups


import json
import hashlib
import netaddr
import os
import sys
import traceback
import urllib
import pdb

import sqlalchemy as sa

from quantum.agent import securitygroups_rpc as sg_rpc
from quantum.api.v2 import attributes
from quantum.common import constants as q_const
from quantum.common import exceptions as q_exc
from quantum.common import rpc as q_rpc
from quantum.common import topics
from quantum.common import utils
from quantum.db import api as db
from quantum.db import api as db_api
from quantum.db import db_base_plugin_v2
from quantum.db import dhcp_rpc_base
from quantum.db import l3_db
from quantum.db import l3_rpc_base
from quantum.db import model_base
from quantum.db import models_v2
from quantum.db import quota_db
from quantum.db import securitygroups_rpc_base as sg_db_rpc
from quantum.openstack.common import cfg
from quantum.openstack.common import context
from quantum.openstack.common import log as logging
from quantum.openstack.common import rpc
from quantum.openstack.common import uuidutils as uu_utils
from quantum.openstack.common.rpc import dispatcher
from quantum.openstack.common.rpc import proxy
from quantum.plugins.brocade import vlanbm as vbm
from quantum.plugins.brocade.db import models as brcd_db
from quantum.plugins.brocade.nos import nosdriver as nos


LOG = logging.getLogger(__name__)
PLUGIN_VERSION = 0.88
AGENT_OWNER_PREFIX = "network:"


class LinuxBridgeRpcCallbacks(dhcp_rpc_base.DhcpRpcCallbackMixin,
                              l3_rpc_base.L3RpcCallbackMixin,
                              sg_db_rpc.SecurityGroupServerRpcCallbackMixin):

    RPC_API_VERSION = '1.1'
    # Device names start with "tap"
    # history
    #   1.1 Support Security Group RPC
    TAP_PREFIX_LEN = 3

    def create_rpc_dispatcher(self):
        '''Get the rpc dispatcher for this manager.

        If a manager would like to set an rpc API version, or support more than
        one class as the target of rpc messages, override this method.
        '''
        return q_rpc.PluginRpcDispatcher([self])

    @classmethod
    def get_port_from_device(cls, device):
        """Get port from the brocade specific db."""
        port = brcd_db.get_port(device[cls.TAP_PREFIX_LEN:])
        # TODO(shiv): need to extend the db model to include device owners
        # make it appears that the device owner is of type network
        if port:
            port['device'] = device
            port['device_owner'] = AGENT_OWNER_PREFIX
        return port

    def get_device_details(self, rpc_context, **kwargs):
        """Agent requests device details."""
        agent_id = kwargs.get('agent_id')
        device = kwargs.get('device')
        LOG.debug(_("Device %(device)s details requested from %(agent_id)s"),
                  locals())
        port = brcd_db.get_port(device[self.TAP_PREFIX_LEN:])
        if port:
            entry = {'device': device,
                     'vlan_id': port.vlan_id,
                     'network_id': port.network_id,
                     'port_id': port.port_id,
                     'physical_network': port.physical_interface,
                     'admin_state_up': port.admin_state_up
                     }

        else:
            entry = {'device': device}
            LOG.debug("%s can not be found in database", device)
        return entry

    def update_device_down(self, rpc_context, **kwargs):
        """Device no longer exists on agent"""

        agent_id = kwargs.get('agent_id')
        device = kwargs.get('device')
        LOG.debug(_("Device %(device)s no longer exists on %(agent_id)s"),
                  locals())
        port = self.get_port_from_device(device)
        if port:
            entry = {'device': device,
                     'exists': True}
            # Set port status to DOWN
            db.set_port_status(port['id'], q_const.PORT_STATUS_DOWN)
        else:
            entry = {'device': device,
                     'exists': False}
            LOG.debug(_("%s can not be found in database"), device)
        return entry


class AgentNotifierApi(proxy.RpcProxy,
                       sg_rpc.SecurityGroupAgentRpcApiMixin):
    '''Agent side of the linux bridge rpc API.

    API version history:
        1.0 - Initial version.

    '''

    BASE_RPC_API_VERSION = '1.0'

    def __init__(self, topic):
        super(AgentNotifierApi, self).__init__(
            topic=topic, default_version=self.BASE_RPC_API_VERSION)
        self.topic = topic
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
                                       physical_network=physical_network,
                                       vlan_id=vlan_id),
                         topic=self.topic_port_update)


class BrcdPluginV2(db_base_plugin_v2.QuantumDbPluginV2):
    """
    BrcdluginV2 is a Quantum plugin that provides L2 Virtual Network
    functionality using VDX.
    """

    def __init__(self, loglevel=None):
        """Initialize Brocade Plugin, specify switch address
        and db configuration.
        """
        self._switch = {}

        switch_opts = [
            cfg.StrOpt('address', default=''),
            cfg.StrOpt('username', default=''),
            cfg.StrOpt('password', default=''),
            cfg.StrOpt('ostype', default='NOS')]

        physical_interface_opts = [
            cfg.StrOpt('physical_interface', default='eth0')]

        cfg.CONF.register_opts(switch_opts, "SWITCH")
        cfg.CONF.register_opts(physical_interface_opts, "PHYSICAL_INTERFACE")
        cfg.CONF(project='quantum')

        self._switch['address'] = cfg.CONF.SWITCH.address
        self._switch['username'] = cfg.CONF.SWITCH.username
        self._switch['password'] = cfg.CONF.SWITCH.password

        self.physical_interface = \
            cfg.CONF.PHYSICAL_INTERFACE.physical_interface

        db.configure_db()

        self._drv = nos.NOSdriver()
        self._vbm = vbm.VlanBitmap()
        self._setup_rpc()

    def _setup_rpc(self):
        # RPC support
        self.topic = topics.PLUGIN
        self.rpc_context = context.RequestContext('quantum', 'quantum',
                                                  is_admin=False)
        self.conn = rpc.create_connection(new=True)
        self.callbacks = LinuxBridgeRpcCallbacks()
        self.dispatcher = self.callbacks.create_rpc_dispatcher()
        self.conn.create_consumer(self.topic, self.dispatcher,
                                  fanout=False)
        # Consume from all consumers in a thread
        self.conn.consume_in_thread()
        self.notifier = AgentNotifierApi(topics.AGENT)

    def create_network(self, context, network, policy=None):
        """This call to create network translates to creation of
        port-profile on the physical switch.
        """
        net = network['network']
        tenant_id = net['tenant_id']
        network_name = net['name']

        net_uuid = uu_utils.generate_uuid()
        vlan_id = self._vbm.get_next_vlan(None)

        sw = self._switch
        self._drv.create_network(sw['address'],
                                 sw['username'],
                                 sw['password'],
                                 vlan_id)
        network['network']['id'] = net_uuid
        brcd_db.create_network(context, net_uuid, vlan_id)
        return super(BrcdPluginV2, self).create_network(context, network)

    def delete_network(self, context, id):
        """This call to delete the network translates to removing
        the port-profile on the physical switch.
        """
        net = brcd_db.get_network(context, id)
        vlan_id = net['vlan']

        sw = self._switch
        self._drv.delete_network(sw['address'],
                                 sw['username'],
                                 sw['password'],
                                 vlan_id)
        brcd_db.delete_network(context, id)
        self._vbm.releaseVlan(int(vlan_id))
        result = super(BrcdPluginV2, self).delete_network(context, id)
        return result

    def get_networks(self, context, filters=None, fields=None):
        """Get port-profiles on the physical switch and look
        up the vlan that was configured when this network was created
        """

        # Current no support for shared networks
        if filters.get("shared") == [True]:
            return []

        nets = super(BrcdPluginV2, self).get_networks(context)
        for net in nets:
            bnet = brcd_db.get_network(context, net['id'])
            net['vlan'] = bnet['vlan']
        return nets

    def get_network(self, context, id, fields=None):
        """Get a specific port-profile."""
        net = super(BrcdPluginV2, self).get_network(context, id, None)
        bnet = brcd_db.get_network(context, id)
        net['vlan'] = bnet['vlan']

        return net

    def update_network(self, context, id, network):
        """We do nothing here for now; in future we will could change the vlan,
        ACL or QOS for the network.
        """
        pass

    def create_port(self, context, port):
        """Creat logical port on the switch."""

        port_id = uu_utils.generate_uuid()
        port_id = port_id[0:8]
        port['port']['id'] = port_id
        admin_state_up = True

        port_update = {"port": {"admin_state_up": admin_state_up}}
        tenant_id = port['port']['tenant_id']
        network_id = port['port']['network_id']
        port_state = "UP"

        physical_interface = self.physical_interface

        bnet = brcd_db.get_network(context, network_id)
        vlan_id = bnet['vlan']

        try:
            quantum_port = super(BrcdPluginV2, self).create_port(context, port)
        except Exception as e:
            raise e

        network = self.get_network(context, network_id)
        interface_mac = quantum_port['mac_address']

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
        #
        # Currently this does nothing for the physical switch
        # we will support this for g-vlan (in future)
        #
        return super(BrcdPluginV2, self).update_port(context, id, port)

    def delete_port(self, context, id):
        brcd_db.delete_port(id)
        return super(BrcdPluginV2, self).delete_port(context, id)

    def get_port(self, context, id, fields=None):
        return super(BrcdPluginV2, self).get_port(context, id, fields)

    def get_plugin_version(self):
        return PLUGIN_VERSION
