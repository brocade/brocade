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

import os
import sys

from quantum.plugins.brocade.db import models as brcd_db


class VlanBitmap(object):

    # Keep track of the vlans that have been allocated/de-allocated
    # uses a bitmap to do this
    vlans = {}

    def __init__(self):
        self.vlans = {}
        #for net in brcd_db.get_networks():
        #if net['vlan']:
        #vlan = net['vlan']
        #self.vlans[int(vlan)] = True

        for x in xrange(2, 4094):
            self.vlans[x] = None
            nets = brcd_db.get_networks()
            for net in nets:
                uuid = net['id']
                vlan = net['vlan']
                if vlan is not None:
                    self.vlans[int(vlan)] = 1

    def get_next_vlan(self, vlan_id):
        if vlan_id is None:
            for x in xrange(2, 4094):
                if self.vlans[x] is None:
                    self.vlans[x] = True
                    return x
        else:
            if self.vlans[vlan_id] is None:
                self.vlans[vlan_id] = True
                return vlan_id
            else:
                return None

    def release_vlan(self, vlan_id):
        if self.vlans[vlan_id] is not None:
            self.vlans[vlan_id] = None
