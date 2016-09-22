##
## Update asset prerequisites
## Walk asset directory and update easy to fixup asset prerequisites
##

import argparse
import sys
import json
import os
from os.path import splitext, join, realpath
import base64
import uuid
from subprocess import Popen, PIPE

parser = argparse.ArgumentParser(prog='generate asset prerequisites for material & material setup assets',description='')
parser.add_argument('-d','--directory', help='*.fbs source directory. Recursive.')

def fbs_uuid_to_hex_str(u):
    #u['highword3']: ((b[15]<<24) | (b[14]<<16) | (b[13]<<8) | (b[12])), 
    #u['highword2']: ((b[11]<<24) | (b[10]<<16) | (b[ 9]<<8) | (b[ 8])), 
    #u['highword1']: ((b[ 7]<<24) | (b[ 6]<<16) | (b[ 5]<<8) | (b[ 4])), 
    #u['lowword'  ]: ((b[ 3]<<24) | (b[ 2]<<16) | (b[ 1]<<8) | (b[ 0]))
    b = '{'
    b += '%02x'%((u['lowword'  ] & 0x000000FF));
    b += '%02x'%((u['lowword'  ] & 0x0000FF00) >> 8);
    b += '%02x'%((u['lowword'  ] & 0x00FF0000) >> 16);
    b += '%02x'%((u['lowword'  ] & 0xFF000000) >> 24);
    b += '-'
    b += '%02x'%((u['highword1'] & 0x000000FF));
    b += '%02x'%((u['highword1'] & 0x0000FF00) >> 8);
    b += '-'
    b += '%02x'%((u['highword1'] & 0x00FF0000) >> 16);
    b += '%02x'%((u['highword1'] & 0xFF000000) >> 24);
    b += '-'
    b += '%02x'%((u['highword2'] & 0x000000FF));
    b += '%02x'%((u['highword2'] & 0x0000FF00) >> 8);
    b += '-'
    b += '%02x'%((u['highword2'] & 0x00FF0000) >> 16);
    b += '%02x'%((u['highword2'] & 0xFF000000) >> 24);
    b += '%02x'%((u['highword3'] & 0x000000FF));
    b += '%02x'%((u['highword3'] & 0x0000FF00) >> 8);
    b += '%02x'%((u['highword3'] & 0x00FF0000) >> 16);
    b += '%02x'%((u['highword3'] & 0xFF000000) >> 24);
    b += '}'
    return b

uuid_properties = [
    ['player', 'test_uuid'],
    ['player', 'inner', 'test_uuid'],
    ['player', 'inner', 'another_test_uuid'],
]

def parseEntityPrerequisites(entity_props):
    prerequisites = []
    for links in uuid_properties:
        found = True
        d = entity_props
        for p in links:
            if p in d:
                d = d[p]
            else:
                found = False
        if found:
            prerequisites += [fbs_uuid_to_hex_str(d)]

    return list(set(prerequisites))#list(set(x)) to make x unique

def main():
    args = parser.parse_args()

    for root, dirs, files in os.walk(args.directory):
        for file in [f for f in files if (splitext(f)[1] == '.asset')]:
            update=False
            with open(realpath(join(root, file)), 'rb') as fin:
                asset = json.load(fin)
            if asset['type'] == 'material':
                with open(realpath(join(root, asset['processoptions']['input']))) as f:
                    obj_json = json.load(f)
                prerequisites = []
                for t in obj_json['techniques']:
                    for p in t['passes']:
                        prerequisites += [fbs_uuid_to_hex_str(p['vertex'])]
                        prerequisites += [fbs_uuid_to_hex_str(p['pixel'])]
                asset['prerequisites'] = prerequisites
                update = True
            elif asset['type'] == 'materialsetup':
                with open(realpath(join(root, asset['processoptions']['input']))) as f:
                    obj_json = json.load(f)
                prerequisites = [fbs_uuid_to_hex_str(obj_json['material'])]
                asset['prerequisites'] = prerequisites
                update = True
            elif asset['type'] == 'entity':
                with open(realpath(join(root, asset['processoptions']['input']))) as f:
                    obj_json = json.load(f)
                prerequisites = [fbs_uuid_to_hex_str(obj_json['entityTemplate'])]
                prerequisites += parseEntityPrerequisites(obj_json['properties'])
                asset['prerequisites'] = prerequisites
                update = True
            elif asset['type'] == 'entitytemplate':
                with open(realpath(join(root, asset['processoptions']['input']))) as f:
                    obj_json = json.load(f)
                prerequisites = parseEntityPrerequisites(obj_json)
                asset['prerequisites'] = prerequisites
                update = True
            # Update the asset meta data
            if update:
                with open(realpath(join(root, file)), 'wb') as fin:
                    fin.write(json.dumps(asset, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()