#!/usr/bin/env python
#
# Resample data using nibabel
#
# Copyright (c) 2014 Polytechnique Montreal <www.neuro.polymtl.ca>
# License: see the file LICENSE

# TODO: add possiblity to resample to destination image

import sys
from typing import Sequence
import textwrap

from spinalcordtoolbox.utils.sys import init_sct, set_loglevel
from spinalcordtoolbox.utils.shell import Metavar, SCTArgumentParser
import spinalcordtoolbox.resampling


class Param:
    # The constructor
    def __init__(self):
        self.fname_data = ''
        self.fname_out = ''
        self.new_size = ''
        self.new_size_type = ''
        self.interpolation = 'linear'
        self.ref = None
        self.x_to_order = {'nn': 0, 'linear': 1, 'spline': 2}
        self.mode = 'reflect'  # How to fill the points outside the boundaries of the input, possible options: constant, nearest, reflect or wrap
        # constant put the superior edges to 0, wrap does something weird with the superior edges, nearest and reflect are fine
        self.file_suffix = '_resampled'  # output suffix
        self.verbose = 1


# initialize parameters
param = Param()


def get_parser():
    parser = SCTArgumentParser(
        description="Anisotropic resampling of 3D or 4D data."
    )

    mandatory = parser.mandatory_arggroup
    mandatory.add_argument(
        '-i',
        metavar=Metavar.file,
        help="Image to resample. Can be 3D or 4D. (Cannot be 2D) Example: `dwi.nii.gz`"
    )

    # TODO: Make these arguments implicitly mutually exclusive
    resample_types = parser.add_argument_group(
        "\nMETHOD TO SPECIFY NEW SIZE:\n"
        "Please choose only one of the 4 options"
    )
    resample_types.add_argument(
        '-f',
        metavar=Metavar.str,
        help=textwrap.dedent("""
            Resampling factor in each dimensions (x,y,z). Separate with `x`. Example: `0.5x0.5x1`

            For 2x upsampling, set to `2`. For 2x downsampling set to `0.5`
        """),
    )
    resample_types.add_argument(
        '-mm',
        metavar=Metavar.str,
        help=textwrap.dedent("""
            New resolution in mm. Separate dimension with `x`. Example: `0.1x0.1x5`

            Note: Resampling can only approximate a desired `mm` resolution, given the limitations of discrete voxel data arrays.
        """),
        # Context: https://github.com/spinalcordtoolbox/spinalcordtoolbox/issues/4077
    )
    resample_types.add_argument(
        '-vox',
        metavar=Metavar.str,
        help="Resampling size in number of voxels in each dimensions (x,y,z). Separate with `x`."
    )
    resample_types.add_argument(
        '-ref',
        metavar=Metavar.file,
        help="Reference image to resample input image to. The voxel dimensions and affine of the reference image will "
             "be used."
    )

    optional = parser.optional_arggroup
    optional.add_argument(
        '-x',
        choices=['nn', 'linear', 'spline'],
        default='linear',
        help="Interpolation method."
    )
    optional.add_argument(
        '-o',
        metavar=Metavar.file,
        help="Output file name. Example: `dwi_resampled.nii.gz`"
    )

    # Arguments which implement shared functionality
    parser.add_common_args()

    return parser


def main(argv: Sequence[str]):
    parser = get_parser()
    arguments = parser.parse_args(argv)
    verbose = arguments.v
    set_loglevel(verbose=verbose, caller_module_name=__name__)
    param.verbose = verbose

    param.fname_data = arguments.i
    arg = 0
    if arguments.f is not None:
        param.new_size = arguments.f
        param.new_size_type = 'factor'
        arg += 1
    if arguments.mm is not None:
        param.new_size = arguments.mm
        param.new_size_type = 'mm'
        arg += 1
    if arguments.vox is not None:
        param.new_size = arguments.vox
        param.new_size_type = 'vox'
        arg += 1
    if arguments.ref is not None:
        param.ref = arguments.ref
        arg += 1

    if arg == 0:
        parser.error("You need to specify one of those four arguments: '-f', '-mm', '-vox' or '-ref'.")
    elif arg > 1:
        parser.error("You need to specify ONLY one of those four arguments: '-f', '-mm', '-vox' or '-ref'.")

    if arguments.o is not None:
        param.fname_out = arguments.o
    if arguments.x is not None:
        if len(arguments.x) == 1:
            param.interpolation = int(arguments.x)
        else:
            param.interpolation = arguments.x

    spinalcordtoolbox.resampling.resample_file(param.fname_data, param.fname_out, param.new_size, param.new_size_type,
                                               param.interpolation, param.verbose, fname_ref=param.ref)


if __name__ == "__main__":
    init_sct()
    main(sys.argv[1:])
