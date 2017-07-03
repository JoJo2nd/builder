

import sys
import json
from os.path import join, realpath, split, splitext
import zipfile
import base64
from PIL import Image
from gamecommon.utils import convertJsonFBSToBin, formatString, scanJSONStringForAssetUUIDs
from subprocess import Popen, PIPE

# .anim format
# # Comments!!
# # Like .obj format, prefix a line with the type of data 
# # AnimationName filepath 
# A Idle idle_.csv
# # Curve type, Linear or Catmull-Rom spline
# C Linear
# # list of frames x , y , end time as % of total anim ;
# # In the maths this can be a 3D curve where z is position along the 2D curve?
# P 0, 0, 0;
# P 16, 0, 100;
# # Walk cycle
# A WalkLeft walk_.csv
# # 
# C Linear
# #
# P 0, 0, 0;
# P -16, 0, 100;

# .csv format
# "Name","Transparent Color","Transparent Color(Hex)","Delay(1/60)","File Name","Width","Height"
# "Frame1","16777215","00FFFFFF","6","walk_0000.png","32","48"
# ...and repeat
#

log = None

def formatString(s, parameters):
    for k, p in parameters.iteritems():
        s = s.replace("%%(%s)"%(k), p)
    return s

if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    TEXTUREC = join(asset['buildparams']['working_directory'], 'texturecRelease')
    FLATC = join(asset['buildparams']['working_directory'], "flatc")
    tmp_dir = asset['tmp_directory']
    frame_tmp_dir = join(asset['tmp_directory'], 'frames')
    fbs_def_path = join(asset['asset_directory'],'game/fbs/sprite.fbs')
    final_fbs_path = join(asset['tmp_directory'], 'sprite.json')
    final_atlas_path = join(asset['tmp_directory'], 'fullatlas_')
    output_ktx = join(asset['tmp_directory'], 'tmp.ktx')
    sprite_path = asset['processoptions']['input']
    sprite_folder = split(sprite_path)[0]
    found_inputs = []

    log = open(join(asset['tmp_directory'], 'log.txt'), 'wb')

    total_control_points = 0
    total_anims = 0
    total_frames = 0
    asset_json = {
        'pages':[],
        'anims':[],
    }
    anim_json = None

    log.write("opening .sprite file %s\n"%(sprite_path))
    found_inputs += [sprite_path]
    with open(sprite_path, "rb") as f:
        for line in f.readlines():
            line = line.strip()
            if line[0] == '#':
                continue
            if line[0] == 'A':
                if not anim_json == None:
                    asset_json['anims'] += [anim_json]
                csv_path = join(sprite_folder, line.split()[2])
                anim_json = {
                    'animType':line.split()[1],
                    'frames':[],
                    'controlPoints':[]
                }
                log.write("opening .csv file %s\n"%(csv_path))
                found_inputs += [csv_path]
                with open(csv_path, 'rb') as csv_f:
                    for cline in csv_f.readlines()[1:]:
                        # "Name","Transparent Color","Transparent Color(Hex)","Delay(1/60)","File Name","Width","Height"
                        # "Frame1","16777215","00FFFFFF","6","walk_0000.png","32","48"
                        log.write(str(cline.split())+'\n')
                        params = cline.strip().split(',')
                        frame_js = {}
                        frame_js['length'] = int(params[3].strip('"'))
                        frame_js['page'] = total_frames
                        frame_js['width'] = int(params[5].strip('"'))
                        frame_js['height'] = int(params[6].strip('"'))
                        anim_json['frames'] += [frame_js]
                        total_frames += 1
                        tex_path = join(sprite_folder, params[4].strip('"'))
                        found_inputs += [tex_path]
                        cmdline = TEXTUREC
                        cmdline += ' -f ' + tex_path
                        cmdline += ' -o ' + output_ktx
                        cmdline += ' -t ' + 'RGBA8'
                        log.write(str(cmdline)+'\n')
            
                        p = Popen(cmdline, stdout=PIPE, stderr=PIPE)
                        stdout, stderr = p.communicate()
            
                        log.write(stdout+'\n')
                        log.write(stderr+'\n')    
            
                        s_bytes = []
                        with open(output_ktx, 'rb') as f:
                            while 1:
                                byte_s = f.read(1)
                                if not byte_s:
                                    break
                                s_bytes += [ord(byte_s[0])]
            
                        js_bytes = []
                        for b in s_bytes:
                            js_bytes += [b]
                        asset_json['pages'] += [{
                            'data':js_bytes
                        }]
            elif line[0] == 'C':
                pass
            elif line[0] == 'P':
                params = line.split()
                anim_json['controlPoints'] += [{
                    'x': float(params[1]), 
                    'y': float(params[2]),
                    'z': float(params[3])
                }]
                total_control_points += 1

    if not anim_json == None:
        asset_json['anims'] += [anim_json]

    asset_json['totalControlPoints'] = total_control_points
    asset_json['totalFrames'] = total_frames

#    with open(final_fbs_path, 'wb') as f:
#        f.write(json.dumps(asset_json, indent=2, sort_keys=True))
#
#    cmdline = [FLATC, '-o', asset['tmp_directory'], '-b', fbs_def_path, final_fbs_path]
#    log.write(str(cmdline)+'\n')
#    p = Popen(cmdline, stdout=PIPE, stderr=PIPE)
#    stdout, stderr = p.communicate()
#    log.write(stdout+'\n')
#    log.write(stderr+'\n')
#
#    with open(splitext(final_fbs_path)[0]+'.bin', 'rb') as bin_file:
#        encoded_data_string = base64.b64encode(bin_file.read())
    final_tmp_path = join(asset['tmp_directory'], 'final_template.json')
    ii, s_bytes, r_bytes = convertJsonFBSToBin(FLATC, asset_json, fbs_def_path, final_tmp_path, asset['tmp_directory'], log)

    log.write('read outputted fbs binary')
    asset['buildoutput'] = {
        "data": base64.b64encode(r_bytes),
    }
    asset['assetmetadata']['inputs'] = found_inputs+ii

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2, sort_keys=True))

