

import sys
import json
import os.path
import base64
from gamecommon.utils import convertJsonFBSToBin, formatString, scanJSONStringForAssetUUIDs
from subprocess import Popen, PIPE

log = None

#def merge_two_dicts(x, y):
#    """Given two dicts, merge them into a new dict as a shallow copy. 
#    Matching entries in the second parameter win any conflicts"""
#    z = x.copy()
#    z.update(y)
#    return z

def merge_two_dicts(a, b, path=None):
    "merges b into a"
    if path is None: path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_two_dicts(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass # same leaf value
            else:
                #raise Exception('Conflict at %s' % '.'.join(path + [str(key)]))
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a


def process_entity(enty_path):
    fin_inputs = []
    fin_prereq = []
    fin_props = {}
    enty_path_base = os.path.split(enty_path)[0]
    log.write('Reading entity json %s \n'%(enty_path))
    with open(enty_path, 'rb') as f:
        entity = json.loads(f.read());

    if 'import' in entity:
        for im in entity['import']:
            new_inputs, new_prereq, new_props = process_entity(os.path.join(enty_path_base, im))
            fin_inputs += new_inputs
            fin_prereq += new_prereq
            fin_props = merge_two_dicts(fin_props, new_props)

    entity_def = entity['properties']
    fin_props = merge_two_dicts(fin_props, entity_def)
    fin_inputs += [enty_path]

    log.write('\tcurrent inputs %s \n'%(str(fin_inputs)))
    log.write('\tcurrent prerequisites %s \n'%(str(fin_prereq)))
    log.write('\tcurrent properties %s \n'%(str(fin_props)))

    #fin_prereq += scanJSONForAssetUUIDs(enty_path)
    return fin_inputs, fin_prereq, fin_props


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

    entity_inputs, entity_prereq, entity_def = process_entity(obj_path)

    log.write('final entity json output:\ninputs: %s\nprerequisites: %s\nprops: %s\n'%(str(entity_inputs), str(entity_prereq), str(entity_def)))

    includes = [obj_path]
    js_offsets = []
    js_bytes = []
    for key, value in entity_def.iteritems():
        if key in fbs_def_path_map:
            fbs_def_path = formatString(fbs_def_path_map[key], asset['buildparams'])
            comp_obj_path = os.path.join(asset['tmp_directory'], key+'.json')
        else:
            fbs_def_path = os.path.realpath(os.path.join(asset_base, key))
            comp_obj_path = os.path.join(asset['tmp_directory'], os.path.split(key)[1]+'.json')

        ii, s_bytes, _ = convertJsonFBSToBin(FLATC, value, fbs_def_path, comp_obj_path, tmp_dir, log)
        includes += ii

        js_offsets += [len(js_bytes)]
        for b in s_bytes:
            js_bytes += [b]


    final_template = {
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
    asset['assetmetadata']['inputs'] = list(set(includes+entity_inputs)) # list(set(x)) to make x unique
    asset['assetmetadata']['prerequisites'] = scanJSONStringForAssetUUIDs(json.dumps(entity_def, sort_keys=True))

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2, sort_keys=True))
