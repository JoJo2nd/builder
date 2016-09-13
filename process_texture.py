import sys
import json
import os.path
import base64
from subprocess import Popen, PIPE

def formatString(s, parameters):
    for k, p in parameters.iteritems():
        s = s.replace("%%(%s)"%(k), p)
    return s

if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    TEXTUREC = os.path.join(asset['buildparams']['working_directory'], 'texturecRelease')
    FLATC = os.path.join(asset['buildparams']['working_directory'], 'flatc')
    tmp_path = os.path.join(asset['tmp_directory'],'texc.data.ktx')
    cmd_path = os.path.join(asset['tmp_directory'],'log.txt')
    clt_fbs = os.path.join(asset['asset_directory'],'hart/fbs/texture.fbs')
    fbs_js_tmp_path = os.path.join(asset['tmp_directory'],'texture.json')

    with open(cmd_path, 'wb') as log:
        cmdline = TEXTUREC
        cmdline += ' -f ' + formatString(asset['processoptions']['input'], asset['buildparams'])
        cmdline += ' -o ' + tmp_path
        cmdline += ' -t ' + asset['processoptions']['format']
        if 'generatemips' in asset['processoptions'] and asset['processoptions']['generatemips'] == True:
            cmdline += ' -m '
        
        log.write(str(cmdline)+'\n')

        p = Popen(cmdline, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()

        log.write(stdout+'\n')
        log.write(stderr+'\n')    

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
            'data': js_bytes 
        }

        with open(fbs_js_tmp_path, 'wb') as f:
            f.write(json.dumps(output, indent=2))

        cmdline = [FLATC, '-o', asset['tmp_directory'], '-b', clt_fbs, fbs_js_tmp_path]
        log.write(str(cmdline)+'\n')
        p = Popen(cmdline, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        log.write(stdout+'\n')
        log.write(stderr+'\n')

        with open(os.path.splitext(fbs_js_tmp_path)[0]+'.bin', 'rb') as bin_file:
            encoded_data_string = base64.b64encode(bin_file.read())

        log.write('read outputted fbs binary')
        asset['buildoutput'] = {
            "data": encoded_data_string,
        }
        asset['assetmetadata']['inputs'] = [formatString(asset['processoptions']['input'], asset['buildparams'])]

        with open(asset['output_file'], 'wb') as f:
            f.write(json.dumps(asset, indent=2))

