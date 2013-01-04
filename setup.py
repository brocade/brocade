import datetime
import os
import re
import subprocess
import sys

def run_shell_command(cmd):
    output = subprocess.Popen(["/bin/sh", "-c", cmd],
                              stdout=subprocess.PIPE)
    out = output.communicate()
    if len(out) == 0:
        return None
    if len(out[0].strip()) == 0:
        return None
    return out[0].strip()


run_shell_command("mkdir -p /etc/quantum/plugins/brocade")
run_shell_command("cp config/brocade.ini /etc/quantum/plugins/brocade/brocade.ini")
