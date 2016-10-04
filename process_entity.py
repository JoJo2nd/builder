

import sys
import json
import os.path
import base64
from gamecommon.utils import convertJsonFBSToBin, formatString
from subprocess import Popen, PIPE

log = None

if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    FLATC = os.path.join(asset['buildparams']['working_directory'], "flatc")
    tmp_dir = asset['tmp_directory']
    info_path = os.path.join(asset['tmp_directory'],'data.txt')
    asset_base = os.path.split(asset['assetpath'])[0]
    fbs_def_path_map = asset['processoptions']['definitions'];
    fbs_templ_def_path = formatString(asset['processoptions']['fbstemplate'], asset['buildparams'])
    obj_path = os.path.realpath(os.path.join(asset_base, formatString(asset['processoptions']['input'], asset['buildparams'])))
    final_tmp_path = os.path.join(asset['tmp_directory'], 'final_template.json')

    log = open(os.path.join(asset['tmp_directory'], 'log.txt'), 'wb')

    with open(obj_path, 'rb') as f:
        entity = json.loads(f.read());

    template_uuid = entity['entityTemplate']
    entity_def = entity['properties']

    includes = []
    js_offsets = []
    js_bytes = []
    for key, value in entity_def.iteritems():
        fbs_def_path = formatString(fbs_def_path_map[key], asset['buildparams'])
        comp_obj_path = os.path.join(asset['tmp_directory'], key+'.json')

        ii, s_bytes, _ = convertJsonFBSToBin(FLATC, value, fbs_def_path, comp_obj_path, tmp_dir, log)
        includes += ii

        js_offsets += [len(js_bytes)]
        for b in s_bytes:
            js_bytes += [b]


    final_template = {
        'entityTemplate':template_uuid,
        'componentOffsets':js_offsets,
        'componentData':js_bytes,
    }

    log.write(str(final_template)+'\n')

    ii, s_bytes, r_bytes = convertJsonFBSToBin(FLATC, final_template, fbs_templ_def_path, final_tmp_path, tmp_dir, log)
    includes += ii

    asset['buildoutput'] = {
        "data": base64.b64encode(r_bytes),
    }
    #Update the input files
    asset['assetmetadata']['inputs'] = list(set(includes)) # list(set(x)) to make x unique

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2, sort_keys=True))
