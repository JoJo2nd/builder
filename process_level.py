#
# process_level
#

'''

Plan for levels.
 * Split each layer into 32x32 blocks. Generate static 32x32 tileset vertex buffer to render (? requires loading tile set). Flag blocks with dynamic/animated tiles (? again, requires loading tile set)
 * Build a Quad-tree of objects with 32x32 being the lowest level. Any objects spanning a boundary lives in the parent.
 * Match each layer to an enum (via layer name)
 * Build collision polys and inject into Quad-tree
 * Look into using Kd tree instead of Quad-tree
 * Load and store UUID for tileset asset (add as prereq)
 * Load and store UUIDs for entity assets (add as prereq, store as list so level knows which entities it owns as more than one level can be loaded.) <- Game objects are loaded this way (NPCs, items, shops, menus(?), player(?))

'''

#
# process tileset
#

import sys
import json
from os.path import join, realpath, split, splitext
import base64
import xmltodict
from gamecommon.utils import convertJsonFBSToBin, formatString, getAssetUUID, getAssetUUIDFromString
from subprocess import Popen, PIPE

log = None

if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    #TEXTUREC = join(asset['buildparams']['working_directory'], 'texturecRelease')
    FLATC = join(asset['buildparams']['working_directory'], "flatc")
    tmp_dir = asset['tmp_directory']
    fbs_def_path = join(asset['asset_directory'],'game/fbs/level.fbs')
    final_fbs_path = join(asset['tmp_directory'], 'level.json')
    level_path = asset['processoptions']['input']
    prerequisites = asset['assetmetadata']['prerequisites']
    other_includes = [level_path]

    log = open(join(asset['tmp_directory'], 'log.txt'), 'wb')

    log.write('open levle %s\n'%(level_path))
    with open(level_path, 'rb') as f:
        level = xmltodict.parse(f.read())

    lvl_collision_objects = []
    level_json = {
        'tilesets': [],
        'layers': [],
        'collisionprims' : [],
        'entities' : []
    }

    for key, value in level['map'].iteritems():
        log.write('iter map key:%s value:%s\n'%(key, value))
        if key == 'tileset':
            tilesets = value
            if not isinstance(value, list):
                tilesets = [value] # make sure tileset is an list
            log.write('parsing tilesets\n')
            for tileset in tilesets:
                tileset_json = {
                    'tilewidth':int(tileset['@tilewidth']),
                    'tileheight':int(tileset['@tileheight']),
                    'tilecount':int(tileset['@tilecount']),
                    'tilecolumns':int(tileset['@columns']),
                    'spacing':int(tileset['@spacing']) if '@spacing' in tileset else 0,
                    'margin':int(tileset['@margin']) if '@margin' in tileset else 0,
                    'firstgid':int(tileset['@firstgid']) if '@firstgid' in tileset else 0,
                    'tiles':[],
                    'animations':[]
                }
                for ts_key, ts_value in tileset.iteritems():
                    log.write('tileset iter key: %s\n'%(ts_key))
                    if ts_key == 'image':
                        log.write('parse image section\n')
                        input_png = realpath(join(split(level_path)[0], ts_value['@source']))
                        other_includes += [input_png]
                        tileset_json['imageasset'], new_prereq = getAssetUUID(splitext(input_png)[0]+'.asset')
                        log.write('Found prerequisite tileset image %s as asset %s\n'%(input_png, splitext(input_png)[0]+'.asset'))
                        prerequisites += [new_prereq]
                    elif ts_key == 'tile':
                        log.write('parse tile section\n')
                        for tile in ts_value:
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
                level_json['tilesets'] += [tileset_json]
        elif key == 'layer':
            layers = value
            if not isinstance(value, list):
                layers = [value] # make sure layers is an list
            for layer in layers:
                layer_json = {
                    'name':layer['@name'],
                    'width':int(layer['@width']),
                    'height':int(layer['@height']),
                    'tiles':[]
                }
                for l_key, l_value in layer.iteritems():
                    tiles = []
                    if l_key == 'data':
                        #log.write(str(l_value)+'\n')
                        for line in l_value['#text'].splitlines():
                            tiles += [int(v) for v in line.split(',') if len(v) > 0]
                            #for v in line.split(','):
                            #    log.write(v+',')
                            #    tiles += [int(v)]
                            #log.write('\n')
                    layer_json['tiles'] = tiles
                level_json['layers'] += [layer_json]
        elif key == 'objectgroup':
            log.write('parse object group\n')
            objectgroups = value
            if not isinstance(value, list):
                objectgroups = [value]
            for objectgroup in objectgroups:
                objects = objectgroup['object']
                if not isinstance(objects, list):
                    objects = [objects]
                if objectgroup['@name'] == 'collision':
                    for obj in objects:
                        collision_prim_json = {
                            'x': int(obj['@x']), 'y': int(obj['@y']),
                            'points': []
                        }
                        x_origin=int(obj['@x'])
                        y_origin=int(obj['@y'])
                        log.write('collision poly points %s'%(str(obj['polygon']['@points'].split())))
                        for p in obj['polygon']['@points'].split():
                            collision_prim_json['points'] += [{ 'x': int(p.split(',')[0])+x_origin, 'y':int(p.split(',')[1])+y_origin }]
                        level_json['collisionprims'] += [collision_prim_json]
                else:
                    #every other layer, only for entities currently
                    for obj in objects:
                        if '@type' in obj and obj['@type'] == 'Entity':
                            props = obj['properties']['property']
                            if not isinstance(props, list):
                                props = [props]
                            for p in props:
                                if '@name' in p and p['@name'] == 'EntityUUID':
                                    prerequisites += [p['@value']]
                                    level_json['entities'] += [{'levelid':int(obj['@id']), 'assetuuid':getAssetUUIDFromString(p['@value'])}]

    #log.write(json.dumps(level_json, indent=2, sort_keys=True))

    includes, js_byes, raw_bytes = convertJsonFBSToBin(FLATC, level_json, fbs_def_path, final_fbs_path, asset['tmp_directory'], log)
    asset['buildoutput'] = {
        "data": base64.b64encode(raw_bytes),
    }
    #Update the input files
    asset['assetmetadata']['inputs'] = list(set(includes+other_includes)) # list(set(x)) to make x unique
    asset['assetmetadata']['prerequisites'] = list(set(prerequisites))

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2, sort_keys=True))
