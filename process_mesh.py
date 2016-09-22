import sys
import json
import os.path
import base64
from subprocess import Popen, PIPE

if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    GEOMETRYC = os.path.join(asset['buildparams']['working_directory'], 'geometrycRelease')
    tmp_path = os.path.join(asset['tmp_directory'],'geomc.data')
    cmd_path = os.path.join(asset['tmp_directory'],'data.txt')

    cmdline = [GEOMETRYC, '-f', asset['assetmetadata']['inputs'][0], '-o', tmp_path]

    p = Popen(cmdline)
    p.wait()

    with open(tmp_path, 'rb') as bin_file:
        encoded_data_string = base64.b64encode(bin_file.read())

    asset['buildoutput'] = {
        "data": encoded_data_string,
    }

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2, sort_keys=True))

