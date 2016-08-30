import sys
import json
import os.path
import base64
from subprocess import Popen, PIPE
import argparse
import flatbuffers
import hart.render.resource.Profile
import hart.render.resource.ShaderResource
import hart.render.resource.ShaderCollection

def formatString(s, parameters):
    for k, p in parameters.iteritems():
        s = s.replace("%%(%s)"%(k), p)
    return s

def bytes_from_file(filename, chunksize=8192):
    with open(filename, "rb") as f:
        while True:
            b = f.read(1)
            if b != "":
                #for b in chunk:
                yield b
            else:
                break


if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    SHADERC = os.path.join(asset['buildparams']['working_directory'], 'shadercRelease')
    FLATC = os.path.join(asset['buildparams']['working_directory'], 'flatc')
    tmp_path = os.path.join(asset['tmp_directory'],'shader.data')
    cmd_path = os.path.join(asset['tmp_directory'],'cmdline.txt')
    clt_fbs = os.path.join(asset['asset_directory'],'hart/fbs/shader.fbs')
    fbs_js_tmp_path = os.path.join(asset['tmp_directory'],'shader.json')

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
        f.write(json.dumps(output, indent=2))

    cmdline = [FLATC, '-o', asset['tmp_directory'], '-b', clt_fbs, fbs_js_tmp_path]

    p = Popen(cmdline)
    p.wait()

    with open(os.path.splitext(fbs_js_tmp_path)[0]+'.bin', 'rb') as bin_file:
        encoded_data_string = base64.b64encode(bin_file.read())

##    builder = flatbuffers.Builder(0)
##
##    hart.render.resource.ShaderResource.ShaderResourceStartMemVector(builder, len(s_bytes))
##    for b in reversed(s_bytes[:-1]):
##        builder.PrependUint8(b)
##    s_mem = builder.EndVector(len(s_bytes))
##    hart.render.resource.ShaderResource.ShaderResourceStart(builder)
##    hart.render.resource.ShaderResource.ShaderResourceAddProfile(builder, hart.render.resource.Profile.Profile.Direct3D11)
##    hart.render.resource.ShaderResource.ShaderResourceAddMem(builder, s_mem)
##    shaderresource = hart.render.resource.ShaderResource.ShaderResourceEnd(builder)
##
##    hart.render.resource.ShaderCollection.ShaderCollectionStartSupportedProfilesVector(builder, 1)
##    builder.PrependUint16(hart.render.resource.Profile.Profile.Direct3D11)
##    profiles = builder.EndVector(1)
##
##    hart.render.resource.ShaderCollection.ShaderCollectionStartShaderArrayVector(builder, 1)
##    builder.PrependUOffsetTRelative(shaderresource)
##    shaders = builder.EndVector(1)
##
##    hart.render.resource.ShaderCollection.ShaderCollectionStart(builder)
##    hart.render.resource.ShaderCollection.ShaderCollectionAddSupportedProfiles(builder, profiles)
##    hart.render.resource.ShaderCollection.ShaderCollectionAddShaderArray(builder, shaders)
##    shadercollection = hart.render.resource.ShaderCollection.ShaderCollectionEnd(builder)
##
##    builder.Finish(shadercollection)
##    encoded_data_string = base64.b64encode(builder.Output())

    asset['buildoutput'] = {
        "data": encoded_data_string,
    }

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2))

