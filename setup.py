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
run_shell_command("mkdir -p /etc/quantum/plugins/brocade")
run_shell_command("cp config/brocade.ini /etc/quantum/plugins/brocade/brocade.ini")

print "\nALSO update Quantum configuration file to point to the Brocade Plugin,"
print "     inside [DEFAULT] section in /etc/qunatum/quantum.com change:"
print "     core_plugin = quantum.plugins.brocade.QuantumPlugin.BrcdPluginV2"
print "\n"

