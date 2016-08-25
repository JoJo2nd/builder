##
##
##
##
##
##
##
##

### JSON format for build config
## We define a few vars that can be inserted in to command lines here. They are
## asset_directory := The root folder that contains all .asset files. Normally the working directory of the script
## cache_directory := Where data between builds is stored
## output_directory := Where assets are written to
## tmp_directory := Somewhere to store data. Don't expect it to persist beyond building a single asset.
## {
##     "prebuild": [
##         "python update_and_generate_texture_assets.py %(asset_directory)"
##     ],
##     "processors": [
##         {
##             "proc": "python process_mesh.py -arg1 -arg2",
##             "defaultprocessoptions" : {
##                 "generatenormals" : true
##             },
##             version: 0.1,
##         },
##         {
##             "proc": "python process_texture.py",
##             "defaultprocessoptions" : {
##                 "compress" : true
##             },
##             version: 0.1,
##         }
##     ]
##    "postbuild": [
##         "python zip_assets.py %(output_directory)"
##     ],
## }
##
### JSON format for assets
## When building an asset this data is passed to the process on stdin. The build process
## generates buildoption and can optionally update any fields in the JSON (e.g. inputs). The updated JSON
## should be passed back on stdout.
## {
##     # UUID in the format below so python can quickly parse it.
##     "uuid": "{AA53D0BE-98A0-42DD-9500-88B375EDC136}",
##     # The process to run on this asset to build it
##     "type": "mesh"
##     # Friendly name for those aren't adept at reading 128bit numbers
##     "friendlyname": "Bunny Mesh",
##     # Relative file paths for files to check timestamps against.
##     "inputs": ["bunny.obj"],
##     # List of UUID's that must be loaded before this asset
##     "prerequisites": [
##          "{00000000-1234-5678-9000-000000000101}",
##          "{00000000-1234-5678-9000-000000000102}",
##     ],
##     # processoptions contains any asset specific parameters to pass to the process that handles this asset.
##     "processoptions": {
##         "meshoptions" : []
##     }
### JSON section generated when building an asset and returned to the builder to be cached
##    "buildoutput": {
##        "data": "Base64 string of asset binary data", # 
##        "warnings": ["Some helpful warning"], #
##        "errors": [] #Empty on success, any members in here will cause failure
##    }
## }
###

import argparse
import json
import os.path
import uuid
import time
import base64
from multiprocessing import Process, Pipe, Pool
from subprocess import Popen, PIPE
import shutil

parser = argparse.ArgumentParser(prog='builder',description='Script to convert data from source to binary')
parser.add_argument('-d','--directory', help='*.asset source directory. Recursive.')
parser.add_argument('-o','--output', help='binary output directory.')
parser.add_argument('--clean', help='Delete all cached build data before build.', action='store_true')

def process_asset(in_asset):
    # build and check the cache
    cache = {
        "asset": in_asset['assetmetadata'],
        "process": in_asset['process'],
        "buildconfig": in_asset['buildconfig'],
        "filestamps": [{"file":f, "stamp":os.path.getmtime(f)} for f in in_asset['assetmetadata']['inputs'] if os.path.isfile(f) ]
    }
    do_build = True

    # Update the cache so paths are relative to asset directory root
    # These need resetting before the build & before writing out to disk
    o_asset_inputs = cache['asset']['inputs']
    o_filestamps = cache['filestamps']
    c_asset_inputs = [os.path.relpath(file, in_asset['buildparams']['asset_directory']) for file in cache['asset']['inputs']]
    c_filestamps = [{'stamp':file['stamp'], 'file':os.path.relpath(file['file'], in_asset['buildparams']['asset_directory'])} for file in cache['filestamps']]

    cache['asset']['inputs'] = c_asset_inputs
    cache['filestamps'] = c_filestamps

    if os.path.isfile(in_asset['cache_file']) and os.path.isfile(in_asset['output_file']):
        with open(in_asset['cache_file']) as f:
            try:
                if cache == json.load(f):
                    do_build = False
            except:
                pass

    cache['asset']['inputs'] = o_asset_inputs
    cache['filestamps'] = o_filestamps

    # Build the resource if needed
    if do_build:
        #print "Building asset %s (%s)"%(in_asset['assetmetadata']['friendlyname'], in_asset['uuid'])
        with open(in_asset['input_file'], 'wb') as f:
            f.write(json.dumps(in_asset, indent=2))
        p = Popen(in_asset['cmdline'].split() + [in_asset['input_file']], stdin=PIPE, stdout=PIPE)
        returncode = p.wait()
        if returncode != 0:
            # Failed. remove the cache file to force rebuilds
            if os.path.isfile(in_asset['cache_file']):
                os.remove(in_asset['cache_file'])
            # return failed result
            return {"input": in_asset, "deploy": False, "failed": True}
        else:
            # write an updated cache
            cache['asset']['inputs'] = c_asset_inputs
            cache['filestamps'] = c_filestamps
            with open(in_asset['cache_file'], 'wb') as f:
                f.write(json.dumps(cache, indent=2))
            cache['asset']['inputs'] = o_asset_inputs
            cache['filestamps'] = o_filestamps
    else:
        #print "Reusing cached asset %s (%s)"%(in_asset['assetmetadata']['friendlyname'], in_asset['uuid'])
        pass

    # Read in the outputted json from the build process
    # outputJSON['buildoutput']['data'] has the Base64 encoded data we need.
    with open(in_asset['output_file']) as f:
        r_json = json.load(f)

    #For any inputs returned, fix them to be relative to .asset file
    asset_path = os.path.split(in_asset['assetpath'])[0]
    #print "Updating asset %s (%s) input paths"%(in_asset['assetmetadata']['friendlyname'], in_asset['uuid'])
    r_json['assetmetadata']['inputs'] = [os.path.relpath(f, asset_path) for f in r_json['assetmetadata']['inputs']]

    #print "Asset %s (%s) built"%(in_asset['assetmetadata']['friendlyname'], in_asset['uuid'])
    return {"input": in_asset, "result": r_json, "deploy": do_build}

def createDirectories(path):
    if not os.path.exists(path):
        os.makedirs(path)

def getAssetCachePath(uuid, cache_root):
    cp = os.path.join(cache_root, uuid.hex[30:32], uuid.hex[28:30])
    createDirectories(cp)
    return cp

def getAssetTmpPath(uuid, temp_root):
    tp = os.path.join(temp_root, uuid.hex[30:32], uuid.hex[28:30], uuid.hex)
    createDirectories(tp)
    return tp

def formatString(s, parameters):
    for k, p in parameters.iteritems():
        s = s.replace("%%(%s)"%(k), p)
    return s

def formatList(d, parameters):
    for v in d:
        print v
        if isinstance(v, dict):
            formatDict(v, parameters)
        elif isinstance(v, list):
            formatList(v, parameters)
        elif isinstance(v, basestring):
            v = formatString(v, parameters)

def formatDict(d, parameters):
    for k, v in d.iteritems():
        print v
        if isinstance(v, dict):
            formatDict(v, parameters)
        elif isinstance(v, list):
            formatList(v, parameters)
        elif isinstance(v, basestring):
            v = formatString(v, parameters)


def main():
    args = parser.parse_args()

    assets = []
    assets_jobs = []
    assets_dict = {}

    working_directory = os.path.realpath(os.getcwd())
    asset_directory = os.path.realpath(os.path.join(os.getcwd(), args.directory))
    output_directory = os.path.realpath(os.path.join(os.getcwd(), args.output))
    cache_directory = os.path.join(output_directory, ".working", ".cache")
    tmp_directory = os.path.join(output_directory, ".working", ".buildtmp")
    friendlyname_dict_file = os.path.realpath(os.path.join(output_directory, 'filelisting.json'))
    createDirectories(cache_directory)
    createDirectories(tmp_directory)
    createDirectories(output_directory)

    parameters = {
        "asset_directory": asset_directory,# := The root folder that contains all .asset files. Normally the working directory of the script
        "cache_directory": cache_directory,# := Where data between builds is stored
        "output_directory": output_directory,# := Where assets are written to
        "tmp_directory": tmp_directory,# := Somewhere to store data. Don't expect it to persist beyond building a single asset.
        "working_directory": working_directory, # := Where the script is run from, using for getting binaries
    }

    if args.clean == True:
        shutil.rmtree(cache_directory, ignore_errors=True)
        shutil.rmtree(tmp_directory, ignore_errors=True)

    with open('builderconfig.json') as f:
        config = json.loads(f.read())

    for prebuild in config['prebuild']:
        print "Running prebuild command", 
        print formatString(prebuild, parameters)+"...",
        p = Popen((formatString(prebuild, parameters)).split())
        p.wait()
        print "Done"

    for root, dirs, files in os.walk(args.directory):
        assets += [{'assetpath': os.path.realpath(os.path.join(root, x))} for x in files if os.path.splitext(x)[1] == ".asset"]

    FirendlyNames = {}

    for asset in assets:
        with open(asset['assetpath']) as f:
            asset['assetmetadata'] = json.loads(f.read())
            try:
                asset_uuid = uuid.UUID(asset['assetmetadata']['uuid'])
                fname = asset['assetmetadata']['friendlyname']
                final_fname = fname
                count = 1
                while final_fname in FirendlyNames:
                    final_fname = "%s_%02x"%(fname, count)
                    print "friendly name conflict. Changing", fname, "to", final_fname
                    count += 1
                FirendlyNames[final_fname] = {}
                FirendlyNames[final_fname]['filepath'] = [asset['assetmetadata']['uuid'].replace('}', '').replace('{', '').replace('-', '')+'.bin']
                if 'prerequisites' in asset['assetmetadata']:
                    FirendlyNames[final_fname]['prerequisites'] = [x.replace('}', '').replace('{', '').replace('-', '')+'.bin' for x in asset['assetmetadata']['prerequisites']]
                else:
                    FirendlyNames[final_fname]['prerequisites'] = []

                asset_uuid = uuid.UUID(asset['assetmetadata']['uuid'])
                asset['uuid'] = asset['assetmetadata']['uuid']
                asset['cmdline'] = config['processors'][asset['assetmetadata']['type']]['proc']
                asset['process'] = config['processors'][asset['assetmetadata']['type']]
                asset['buildconfig'] = config['global']
                asset['buildparams'] = parameters
                asset['processoptions'] = {}
                for k, v in asset['process']['defaultprocessoptions'].iteritems():
                    asset['processoptions'][k] = v
                for k, v in asset['assetmetadata']['processoptions'].iteritems():
                    asset['processoptions'][k] = v

                asset_root, _ = os.path.split(asset['assetpath'])
                asset['assetmetadata']['inputs'] = [os.path.realpath(os.path.join(asset_root, inp)) for inp in asset['assetmetadata']['inputs']]

                cache_root = getAssetCachePath(asset_uuid, cache_directory)
                uuid_hex_str = asset_uuid.hex

                asset['cache_directory'] = cache_root
                asset['asset_directory'] = asset_directory
                asset['cache_file'] = os.path.join(cache_root, uuid_hex_str + '.cache')
                asset['tmp_directory'] = getAssetTmpPath(asset_uuid, tmp_directory)
                asset['input_file'] = os.path.join(cache_root, uuid_hex_str + '.in.json')
                asset['output_file'] = os.path.join(cache_root, uuid_hex_str + '.bin')
                asset['final_dest'] = os.path.join(output_directory, uuid_hex_str + '.bin')
            except:
                print "failed to load asset", asset['assetpath']
                raise

        assets_dict[uuid.UUID(asset['uuid'])] = asset

    #Generate the friendly name listing
    with open(friendlyname_dict_file, 'wb') as f:
        f.write(json.dumps(FirendlyNames, indent=2))


    #
    p = Pool()
    for res in p.imap_unordered(process_asset, assets):
        # Output build results. Check for errors
        if 'failed' in res:
            print "Asset %s (%s) failed to build."%(res['input']['assetmetadata']['friendlyname'], res['input']['uuid'])
        else:
            j = res['result']
            #Update the asset metafile with any info returned by the build process
            if not (res['input']['assetmetadata'] == res['result']['assetmetadata']):
                with open(res['input']['assetpath'], 'wb') as f:
                    f.write(json.dumps(res['result']['assetmetadata'], indent=2))
            if res['deploy']:
                print "Deploy updated asset %s (%s)"%(res['result']['assetmetadata']['friendlyname'], res['result']['uuid'])
                with open(res['result']['final_dest'], 'wb') as f:
                    f.write(base64.b64decode(res['result']['buildoutput']['data']))

    for postbuild in config['postbuild']:
        print "Running postbuild command", formatString(postbuild, parameters)+"...",
        p = Popen((formatString(postbuild, parameters)).split())
        p.wait()
        print "Done"

if __name__ == '__main__':
    main()
