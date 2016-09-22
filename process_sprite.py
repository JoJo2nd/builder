

import sys
import json
from os.path import join, realpath, split
import zipfile
import base64
from PIL import Image
from subprocess import Popen, PIPE

log = None

def formatString(s, parameters):
    for k, p in parameters.iteritems():
        s = s.replace("%%(%s)"%(k), p)
    return s

if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)
    FLATC = join(asset['buildparams']['working_directory'], "flatc")
    tmp_dir = asset['tmp_directory']
    frame_tmp_dir = join(asset['tmp_directory'], 'frames')
    final_fbs_path = join(asset['tmp_directory'], 'sprite.json')
    sprite_zip_path = asset['processoptions']['input']
    sprite_folder = split(sprite_zip_path)[0]
    sprite_data_path = join(sprite_folder, 'meta.json')

    log = open(join(asset['tmp_directory'], 'log.txt'), 'wb')

    log.write("opening zipfile %s"%(sprite_zip_path))
    with zipfile.ZipFile(sprite_zip_path) as zf:
        log.write("...open\n")
        frames = [i for i in zf.infolist() if i.filename.startswith('frame_')]
        for f in frames:
            log.write("extracting frame %s to %s\n"%(f.filename, frame_tmp_dir))
            zf.extract(f, frame_tmp_dir)
            #im = Image.open(join(frame_tmp_dir, f.filename))
        log.write('loading sprite metadata %s\n'%(sprite_data_path))
        with open(sprite_data_path, 'rb') as f:
            sprite_data = json.loads(f.read())


    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2, sort_keys=True))
