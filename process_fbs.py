import sys
import json
import os.path
import base64
import re
from subprocess import Popen, PIPE
from gamecommon.utils import convertJsonFBSToBin, formatString, getAssetUUID, getAssetUUIDFromString, buildStrFromUUIDFromNumbers, scanJSONForAssetUUIDs

log = None

if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    FLATC = os.path.join(asset['buildparams']['working_directory'], "flatc")
    tmp_dir = asset['tmp_directory']
    info_path = os.path.join(asset['tmp_directory'],'data.txt')
    asset_base = os.path.split(asset['assetpath'])[0]
    fbs_def_path = formatString(asset['processoptions']['def'], asset['buildparams'])
    obj_path = os.path.realpath(os.path.join(asset_base, asset['processoptions']['input']))
    tmp_path = os.path.join(asset['tmp_directory'], os.path.splitext(os.path.split(obj_path)[1])[0]+'.bin')

    log = open(os.path.join(asset['tmp_directory'], 'log.txt'), 'wb')

    cmdline = FLATC
    cmdline += ' -o ' + tmp_dir
    cmdline += ' -b ' + fbs_def_path
    cmdline += ' ' + obj_path

    prerequisites = scanJSONForAssetUUIDs(obj_path)

    p = Popen(cmdline)
    p.wait()

    if not p.returncode == 0:
        print(includes_string+'\n')
        raise ValueError('flatc compiler returned an error:'+includes_string)

    cmdline1 = cmdline
    cmdline = FLATC
    cmdline += ' -M --cpp ' + fbs_def_path
    p = Popen(cmdline, stdout=PIPE)
    includes_string = p.communicate()[0]

    if not p.returncode == 0:
        print(includes_string+'\n')
        raise ValueError('flatc compiler returned an error:'+includes_string)

    includes = [obj_path]
    includes += [inc[0:-1].strip().strip('\\') for inc in includes_string.split('\n')[1:-1]]

    with open(info_path, 'wb') as f:
        f.write(cmdline1+'\n')
        f.write(cmdline+'\n')
        f.write(includes_string+'\n')
        f.writelines(includes)

    with open(tmp_path, 'rb') as bin_file:
        encoded_data_string = base64.b64encode(bin_file.read())

    asset['buildoutput'] = {
        "data": encoded_data_string,
    }
    #Update the input files
    asset['assetmetadata']['inputs'] = list(set(includes))
    asset['assetmetadata']['prerequisites'] = list(set(prerequisites))

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2, sort_keys=True))
