

import sys
import json
import os
from os.path import join, realpath, split, splitext
import zipfile
import base64
import re
from PIL import Image
from gamecommon.utils import convertJsonFBSToBin, formatString, scanJSONStringForAssetUUIDs
from subprocess import Popen, PIPE
from struct import unpack_from, calcsize

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

# TODO: add palette class with __hash__, __eq__ & __ne__ methods (NB: use built in hash function?)
# 

def formatString(s, parameters):
    for k, p in parameters.iteritems():
        s = s.replace("%%(%s)"%(k), p)
    return s

def getImageBBox(image):
    l = image.width+1
    r = -1
    t = image.height+1
    b = -1
    for y in range(image.height):
        for x in range(image.width):
            if image.getpixel((x,y))[3] > 0:
                l = min(l, x)
                r = max(r, x)
                t = min(t, y)
                b = max(b, y)
    return (l, (image.height-t), r+1, (image.height-b)-1)

def readSpriteFile(filebuf, palettes, full_pal):
    filebytes = bytearray(filebuf.read())
    filesize = os.fstat(filebuf.fileno()).st_size
    data_ofs = 0
    palette_idx = 0
    sprite = {
        'palettes':[],
        'frames':[]
    }
    header = unpack_from('=cccHHH', filebytes, data_ofs)
    data_ofs += calcsize('=cccHHH')
    if header[0] != 'S' or header[1] != 'P' or header[2] != 'R':
        raise ValueError('Unexpected file format. Expected .SPR')
    sprite['frameCount'] = header[3]
    sprite['width'] = header[4]
    sprite['height'] = header[5]
    frame_size = header[4]*header[5]
    try:
        t,r,a,n,s,p,P = unpack_from('=ccccccB', filebytes, filesize-7)
        sprite['transparent'] = P
    except:
        sprite['transparent'] = -1
    sprite['layers'] = []
    current_layer = {
        'order': 0,
        'type': 'Unknown',
        'frames': []
    }
    for f in range(sprite['frameCount']):
        frame = {}
        frame['delay'] = int(round(unpack_from('=H', filebytes, data_ofs)[0] / 10))
        data_ofs += calcsize('=H')
        pal = []
        for p in range(256):
            rgb = unpack_from('=BBB', filebytes, data_ofs)
            data_ofs += calcsize('=BBB')
            pal += [{'r':rgb[0], 'g':rgb[1], 'b':rgb[2]}]
        pal_str = str(pal)
        if not pal_str in palettes:
            palette_idx = len(palettes)
            palettes[pal_str] = palette_idx
            full_pal += [{'transparent':sprite['transparent'], 'pal':pal}]
        frame['palette'] = palettes[pal_str]
        frame['data'] = []
        for b in range(frame_size):
            frame['data'] += [unpack_from('=B', filebytes, data_ofs)[0]]
            data_ofs += calcsize('=B')
        current_layer['frames'] += [frame]
    sprite['layers'] += [current_layer]

    return sprite

def readSplitLayerSpriteFile(filepath, palettes, full_pal):
    # Read a collection fo files with the file name format [filepath w/o ext]-[layername]-[layerorder]
    # and merge these into a single sprite image to process
    file_path_root, file_name = split(filepath)
    file_path_base, file_path_ext = splitext(file_name)

    log.write("Reading multi-layer sprite file. Searching for '")
    log.write("%s\-(Char|Gun)\-\d+\.spr'\n"%(file_path_base))

    sprite_files = []
    for root, dirs, files in os.walk(file_path_root):
        sprite_files += [os.path.realpath(os.path.join(root, x)) for x in files if re.search("%s\-(Char|Gun)\-(\d+)\.spr"%(file_path_base), x)]

    log.write("Found Layer sprite files %s\n"%(str(sprite_files)))

    all_inputs = []
    final_sprite = None
    for sprite in sprite_files:
        with open(sprite, 'rb') as f:
            log.write("Opened %s\n"%(sprite))
            all_inputs += [sprite]
            match = re.search("-(Char|Gun)-(\d+)\.spr", split(sprite)[1])
            sprite_layer = readSpriteFile(f, palettes, full_pal)
            sprite_layer['layers'][0]['order'] = int(match.group(2))
            sprite_layer['layers'][0]['type'] = match.group(1)
            if final_sprite == None:
                final_sprite = sprite_layer
                log.write("initial layer set\n%s\n"%(str(final_sprite['layers'])))
            else:
                final_sprite['layers'] += sprite_layer['layers']
                log.write("layer add\n%s\n"%(str(final_sprite['layers'])))

    log.write("layer sprite read finished\n")
    return final_sprite, all_inputs


def spriteFrameBBox(sprite, frame):
    transparent_px = sprite['transparent']
    frame_px = frame['data']
    sw = sprite['width']
    sh = sprite['height'] 
    l = sprite['width']+1
    r = -1
    t = sprite['height']+1
    b = -1
    for y in range(sh):
        for x in range(sw):
            if frame_px[y*sw+x] != transparent_px:
                l = min(l, x)
                r = max(r, x)
                t = min(t, y)
                b = max(b, y)
    return (l, (sh-t), r+1, (sh-b)-1)

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
    total_events = 0
    total_anims = 0
    total_frames = 0
    total_pages = 0
    asset_json = {
        'pages':[],
        'anims':[],
        'palettes':[]
    }
    anim_json = None
    frame_id = {}
    frame_bbox = {}
    palettes = {}

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
                flipx = False
                cp_anim_precent = 0;
                anim_json = {
                    'animType':line.split()[1],
                    'flipx':False,
                    'curveType':'Linear',
                    'layers':[],
                    'controlPoints':[],
                    'events':[]
                }

                if 'canInterrupt' in line.split():
                    anim_json['canInterrupt'] = True
                if 'alwaysInterrupts' in line.split():
                    anim_json['alwaysInterrupts'] = True

                if 'flipx' in line.split():
                    anim_json['flipx'] = True
                    anim_json['flipSource']=line.split()[2]
                elif splitext(csv_path)[1] == '.csv':
                    log.write("opening .csv file %s\n"%(csv_path))
                    found_inputs += [csv_path]
                    with open(csv_path, 'rb') as csv_f:
                        layer = {
                            'order': 0,
                            'type': 'Unknown',
                            'frames': []
                        }
                        for cline in csv_f.readlines()[1:]:
                            # "Name","Transparent Color","Transparent Color(Hex)","Delay(1/60)","File Name","Width","Height"
                            # "Frame1","16777215","00FFFFFF","6","walk_0000.png","32","48"
                            log.write(str(cline.split())+'\n')
                            params = cline.strip().split(',')
                            tex_path = join(sprite_folder, params[4].strip('"'))
                            frame_js = {}
                            frame_js['length'] = int(params[3].strip('"'))
                            frame_js['page'] = total_pages
                            frame_id[tex_path] = total_pages
                            with Image.open(tex_path) as image:
                                bbox = getImageBBox(image)#image.getbbox()
                                frame_bbox[tex_path] = bbox
                                frame_js['left'] = bbox[0]
                                frame_js['top'] = bbox[1]
                                frame_js['right'] = bbox[2]
                                frame_js['bottom'] = bbox[3]
                            total_pages += 1
                            frame_js['width'] = int(params[5].strip('"'))
                            frame_js['height'] = int(params[6].strip('"'))
                            layer['frames'] += [frame_js]
                            total_frames += 1
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
                                'type':'FullColour',
                                'data':js_bytes
                            }]
                        anim_json['layers'] = layer
                elif splitext(csv_path)[1] == '.spr':
                    log.write("opening .spr file %s\n"%(csv_path))
                    if not os.path.exists(csv_path):
                        sprite_data, all_inputs = readSplitLayerSpriteFile(csv_path, palettes, asset_json['palettes'])
                        found_inputs += all_inputs
                    else:
                        found_inputs += [csv_path]
                        sprite_data = readSpriteFile(open(csv_path, 'rb'), palettes, asset_json['palettes'])
                    frame_len = 0
                    for sprite_layer in sprite_data['layers']:
                        log.write(str(sprite_layer))
                        layer = {
                            'order': sprite_layer['order'],
                            'type': sprite_layer['type'],
                            'frames': []
                        }
                        assert frame_len == 0 or len(sprite_layer['frames']) == frame_len, "Frame count across all layers MUST be the same"
                        frame_len = len(sprite_layer['frames'])
                        for f in sprite_layer['frames']:
                            frame_js = {}
                            frame_js['length'] = f['delay']
                            frame_js['width'] = sprite_data['width']
                            frame_js['height'] = sprite_data['height']
                            # TODO: tight bounds
                            bbox = spriteFrameBBox(sprite_data, f)
                            frame_js['left'] = bbox[0]
                            frame_js['top'] = bbox[1]
                            frame_js['right'] = bbox[2]
                            frame_js['bottom'] = bbox[3]
                            # frame_js['left'] = 0
                            # frame_js['top'] = sprite_data['height']
                            # frame_js['right'] = sprite_data['width']
                            # frame_js['bottom'] = 0 
                            frame_js['page'] = total_pages
                            asset_json['pages'] += [{
                                'type':'Palette',
                                'width': sprite_data['width'],
                                'height': sprite_data['height'],
                                'palette': f['palette'],
                                'data':f['data']
                            }]
                            total_pages += 1
                            total_frames += 1
                            layer['frames'] += [frame_js]
                        anim_json['layers'] += [layer]
                else:
                    raise ValueError("Unknown file type %s"%(csv_path))
            elif line[0] == 'C':
                line_type = line.split()[1]
                anim_json['curveType'] = line_type
            elif line[0] == 'P':
                params = line.split()
                anim_json['controlPoints'] += [{
                    'x': float(params[1]), 
                    'y': float(params[2]),
                    'z': float(params[3])/100
                }]
                cp_anim_precent += (float(params[3])-cp_anim_precent)
                total_control_points += 1
            elif line[0] == 'E':
                params = line.split()
                anim_json['events'] += [{
                    'type':params[1],
                    'time':float(params[2])/100
                }]
                total_events += 1

    if not anim_json == None:
        asset_json['anims'] += [anim_json]

    asset_json['totalControlPoints'] = total_control_points
    asset_json['totalFrames'] = total_frames
    asset_json['totalEvents'] = total_events

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

