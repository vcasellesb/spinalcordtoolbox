#!/usr/bin/env python
#
# Merge images. See details in function "merge_images".
#
# Copyright (c) 2014 Polytechnique Montreal <www.neuro.polymtl.ca>
# License: see the file LICENSE

# TODO: parameter "almost_zero" might case problem if merging data with very low values (e.g. MD from diffusion)

import sys
import os
from typing import Sequence
import textwrap

import numpy as np

from spinalcordtoolbox.image import Image
from spinalcordtoolbox.utils.shell import SCTArgumentParser, Metavar, display_viewer_syntax
from spinalcordtoolbox.utils.sys import init_sct, set_loglevel
from spinalcordtoolbox.utils.fs import tmp_create, rmtree
from spinalcordtoolbox.math import binarize

from spinalcordtoolbox.scripts import sct_apply_transfo


ALMOST_ZERO = 0.00000001


# PARSER
# ==========================================================================================
def get_parser():
    # Initialize the parser

    parser = SCTArgumentParser(
        description=(textwrap.dedent("""
            Merge multiple source images (`-i`) onto destination space (`-d`). (All images are warped to the destination space and then added together.)

            To deal with overlap during merging (e.g. multiple input images map to the same voxel regions in the destination space), the output voxels are divided by the sum of the partial volume values for each image.

            Specifically, the per-voxel calculation used is:
              `im_out = (im_1*pv_1 + im_2*pv_2 + ...) / (pv_1 + pv_2 + ...)`

            So this function acts like a weighted average operator, only in destination voxels that share multiple source voxels.
        """))  # noqa
    )

    mandatory = parser.mandatory_arggroup
    mandatory.add_argument(
        "-i",
        metavar=Metavar.file,
        nargs="+",
        help="Input images")
    mandatory.add_argument(
        "-d",
        metavar=Metavar.file,
        help="Destination image")
    mandatory.add_argument(
        "-w",
        nargs="+",
        metavar=Metavar.file,
        help="List of warping fields from input images to destination image")

    optional = parser.optional_arggroup
    optional.add_argument(
        "-x",
        metavar=Metavar.str,
        help="Interpolation for warping the input images to the destination image.",
        default='linear')
    optional.add_argument(
        "-o",
        metavar=Metavar.file,
        help="Output image",
        default='merged_images.nii.gz')

    # Arguments which implement shared functionality
    parser.add_common_args()
    parser.add_tempfile_args()

    return parser


def merge_images(list_fname_src, fname_dest, list_fname_warp, fname_out, interp, rm_tmp):
    """
    Merge multiple source images (-i) onto destination space (-d). (All images are warped to the destination
    space and then added together.)

    To deal with overlap during merging (e.g. multiple input images map to the same voxel regions in the
    destination space), the output voxels are divided by the sum of the partial volume values for each image.

    Specifically, the per-voxel calculation used is:
        im_out = (im_1*pv_1 + im_2*pv_2 + ...) / (pv_1 + pv_2 + ...)

    So this function acts like a weighted average operator, only in destination voxels that share multiple
    source voxels.

    Parameters
    ----------
    list_fname_src
    fname_dest
    list_fname_warp
    fname_out
    interp
    rm_tmp

    Returns
    -------

    """
    # create temporary folder
    path_tmp = tmp_create(basename="merge-images")

    # get dimensions of destination file
    nii_dest = Image(fname_dest)

    # initialize variables
    data = np.zeros([nii_dest.dim[0], nii_dest.dim[1], nii_dest.dim[2], len(list_fname_src)])
    partial_volume = np.zeros([nii_dest.dim[0], nii_dest.dim[1], nii_dest.dim[2], len(list_fname_src)])

    for i_file, fname_src in enumerate(list_fname_src):
        # apply transformation src --> dest
        fname_src_warped = os.path.join(path_tmp, f"src{i_file}_template.nii.gz")
        sct_apply_transfo.main(argv=[
            '-i', fname_src,
            '-d', fname_dest,
            '-w', list_fname_warp[i_file],
            '-x', interp,
            '-o', fname_src_warped,
            '-v', '0'])

        # create binary mask from input file by assigning one to all non-null voxels
        img = Image(fname_src)
        out = img.copy()
        out.data = binarize(out.data, ALMOST_ZERO)
        fname_src_bin = os.path.join(path_tmp, f"src{i_file}_native_bin.nii.gz")
        out.save(path=fname_src_bin)

        # apply transformation to binary mask to compute partial volume
        fname_src_pv = os.path.join(path_tmp, f"src{i_file}_template_partialVolume.nii.gz")
        sct_apply_transfo.main(argv=[
            '-i', fname_src_bin,
            '-d', fname_dest,
            '-w', list_fname_warp[i_file],
            '-x', interp,
            '-o', fname_src_pv,
            '-v', '0'])

        # open data
        data[:, :, :, i_file] = Image(fname_src_warped).data
        partial_volume[:, :, :, i_file] = Image(fname_src_pv).data

    # merge files using partial volume information (and convert nan resulting from division by zero to zeros)
    data_merge = np.divide(np.sum(data * partial_volume, axis=3), np.sum(partial_volume, axis=3))
    data_merge = np.nan_to_num(data_merge)

    # write result in file
    nii_dest.data = data_merge
    nii_dest.save(fname_out)

    # remove temporary folder
    if rm_tmp:
        rmtree(path_tmp)


# MAIN
# ==========================================================================================
def main(argv: Sequence[str]):
    parser = get_parser()
    arguments = parser.parse_args(argv)
    verbose = arguments.v
    set_loglevel(verbose=verbose, caller_module_name=__name__)

    # set param arguments ad inputted by user
    list_fname_src = arguments.i
    fname_dest = arguments.d
    list_fname_warp = arguments.w
    fname_out = arguments.o
    interp = arguments.x
    rm_tmp = arguments.r

    # check if list of input files and warping fields have same length
    if len(list_fname_src) != len(list_fname_warp):
        parser.error("lists of files are not of the same length")

    # merge src images to destination image
    merge_images(list_fname_src, fname_dest, list_fname_warp, fname_out, interp, rm_tmp)

    display_viewer_syntax([fname_dest, os.path.abspath(fname_out)], verbose=verbose)


if __name__ == "__main__":
    init_sct()
    main(sys.argv[1:])
