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

from nose import config
from nose import core

sys.path.append(os.getcwd())
sys.path.append(os.path.dirname(__file__))

from quantum.common.test_lib import run_tests, test_config

if __name__ == '__main__':
    exit_status = False

    # if a single test case was specified,
    # we should only invoked the tests once
    invoke_once = len(sys.argv) > 1

    test_config['plugin_name'] = "QuantumPluginV2"

    cwd = os.getcwd()

    working_dir = os.path.abspath("quantum/plugins/brocade")
    c = config.Config(stream=sys.stdout,
                      env=os.environ,
                      verbosity=3,
                      workingDir=working_dir)
    exit_status = exit_status or run_tests(c)

    sys.exit(exit_status)
