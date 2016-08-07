import sys
import json
import os.path
import base64
from subprocess import Popen, PIPE
import argparse

def formatString(s, parameters):
    for k, p in parameters.iteritems():
        s = s.replace("%%(%s)"%(k), p)
    return s

if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    SHADERC = os.path.join(asset['buildparams']['working_directory'], '../../external/bgfx/.build/win64_vs2015/bin/shadercRelease')
    tmp_path = os.path.join(asset['tmp_directory'],'shader.data')
    cmd_path = os.path.join(asset['tmp_directory'],'cmdline.txt')

    includes = ""
    for i in asset['processoptions']['sysincludes']:
        includes += formatString(i, asset['buildparams']) + ';'

    if 'includes' in asset['processoptions']:
        for i in asset['processoptions']['includes']:
            includes += formatString(i, asset['buildparams']) + ';'


    cmdline = SHADERC
    cmdline += ' -f ' + asset['assetmetadata']['inputs'][0]
    cmdline += ' -i ' + '"' + includes + '"'
    cmdline += ' -o ' + tmp_path
    if 'type' in asset['processoptions']:
        cmdline += ' --type ' + asset['processoptions']['type']
    if 'platform' in asset['processoptions']:
        cmdline += ' --platform ' + asset['processoptions']['platform']
    if 'platformext' in asset['processoptions']:
        cmdline += ' ' + asset['processoptions']['platformext']

    with open(cmd_path, 'wb') as f:
        f.write(cmdline)

    p = Popen(cmdline)
    p.wait()

    with open(tmp_path, 'rb') as bin_file:
        encoded_data_string = base64.b64encode(bin_file.read())

    asset['buildoutput'] = {
        "data": encoded_data_string,
    }

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2))

