#
# process tileset
#

import sys
import json
from os.path import join, realpath, split, splitext
import base64
import xmltodict
from gamecommon.utils import convertJsonFBSToBin
from subprocess import Popen, PIPE

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
    fbs_def_path = join(asset['asset_directory'],'game/fbs/tileset.fbs')
    final_fbs_path = join(asset['tmp_directory'], 'tileset.json')
    out_img_path = join(asset['tmp_directory'], 'tileset.ktx')
    tileset_path = asset['processoptions']['input']

    log = open(join(asset['tmp_directory'], 'log.txt'), 'wb')

    log.write('open tileset %s\n'%(tileset_path))
    with open(tileset_path, 'rb') as f:
        tileset = xmltodict.parse(f.read())

    log.write(str(tileset)+'\n')

    tileset_json = {
        'tilewidth':int(tileset['tileset']['@tilewidth']),
        'tileheight':int(tileset['tileset']['@tileheight']),
        'tilecount':int(tileset['tileset']['@tilecount']),
        'tilecolumns':int(tileset['tileset']['@columns']),
        'tiles':[],
        'animations':[]
    }
    other_includes = [tileset_path]
    for key, value in tileset['tileset'].iteritems():
        if key == 'image':
            input_png = realpath(join(split(tileset_path)[0], value['@source']))
            output_ktx = out_img_path
            cmdline = [TEXTUREC]
            cmdline += ['-f'] + [input_png]
            cmdline += ['-o'] + [output_ktx]
            cmdline += ['-t'] + ['RGBA8']

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

            other_includes += [input_png]
            tileset_json['imagedata'] = js_bytes
        elif key == 'tile':
            for tile in value:
                tile_json = {
                    'id':int(tile['@id']),
                    'transparent':False,
                    'animated':False
                }
                for tile_key, tile_value in tile.iteritems():
                    if tile_key == 'properties':
                        for prop_key, prop_value in tile_value.iteritems():
                            if prop_key == 'property':
                                if prop_value['@name'] == 'transparent':
                                    tile_json['transparent'] = True if prop_value['@value'] == 'true' else False

                    if tile_key == 'animation':
                        tile_json['animated'] = True;
                        animation_json = []
                        for prop_key, prop_value in tile_value.iteritems():
                            if prop_key == 'frame':
                                for frame in prop_value:
                                    frame_json = {
                                        'id':int(frame['@tileid']),
                                        'len':int(frame['@duration'])
                                    }
                                    animation_json += [frame_json]
                        tileset_json['animations'] += [{'frames':animation_json}]
                tileset_json['tiles'] += [tile_json]


    #log.write(json.dumps(tileset_json, indent=2, sort_keys=True))

    includes, js_byes, raw_bytes = convertJsonFBSToBin(FLATC, tileset_json, fbs_def_path, final_fbs_path, asset['tmp_directory'], log)
    asset['buildoutput'] = {
        "data": base64.b64encode(raw_bytes),
    }
    #Update the input files
    asset['assetmetadata']['inputs'] = list(set(includes+other_includes)) # list(set(x)) to make x unique

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2, sort_keys=True))

