import sys
import json
import os.path
import base64

if __name__ == '__main__':
    with open(sys.argv[1]) as fin:
        asset = json.load(fin)

    with open(asset['assetmetadata']['inputs'][0], 'rb') as bin_file:
        encoded_data_string = base64.b64encode(bin_file.read())

    asset['buildoutput'] = {
        "data": encoded_data_string,
    }

    with open(asset['output_file'], 'wb') as f:
        f.write(json.dumps(asset, indent=2))

