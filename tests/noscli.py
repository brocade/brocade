#!/usr/bin/env python
#
# Copyright (c) 2012 Brocade Communications Systems, Inc.
# All Rights Reserved.
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
# Varma Bhupatiraju (vbhupati@#brocade.com)
# Shiv Haris (sharis@brocade.com)
#
"""
Brocade NOS Driver CLI
"""

import argparse
import sys
import logging

from quantum.plugins.brocade.nos import nosdriver as nos

LOG = logging.getLogger(__name__)


class NOSCli(object):

    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.driver = nos.NOSdriver()

    def execute(self, cmd):
        numargs = len(args.otherargs)

        if args.cmd == 'create' and numargs == 1:
            self._create(args.otherargs[0])
        elif args.cmd == 'delete' and numargs == 1:
            self._delete(args.otherargs[0])
        elif args.cmd == 'associate' and numargs == 2:
            self._associate(args.otherargs[0], args.otherargs[1])
        elif args.cmd == 'dissociate' and numargs == 2:
            self._dissociate(args.otherargs[0], args.otherargs[1])
        else:
            print usage_desc
            exit(0)

    def _create(self, id):
        self.driver.create_network(self.host, self.username, self.password, id)

    def _delete(self, id):
        self.driver.delete_network(self.host, self.username, self.password, id)

    def _associate(self, id, mac):
        self.driver.associate_mac_to_network(
            self.host, self.username, self.password, id, mac)

    def _dissociate(self, id, mac):
        self.driver.dissociate_mac_from_network(
            self.host, self.username, self.password, id, mac)


usage_desc = """
Command descriptions:

    create <id>
    delete <id>
    associate <id> <mac>
    dissociate <id> <mac>
"""

parser = argparse.ArgumentParser(description='process args',
                                 usage=usage_desc, epilog='foo bar help')
parser.add_argument('--ip', default='localhost')
parser.add_argument('--username', default='admin')
parser.add_argument('--password', default='password')
parser.add_argument('cmd')
parser.add_argument('otherargs', nargs='*')
args = parser.parse_args()

#print args

noscli = NOSCli(args.ip, args.username, args.password)
noscli.execute(args.cmd)
