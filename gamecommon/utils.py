#
# utils
#

import sys
import json
import os.path
import uuid
import struct
import re
from subprocess import Popen, PIPE

def swap32(i):
    return struct.unpack("<I", struct.pack(">I", i))[0]

def formatString(s, parameters):
    for k, p in parameters.iteritems():
        s = s.replace("%%(%s)"%(k), p)
    return s

def convertJsonFBSToBin(IN_FLATC, in_value, in_fbs_def_path, json_obj_path, in_tmp_dir, in_log):
    tmp_path = os.path.join(in_tmp_dir, os.path.splitext(json_obj_path)[0]+'.bin')

    with open(json_obj_path, 'wb') as f:
        f.write(json.dumps(in_value, indent=2, sort_keys=True))

    cmdline = [IN_FLATC]
    cmdline += ['-o'] + [in_tmp_dir]
    cmdline += ['-b'] + [in_fbs_def_path]
    cmdline += [json_obj_path]
    in_log.write(str(cmdline) +'\n')
    p = Popen(cmdline, stdout=PIPE, stderr=PIPE)
    stdout, stderr = p.communicate()
    if not p.returncode == 0:
        print(stdout+'\n')
        raise ValueError('flatc compiler returned an error:'+stdout)
    in_log.write(stdout+'\n')
    in_log.write(stderr+'\n')    

    cmdline1 = cmdline
    cmdline = [IN_FLATC]
    cmdline += ['-M'] + ['--cpp'] + [in_fbs_def_path]
    in_log.write(str(cmdline) +'\n')
    p = Popen(cmdline, stdout=PIPE)
    includes_string = p.communicate()[0]
    in_log.write(includes_string+'\n')

    if not p.returncode == 0:
        print(includes_string+'\n')
        raise ValueError('flatc compiler returned an error:'+includes_string)

    includes = [in_fbs_def_path]
    includes += [inc[0:-1].strip().strip('\\') for inc in includes_string.split('\n')[1:-1]]

    s_bytes = []
    with open(tmp_path, 'rb') as f:
        while 1:
            byte_s = f.read(1)
            if not byte_s:
                break
            s_bytes += [ord(byte_s[0])]

    with open(tmp_path, 'rb') as f:
        raw_bytes = f.read()

    return includes, s_bytes, raw_bytes

def getAssetUUID(asset_path):
    with open(asset_path, 'rb') as f:
        asset_json = json.loads(f.read())
    asset_uuid = uuid.UUID(asset_json['uuid'])
    b = bytearray()
    b.extend(asset_uuid.bytes)
    return {
        'highword3': ((b[15]<<24) | (b[14]<<16) | (b[13]<<8) | (b[12])), 
        'highword2': ((b[11]<<24) | (b[10]<<16) | (b[ 9]<<8) | (b[ 8])), 
        'highword1': ((b[ 7]<<24) | (b[ 6]<<16) | (b[ 5]<<8) | (b[ 4])), 
        'lowword'  : ((b[ 3]<<24) | (b[ 2]<<16) | (b[ 1]<<8) | (b[ 0]))
    }, asset_json['uuid']

def getAssetUUIDFromString(asset_uuid_str):
    asset_uuid = uuid.UUID(asset_uuid_str)
    b = bytearray()
    b.extend(asset_uuid.bytes)
    return {
        'highword3': ((b[15]<<24) | (b[14]<<16) | (b[13]<<8) | (b[12])), 
        'highword2': ((b[11]<<24) | (b[10]<<16) | (b[ 9]<<8) | (b[ 8])), 
        'highword1': ((b[ 7]<<24) | (b[ 6]<<16) | (b[ 5]<<8) | (b[ 4])), 
        'lowword'  : ((b[ 3]<<24) | (b[ 2]<<16) | (b[ 1]<<8) | (b[ 0]))
    }

def buildStrFromUUIDFromNumbers(hw1, hw2, hw3, lw):
    return str(uuid.UUID("%08x%08x%08x%08x"%(swap32(lw), swap32(hw1), swap32(hw2), swap32(hw3))))

def bytes_from_file(filename, chunksize=8192):
    with open(filename, "rb") as f:
        while True:
            b = f.read(1)
            if b != "":
                #for b in chunk:
                yield b
            else:
                break

def scanJSONStringForAssetUUIDs(json_str):
    prerequisites = []
    for r in re.finditer('\"(highword\d|lowword)\"\s*\:\s*(\d+)\s*\,\s*\"(highword\d|lowword)\"\s*\:\s*(\d+)\s*\,\s*\"(highword\d|lowword)\"\s*\:\s*(\d+)\s*\,\s*\"(highword\d|lowword)\"\s*\:\s*(\d+)', json_str):
        uuidstuff = {r.group(1):r.group(2), r.group(3):r.group(4), r.group(5):r.group(6), r.group(7):r.group(8)}
        uuid_str = buildStrFromUUIDFromNumbers(int(uuidstuff['highword1']), int(uuidstuff['highword2']), int(uuidstuff['highword3']), int(uuidstuff['lowword']))
        prerequisites += [uuid_str]
    return list(set(prerequisites))

def scanJSONForAssetUUIDs(json_path):
    prerequisites = []
    with open(json_path, 'rb') as f:
        return scanJSONStringForAssetUUIDs(f.read())
        json_str = f.read()
    return []
#        for r in re.finditer('\"(highword\d|lowword)\"\s*\:\s*(\d+)\s*\,\s*\"(highword\d|lowword)\"\s*\:\s*(\d+)\s*\,\s*\"(highword\d|lowword)\"\s*\:\s*(\d+)\s*\,\s*\"(highword\d|lowword)\"\s*\:\s*(\d+)', json_str):
#            uuidstuff = {r.group(1):r.group(2), r.group(3):r.group(4), r.group(5):r.group(6), r.group(7):r.group(8)}
#            uuid_str = buildStrFromUUIDFromNumbers(int(uuidstuff['highword1']), int(uuidstuff['highword2']), int(uuidstuff['highword3']), int(uuidstuff['lowword']))
#            prerequisites += [uuid_str]
#    return list(set(prerequisites))
