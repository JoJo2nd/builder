#
# process resource collection
#

import sys
import json
import os.path
import base64
import uuid
from subprocess import Popen, PIPE

if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    FLATC = os.path.join(asset['buildparams']['working_directory'], 'flatc')
    tmp_path = os.path.join(asset['tmp_directory'],'flatc.in.data')
    cmd_path = os.path.join(asset['tmp_directory'],'data.txt')
    clt_fbs = os.path.join(asset['asset_directory'],'hart/fbs/resourcecollection.fbs')

    final_output = {}
    final_output['assetUUIDs'] = []
    for i in asset['assetmetadata']['prerequisites']:
        au = uuid.UUID(i)
        b = bytearray()
        b.extend(au.bytes)
        final_output['assetUUIDs'] += [{
            'highword3': ((b[15]<<24) | (b[14]<<16) | (b[13]<<8) | (b[12])), 
            'highword2': ((b[11]<<24) | (b[10]<<16) | (b[ 9]<<8) | (b[ 8])), 
            'highword1': ((b[ 7]<<24) | (b[ 6]<<16) | (b[ 5]<<8) | (b[ 4])), 
            'lowword'  : ((b[ 3]<<24) | (b[ 2]<<16) | (b[ 1]<<8) | (b[ 0]))
        }]

    with open(tmp_path, 'wb') as f:
        f.write(json.dumps(final_output, indent=2))

    cmdline = [FLATC, '-o', asset['tmp_directory'], '-b', clt_fbs, tmp_path]
    with open(cmd_path,'wb') as f:
        f.write(str(cmdline))

    p = Popen(cmdline)
    p.wait()

    with open(os.path.splitext(tmp_path)[0]+'.bin', 'rb') as bin_file:
        encoded_data_string = base64.b64encode(bin_file.read())

    asset['buildoutput'] = {
        "data": encoded_data_string,
    }

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2))