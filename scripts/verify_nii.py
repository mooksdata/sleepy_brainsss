"""Check a Bruker .nii conversion against the original .ome.tif files. Read-only.

For one TSeries, picks random (volume, slice) pairs in each <TSeries>_channel_<N>.nii,
looks up in the xml which tif file and page that slice was recorded in, reads that page
straight from the tif, and checks the .nii slice is identical pixel for pixel.

The slice is matched by its recorded z position, not by slice order, so this check is
independent of how the converter ordered slices (bidirectional scans included). It works
on any converter's output (brukerbridge, the Sherlock bridge, or tiff_to_nii.py), as long
as the .nii uses the lab's layout: axes (x, y, z, t), slice 1 = first slice of volume 1.

Usage:  python3 verify_nii.py /path/to/TSeries-XXXX/TSeries-XXXX.xml [samples_per_channel]
Prints one summary line per channel; exits with code 1 if anything does not match.
Nothing is written or changed.
"""
import os
import random
import sys
from xml.etree import ElementTree as ET

import numpy as np
import nibabel as nib
from PIL import Image


def frame_z(frame):
    values = []
    for s in frame.iter('SubindexedValues'):
        if s.get('index') == 'ZAxis':
            values += [x.get('value') for x in s.findall('SubindexedValue')]
    try:
        return float(values[-1])
    except (IndexError, TypeError, ValueError):
        return None


def read_page(path, page):
    img = Image.open(path)
    img.seek(page - 1)
    return np.array(img, dtype=np.uint16)


def find_by_z(zs, target):
    """Index of the frame recorded at z=target (within 0.5 um), or None."""
    best = None
    for k, v in enumerate(zs):
        if v is not None and abs(v - target) <= 0.5:
            if best is None or abs(v - target) < abs(zs[best] - target):
                best = k
    return best


def locate(zs, ref_z, z):
    """Which frame of a volume holds .nii slice z. Returns (frame index or None, how).
    Matched by recorded z. If slice z has no z in volume 1 or in this volume, use its
    neighbours: the frame lying exactly between the frames recorded at the z of
    slice z-1 and slice z+1 is slice z."""
    if ref_z[z] is not None:
        k = find_by_z(zs, ref_z[z])
        if k is not None:
            return k, 'z'
    if 0 < z < len(ref_z) - 1 and ref_z[z - 1] is not None and ref_z[z + 1] is not None:
        a, b = find_by_z(zs, ref_z[z - 1]), find_by_z(zs, ref_z[z + 1])
        if a is not None and b is not None and abs(a - b) == 2:
            return (a + b) // 2, 'neighbours'
    return None, None


def main(xml_file, n_samples):
    xml_file = os.path.abspath(xml_file)
    data_dir = os.path.dirname(xml_file)
    stem = xml_file[:-4]
    sequences = ET.parse(xml_file).getroot().findall('Sequence')
    num_channels = len(sequences[0].findall('Frame')[0].findall('File'))

    # z position of each slice of volume 1 defines what slice index z means in the .nii.
    # Bruker leaves z out of a few frames (one per volume on this rig); see locate().
    ref_z = [frame_z(f) for f in sequences[0].findall('Frame')]
    if sum(z is not None for z in ref_z) < len(ref_z) / 2:
        sys.exit('Fewer than half the slices of volume 1 have a recorded z: '
                 'cannot match slices independently.')
    missing_ref = [i + 1 for i, z in enumerate(ref_z) if z is None]
    print('{}: {} volumes in xml, {} slices per volume, bidirectionalZ={}; '
          'volume 1 slices without z: {}'.format(
              os.path.basename(xml_file), len(sequences), len(ref_z),
              sequences[0].get('bidirectionalZ'), missing_ref or 'none'), flush=True)

    all_ok = True
    rng = random.Random(0)
    for ch in range(num_channels):
        nii_path = '{}_channel_{}.nii'.format(stem, ch + 1)
        if not os.path.exists(nii_path):
            print('channel {}: MISSING {}'.format(ch + 1, nii_path))
            all_ok = False
            continue
        img = nib.load(nii_path)  # reads slices on demand; the file is never written
        nx, ny, nz, nt = img.shape
        problems = []
        if nz != len(ref_z):
            problems.append('nii has {} slices, xml has {}'.format(nz, len(ref_z)))
        if nt > len(sequences):
            problems.append('nii has {} volumes, xml only {}'.format(nt, len(sequences)))
        if img.get_data_dtype() != np.uint16:
            problems.append('dtype {} (expected uint16)'.format(img.get_data_dtype()))
        if problems:
            print('channel {}: SHAPE PROBLEM: {}'.format(ch + 1, '; '.join(problems)))
            all_ok = False
            continue

        # always include the first and last volume and slice, plus random ones
        pairs = {(0, 0), (nt - 1, nz - 1), (0, nz - 1), (nt - 1, 0)}
        if nt > 1:
            pairs |= {(1, 0), (1, nz - 1)}  # second volume: the reversed one if bidirectional
        for i in missing_ref[:2]:            # make sure the no-z slices get tested too
            pairs |= {(0, i - 1), (nt - 1, i - 1)}
            if nt > 1:
                pairs.add((1, i - 1))
        while len(pairs) < min(n_samples, nt * nz):
            pairs.add((rng.randrange(nt), rng.randrange(nz)))

        n_ok, n_by_neighbours, bad = 0, 0, []
        for t, z in sorted(pairs):
            frames = sequences[t].findall('Frame')
            zs = [frame_z(f) for f in frames]
            k, how = locate(zs, ref_z, z)
            if k is None:
                bad.append('volume {} slice {}: could not find which recorded frame it is'.format(
                    t + 1, z + 1))
                continue
            if how == 'neighbours':
                n_by_neighbours += 1
            f = frames[k].findall('File')[ch]
            tif = read_page(os.path.join(data_dir, f.get('filename')), int(f.get('page')))
            nii_slice = np.asarray(img.dataobj[:, :, z, t])
            if tif.T.shape == nii_slice.shape and np.array_equal(tif.T, nii_slice):
                n_ok += 1
            else:
                bad.append('volume {} slice {}: differs from {} page {}'.format(
                    t + 1, z + 1, f.get('filename'), f.get('page')))
        status = 'OK' if not bad else 'MISMATCH'
        print('channel {}: {}  {}/{} sampled slices identical to the tifs  '
              '({} located via neighbours; nii shape {})'.format(
                  ch + 1, status, n_ok, len(pairs), n_by_neighbours, img.shape), flush=True)
        for line in bad[:10]:
            print('    ' + line)
        all_ok = all_ok and not bad

    print('RESULT: {}'.format('ALL MATCH' if all_ok else 'PROBLEMS FOUND'))
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) == 3 else 40)
