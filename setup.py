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
import datetime
import os
import re
import subprocess
import sys


def run_shell_command(cmd):
    print cmd
    output = subprocess.Popen(["/bin/sh", "-c", cmd],
                              stdout=subprocess.PIPE)
    out = output.communicate()
    if len(out) == 0:
        return None
    if len(out[0].strip()) == 0:
        return None
    return out[0].strip()


print "\nCopy configuration files ..."
run_shell_command(
    "mkdir -p /etc/quantum/plugins/brocade")
run_shell_command(
    "cp config/brocade.ini /etc/quantum/plugins/brocade/brocade.ini")

print "\nALSO update Quantum config file to point to the Brocade Plugin,"
print "     inside [DEFAULT] section in /etc/qunatum/quantum.com change:"
print "     core_plugin = quantum.plugins.brocade.QuantumPlugin.BrcdPluginV2"
print "\n"
