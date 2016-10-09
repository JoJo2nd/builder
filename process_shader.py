import sys
import json
import os.path
import base64
from subprocess import Popen, PIPE
import argparse
import flatbuffers

from gamecommon.utils import convertJsonFBSToBin, formatString, getAssetUUID, getAssetUUIDFromString, bytes_from_file


if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    SHADERC = os.path.join(asset['buildparams']['working_directory'], 'shadercRelease')
    FLATC = os.path.join(asset['buildparams']['working_directory'], 'flatc')
    tmp_path = os.path.join(asset['tmp_directory'],'shader.data')
    d_path = os.path.join(asset['tmp_directory'],'shader.data.d')
    cmd_path = os.path.join(asset['tmp_directory'],'cmdline.txt')
    clt_fbs = os.path.join(asset['asset_directory'],'hart/fbs/shader.fbs')
    fbs_js_tmp_path = os.path.join(asset['tmp_directory'],'shader.json')
    sc_input = formatString(asset['processoptions']['input'], asset['buildparams']);

    includes = ""
    for i in asset['processoptions']['sysincludes']:
        includes += formatString(i, asset['buildparams']) + ';'

    if 'includes' in asset['processoptions']:
        for i in asset['processoptions']['includes']:
            includes += formatString(i, asset['buildparams']) + ';'


    cmdline = SHADERC
    cmdline += ' --depends '
    cmdline += ' -f ' + sc_input
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

    with open(d_path, 'rb') as f:
        includes_string = f.read()
    includes = [sc_input]
    includes += [inc[0:].strip().strip('\\') for inc in includes_string.split('\n')[1:-1]]

    s_bytes = []
    with open(tmp_path, 'rb') as f:
        while 1:
            byte_s = f.read(1)
            if not byte_s:
                break
            s_bytes += [ord(byte_s[0])]

    js_bytes = []
    for b in s_bytes:
        js_bytes += [b]

    output = {
        'supportedProfiles': ['Direct3D11'],
        'shaderArray':[
            {
                'profile': 'Direct3D11',
                'mem': js_bytes,
            }
        ]
    }

    with open(fbs_js_tmp_path, 'wb') as f:
        f.write(json.dumps(output, indent=2, sort_keys=True))

    cmdline = [FLATC, '-o', asset['tmp_directory'], '-b', clt_fbs, fbs_js_tmp_path]

    p = Popen(cmdline)
    p.wait()

    with open(os.path.splitext(fbs_js_tmp_path)[0]+'.bin', 'rb') as bin_file:
        encoded_data_string = base64.b64encode(bin_file.read())

    asset['buildoutput'] = {
        "data": encoded_data_string,
    }
    #Update the input files
    asset['assetmetadata']['inputs'] = includes

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2, sort_keys=True))

