

import sys
import json
import os.path
import base64
from subprocess import Popen, PIPE

log = None

def formatString(s, parameters):
    for k, p in parameters.iteritems():
        s = s.replace("%%(%s)"%(k), p)
    return s

def convertJsonFBSToBin(IN_FLATC, in_value, in_fbs_def_path, json_obj_path):
    tmp_path = os.path.join(asset['tmp_directory'], os.path.splitext(json_obj_path)[0]+'.bin')

    with open(json_obj_path, 'wb') as f:
        f.write(json.dumps(in_value, indent=2, sort_keys=True))

    cmdline = IN_FLATC
    cmdline += ' -o ' + tmp_dir
    cmdline += ' -b ' + in_fbs_def_path
    cmdline += ' ' + json_obj_path
    log.write(cmdline+'\n')
    p = Popen(cmdline)
    p.wait()

    cmdline1 = cmdline
    cmdline = IN_FLATC
    cmdline += ' -M --cpp ' + in_fbs_def_path
    log.write(cmdline+'\n')
    p = Popen(cmdline, stdout=PIPE)
    includes_string = p.communicate()[0]

    includes = [obj_path, in_fbs_def_path]
    includes += [inc[0:-1].strip().strip('\\') for inc in includes_string.split('\n')[1:-1]]

    s_bytes = []
    with open(tmp_path, 'rb') as f:
        while 1:
            byte_s = f.read(1)
            if not byte_s:
                break
            s_bytes += [ord(byte_s[0])]

    return includes, s_bytes

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

        ii, s_bytes = convertJsonFBSToBin(FLATC, value, fbs_def_path, comp_obj_path)
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

    ii, s_bytes = convertJsonFBSToBin(FLATC, final_template, fbs_templ_def_path, final_tmp_path)
    includes += ii

    asset['buildoutput'] = {
        "data": base64.b64encode(str(s_bytes)),
    }
    #Update the input files
    asset['assetmetadata']['inputs'] = list(set(includes)) # list(set(x)) to make x unique

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2, sort_keys=True))
