import sys
import json
import os.path
import base64
from subprocess import Popen, PIPE

if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    TEXTUREC = os.path.join(asset['buildparams']['working_directory'], '../../external/bgfx/.build/win64_vs2015/bin/texturecRelease')
    tmp_path = os.path.join(asset['tmp_directory'],'texc.data.ktx')
    cmd_path = os.path.join(asset['tmp_directory'],'data.txt')

    cmdline = TEXTUREC
    cmdline += ' -f ' + asset['assetmetadata']['inputs'][0]
    cmdline += ' -o ' + tmp_path
    cmdline += ' -t ' + asset['processoptions']['format']
    if 'generatemips' in asset['processoptions'] and asset['processoptions']['generatemips'] == True:
        cmdline += ' -m '

    p = Popen(cmdline)
    p.wait()

    with open(tmp_path, 'rb') as bin_file:
        encoded_data_string = base64.b64encode(bin_file.read())

    asset['buildoutput'] = {
        "data": encoded_data_string,
    }

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset))

