"""Convert one Bruker TSeries folder of multipage .ome.tif files to one .nii per channel.

Standalone port of brukerbridge's tiff_to_nii (ClandininLab/brukerbridge,
brukerbridge/tiff_to_nii.py) for when the bridge did not produce .nii files.
The output matches brukerbridge's exactly: <TSeries>_channel_<N>.nii next to the
xml, uint16, axes (x, y, z, t), identity affine, Nifti1. Only numpy, nibabel and
Pillow are needed, so it runs on Sherlock without the brukerbridge package.

Usage:  python3 tiff_to_nii.py /path/to/TSeries-XXXX/TSeries-XXXX.xml
Existing .nii outputs are never overwritten.
"""
import os
import sys
import time
from xml.etree import ElementTree as ET

import numpy as np
import nibabel as nib
from PIL import Image


def read_multipage(path):
    """Return a (pages, rows, cols) uint16 array from a multipage tif."""
    img = Image.open(path)
    pages = []
    i = 0
    while True:
        try:
            img.seek(i)
        except EOFError:
            break
        pages.append(np.array(img, dtype=np.uint16))
        i += 1
    return np.stack(pages, axis=0)


def main(xml_file):
    xml_file = os.path.abspath(xml_file)
    data_dir = os.path.dirname(xml_file)
    stem = xml_file[:-4]
    print('Converting tiffs to nii in {}'.format(data_dir), flush=True)

    if not os.path.exists(stem + '.companion.ome'):
        sys.exit('No .companion.ome next to the xml: these are not multipage tifs, '
                 'which this script does not handle. Use brukerbridge instead.')

    root = ET.parse(xml_file).getroot()
    if root.tag != 'PVScan':
        sys.exit('{} is not a Bruker scan xml (root tag {}).'.format(xml_file, root.tag))
    sequences = root.findall('Sequence')
    seq_type = sequences[0].get('type')
    if seq_type == 'TSeries Timed Element':
        sys.exit('Single-plane time series: not handled here, use brukerbridge.')
    if sequences[0].get('bidirectionalZ') == 'True':
        # brukerbridge does not flip multipage volumes either; flag it so we check by eye
        print('WARNING: bidirectionalZ is True; odd volumes are NOT flipped (same as brukerbridge).')

    num_t = len(sequences)
    z_counts = [len(s.findall('Frame')) for s in sequences]
    num_z = z_counts[0]
    if z_counts[-1] != num_z:
        print('Last volume has {} slices instead of {} (scan aborted): dropping it.'.format(
            z_counts[-1], num_z))
        num_t -= 1
    num_channels = len(sequences[0].findall('Frame')[0].findall('File'))

    first = read_multipage(os.path.join(
        data_dir, sequences[0].findall('Frame')[0].findall('File')[0].get('filename')))
    num_y, num_x = first.shape[-2], first.shape[-1]
    gb = num_x * num_y * num_z * num_t * 2 / 1e9
    print('channels={} t={} z={} y={} x={}  (~{:.1f} GB per channel)'.format(
        num_channels, num_t, num_z, num_y, num_x, gb), flush=True)

    for ch in range(num_channels):
        save_name = '{}_channel_{}.nii'.format(stem, ch + 1)
        if os.path.exists(save_name):
            print('{} already exists, skipping.'.format(save_name))
            continue
        # brukerbridge builds (t, z, y, x) then reorders to (x, y, z, t); fill that directly
        out = np.zeros((num_x, num_y, num_z, num_t), dtype=np.uint16)
        t0 = time.time()
        for t in range(num_t):
            fname = sequences[t].findall('Frame')[0].findall('File')[ch].get('filename')
            vol = read_multipage(os.path.join(data_dir, fname))  # (z, y, x)
            if vol.shape != (num_z, num_y, num_x):
                sys.exit('{} has shape {}, expected {}.'.format(
                    fname, vol.shape, (num_z, num_y, num_x)))
            out[:, :, :, t] = vol.transpose(2, 1, 0)
            if t % 10 == 0 or t == num_t - 1:
                print('  ch{} volume {}/{} ({:.0f} s)'.format(
                    ch + 1, t + 1, num_t, time.time() - t0), flush=True)
        tmp_name = save_name[:-4] + '_partial.nii'
        nib.Nifti1Image(out, np.eye(4)).to_filename(tmp_name)
        os.rename(tmp_name, save_name)
        del out
        print('Saved {}'.format(save_name), flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
