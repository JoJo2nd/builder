

import sys
import json
from os.path import join, realpath, split, splitext
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
    TEXTUREC = join(asset['buildparams']['working_directory'], 'texturecRelease')
    FLATC = join(asset['buildparams']['working_directory'], "flatc")
    tmp_dir = asset['tmp_directory']
    frame_tmp_dir = join(asset['tmp_directory'], 'frames')
    fbs_def_path = join(asset['asset_directory'],'game/fbs/sprite.fbs')
    final_fbs_path = join(asset['tmp_directory'], 'sprite.json')
    final_atlas_path = join(asset['tmp_directory'], 'fullatlas_')
    sprite_zip_path = asset['processoptions']['input']
    sprite_folder = split(sprite_zip_path)[0]
    sprite_data_path = join(sprite_folder, 'meta.json')

    log = open(join(asset['tmp_directory'], 'log.txt'), 'wb')

    log.write("opening zipfile %s"%(sprite_zip_path))
    with zipfile.ZipFile(sprite_zip_path) as zf:
        log.write("...open\n")
        log.write('loading sprite metadata %s\n'%(sprite_data_path))
        with open(sprite_data_path, 'rb') as f:
            sprite_data = json.loads(f.read())
        frames = [i for i in zf.infolist() if i.filename.startswith('frame_')]
        frames_data = {}
        for f in frames:
            log.write("extracting frame %s to %s\n"%(f.filename, frame_tmp_dir))
            zf.extract(f, frame_tmp_dir)
            frame_number = int(splitext(f.filename)[0].lstrip('frame_'))
            log.write('adding frame %d\n'%(frame_number))
            frames_data[frame_number] = Image.open(join(frame_tmp_dir, f.filename))

        cell_w = frames_data[0].size[0]
        cell_h = frames_data[0].size[1]
        log.write(str(sprite_data))
        padding = sprite_data['layout']['padding'];
        padded_cell_w = cell_w + padding
        padded_cell_h = cell_h + padding
        cols = sprite_data['layout']['cellsX']
        rows = sprite_data['layout']['cellsY']
        log.write("\ncell size (%d, %d)\n"%(padded_cell_w, padded_cell_h))

        # TODO: align to 4?
        final_width = padded_cell_w*cols
        final_height = padded_cell_h*rows
        final_cell_count = (cols*rows)
        final_page_count = (len(frames_data)+(final_cell_count-1))/final_cell_count
        final_im = {}
        log.write('page count (%d /%d*%d) %d\n'%(len(frames_data), rows, cols, final_page_count))
        for f in range(0, final_page_count):
            final_im[f] = Image.new(frames_data[0].mode, (final_width, final_height))

        frames_data_array = []
        current_page = 0
        for f in range(0, len(frames_data)):
            current_page = f / final_cell_count
            pf = f % final_cell_count
            y = pf / cols
            x = pf % cols
            final_im[current_page].paste(frames_data[f], (x*padded_cell_w, y*padded_cell_h))
            frames_data_array += [{
                'u1': ((x*padded_cell_w)+padding)*(1.0/final_width), 'v1': ((y*padded_cell_h)+padding)*(1.0/final_height),
                'u2': (((x+1)*padded_cell_w)-padding)*(1.0/final_width), 'v2': (((y+1)*padded_cell_h)-padding)*(1.0/final_height),
                'page':current_page
            }]
            #TODO: build the frame array (with UVs etc)

        #process each page
        page = 0
        pages = []
        for f in final_im:
            input_png = final_atlas_path+str(page)+'.png'
            output_ktx = final_atlas_path+str(page)+'.ktx'
            final_im[f].save(input_png)
            page+=1
            cmdline = TEXTUREC
            cmdline += ' -f ' + input_png
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

            pages += [{
                'cellWidth': cell_w, 'cellHeight': cell_h, 'xCells': cols, 'yCells': rows,
                'data': js_bytes
            }]


        asset_json = {
            'pages': pages,
            'frames': frames_data_array,
            'anims': sprite_data['animations']
        }
        with open(final_fbs_path, 'wb') as f:
            f.write(json.dumps(asset_json, indent=2, sort_keys=True))

        cmdline = [FLATC, '-o', asset['tmp_directory'], '-b', fbs_def_path, final_fbs_path]
        log.write(str(cmdline)+'\n')
        p = Popen(cmdline, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        log.write(stdout+'\n')
        log.write(stderr+'\n')

        with open(splitext(final_fbs_path)[0]+'.bin', 'rb') as bin_file:
            encoded_data_string = base64.b64encode(bin_file.read())

        log.write('read outputted fbs binary')
        asset['buildoutput'] = {
            "data": encoded_data_string,
        }
        asset['assetmetadata']['inputs'] = [
            sprite_data_path, sprite_zip_path
        ]

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2, sort_keys=True))
