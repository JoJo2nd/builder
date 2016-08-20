##
## generate python flatbuffers
## 

import argparse
import sys
import json
import os.path
import base64
import uuid
from subprocess import Popen, PIPE

parser = argparse.ArgumentParser(prog='generate python flatbuffers',description='')
parser.add_argument('-d','--directory', help='*.fbs source directory. Recursive.')
parser.add_argument('-o','--output', help='code output directory.')
parser.add_argument('-f', '--flatc')

if __name__ == '__main__':
    args = parser.parse_args()

    cmdline = args.flatc
    cmdline += ' -o ' + args.output
    cmdline += ' --python ' 

    for root, dirs, files in os.walk(args.directory):
        for file in files:
            if os.path.splitext(file)[1] == '.fbs':
                cmdline += ' "%s" '%(os.path.realpath(os.path.join(root, file)))

    print cmdline
    p = Popen(cmdline)
    p.wait()
