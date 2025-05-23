"""
Functions processing segmentation data

Copyright (c) 2019 Polytechnique Montreal <www.neuro.polymtl.ca>
License: see the file LICENSE
"""

import math
import platform
import numpy as np
from skimage import measure, transform
import logging

from spinalcordtoolbox.image import Image
from spinalcordtoolbox.aggregate_slicewise import Metric
from spinalcordtoolbox.centerline.core import get_centerline
from spinalcordtoolbox.resampling import resample_nib
from spinalcordtoolbox.utils.shell import parse_num_list_inv
from spinalcordtoolbox.utils.sys import sct_progress_bar

# NB: We use a threshold to check if an array is empty, instead of checking if it's exactly 0. This is because
# resampling can change 0 -> ~0 (e.g. 1e-16). See: https://github.com/spinalcordtoolbox/spinalcordtoolbox/issues/3402
NEAR_ZERO_THRESHOLD = 1e-6


def compute_shape(segmentation, angle_correction=True, centerline_path=None, param_centerline=None,
                  verbose=1, remove_temp_files=1):
    """
    Compute morphometric measures of the spinal cord in the transverse (axial) plane from the segmentation.
    The segmentation could be binary or weighted for partial volume [0,1].

    :param segmentation: input segmentation. Could be either an Image or a file name.
    :param angle_correction:
    :param centerline_path: path to image file to be used as a centerline for computing angle correction.
    :param param_centerline: see centerline.core.ParamCenterline()
    :param verbose:
    :param remove_temp_files: int: Whether to remove temporary files. 0 = no, 1 = yes.
    :return metrics: Dict of class Metric(). If a metric cannot be calculated, its value will be nan.
    :return fit_results: class centerline.core.FitResults()
    """
    # List of properties to output (in the right order)
    property_list = ['area',
                     'angle_AP',
                     'angle_RL',
                     'diameter_AP',
                     'diameter_RL',
                     'eccentricity',
                     'orientation',
                     'solidity',
                     'length'
                     ]

    im_seg = Image(segmentation).change_orientation('RPI')
    # Getting image dimensions. x, y and z respectively correspond to RL, PA and IS.
    nx, ny, nz, nt, px, py, pz, pt = im_seg.dim
    pr = min([px, py])
    # Resample to isotropic resolution in the axial plane. Use the minimum pixel dimension as target dimension.
    im_segr = resample_nib(im_seg, new_size=[pr, pr, pz], new_size_type='mm', interpolation='linear')

    # Update dimensions from resampled image.
    nx, ny, nz, nt, px, py, pz, pt = im_segr.dim

    # Extract min and max index in Z direction
    data_seg = im_segr.data
    X, Y, Z = (data_seg > NEAR_ZERO_THRESHOLD).nonzero()
    min_z_index, max_z_index = min(Z), max(Z)

    # Initialize dictionary of property_list, with 1d array of nan (default value if no property for a given slice).
    shape_properties = {key: np.full(nz, np.nan, dtype=np.double) for key in property_list}

    fit_results = None

    if angle_correction:
        # allow the centerline image to be bypassed (in case `im_seg` is irregularly shaped, e.g. GM/WM)
        if centerline_path:
            im_centerline = Image(centerline_path).change_orientation('RPI')
            im_centerline_r = resample_nib(im_centerline, new_size=[pr, pr, pz], new_size_type='mm',
                                           interpolation='linear')
        else:
            im_centerline_r = im_segr
        # compute the spinal cord centerline based on the spinal cord segmentation
        _, arr_ctl, arr_ctl_der, fit_results = get_centerline(im_centerline_r, param=param_centerline, verbose=verbose,
                                                              remove_temp_files=remove_temp_files)
        # the third column of `arr_ctl` contains the integer slice numbers, and the first two
        # columns of `arr_ctl_der` contain the x and y components of the centerline derivative
        deriv = {int(z_ref): arr_ctl_der[:2, index] for index, z_ref in enumerate(arr_ctl[2])}

        # check for slices in the input mask not covered by the centerline
        missing_slices = sorted(set(range(min_z_index, max_z_index + 1)).difference(deriv.keys()))
        if missing_slices:
            raise ValueError(
                "The provided angle correction centerline does not cover slice(s) "
                f"{parse_num_list_inv(missing_slices)} of the input mask. Please "
                "supply a more extensive '-angle-corr-centerline', or disable angle "
                "correction ('-angle-corr 0')."
            ) from None

    # Loop across z and compute shape analysis
    for iz in sct_progress_bar(range(min_z_index, max_z_index + 1), unit='iter', unit_scale=False, desc="Compute shape analysis",
                               ncols=80):
        # Extract 2D patch
        current_patch = im_segr.data[:, :, iz]
        if angle_correction:
            # Extract tangent vector to the centerline (i.e. its derivative)
            tangent_vect = np.array([deriv[iz][0] * px, deriv[iz][1] * py, pz])
            # Compute the angle about AP axis between the centerline and the normal vector to the slice
            angle_AP_rad = math.atan2(tangent_vect[0], tangent_vect[2])
            # Compute the angle about RL axis between the centerline and the normal vector to the slice
            angle_RL_rad = math.atan2(tangent_vect[1], tangent_vect[2])
            # Apply affine transformation to account for the angle between the centerline and the normal to the patch
            tform = transform.AffineTransform(scale=(np.cos(angle_RL_rad), np.cos(angle_AP_rad)))
            # Convert to float64, to avoid problems in image indexation causing issues when applying transform.warp
            current_patch = current_patch.astype(np.float64)
            # TODO: make sure pattern does not go extend outside of image border
            current_patch_scaled = transform.warp(current_patch,
                                                  tform.inverse,
                                                  output_shape=current_patch.shape,
                                                  order=1,
                                                  )
        else:
            current_patch_scaled = current_patch
            angle_AP_rad, angle_RL_rad = 0.0, 0.0
        # compute shape properties on 2D patch
        shape_property = _properties2d(current_patch_scaled, [px, py])
        if shape_property is not None:
            # Add custom fields
            shape_property['angle_AP'] = angle_AP_rad * 180.0 / math.pi
            shape_property['angle_RL'] = angle_RL_rad * 180.0 / math.pi
            shape_property['length'] = pz / (np.cos(angle_AP_rad) * np.cos(angle_RL_rad))
            # Loop across properties and assign values for function output
            for property_name in property_list:
                shape_properties[property_name][iz] = shape_property[property_name]
        else:
            logging.warning('\nNo properties for slice: {}'.format(iz))

        """ DEBUG
        from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
        from matplotlib.figure import Figure
        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.imshow(current_patch_scaled)
        ax.grid()
        ax.set_xlabel('y')
        ax.set_ylabel('x')
        fig.savefig('tmp_fig.png')
        """
    metrics = {}
    for key, value in shape_properties.items():
        # Making sure all entries added to metrics have results
        value = np.array(value)
        if value.size > 0:
            metrics[key] = Metric(data=value, label=key)

    return metrics, fit_results


def _properties2d(image, dim):
    """
    Compute shape property of the input 2D image. Accounts for partial volume information.
    :param image: 2D input image in uint8 or float (weighted for partial volume) that has a single object.
    :param dim: [px, py]: Physical dimension of the image (in mm). X,Y respectively correspond to AP,RL.
    :return:
    """
    upscale = 5  # upscale factor for resampling the input image (for better precision)
    pad = 3  # padding used for cropping
    # Check if slice is empty
    if np.all(image < NEAR_ZERO_THRESHOLD):
        logging.debug('The slice is empty.')
        return None
    # Normalize between 0 and 1 (also check if slice is empty)
    image_norm = (image - image.min()) / (image.max() - image.min())
    # Convert to float64
    image_norm = image_norm.astype(np.float64)
    # Binarize image using threshold at 0. Necessary input for measure.regionprops
    image_bin = np.array(image_norm > 0.5, dtype='uint8')
    # Get all closed binary regions from the image (normally there is only one)
    regions = measure.regionprops(image_bin, intensity_image=image_norm)
    # Check number of regions
    if len(regions) > 1:
        logging.debug('There is more than one object on this slice.')
        return None
    region = regions[0]
    # Get bounding box of the object
    minx, miny, maxx, maxy = region.bbox
    # Use those bounding box coordinates to crop the image (for faster processing)
    image_crop = image_norm[np.clip(minx-pad, 0, image_bin.shape[0]): np.clip(maxx+pad, 0, image_bin.shape[0]),
                            np.clip(miny-pad, 0, image_bin.shape[1]): np.clip(maxy+pad, 0, image_bin.shape[1])]
    # Oversample image to reach sufficient precision when computing shape metrics on the binary mask
    image_crop_r = transform.pyramid_expand(image_crop, upscale=upscale, sigma=None, order=1)
    # Binarize image using threshold at 0. Necessary input for measure.regionprops
    image_crop_r_bin = np.array(image_crop_r > 0.5, dtype='uint8')
    # Get all closed binary regions from the image (normally there is only one)
    regions = measure.regionprops(image_crop_r_bin, intensity_image=image_crop_r)
    region = regions[0]
    # Compute area with weighted segmentation and adjust area with physical pixel size
    area = np.sum(image_crop_r) * dim[0] * dim[1] / upscale ** 2
    # Compute ellipse orientation, modulo pi, in deg, and between [0, 90]
    orientation = fix_orientation(region.orientation)
    # Find RL and AP diameter based on major/minor axes and cord orientation=
    [diameter_AP, diameter_RL] = \
        _find_AP_and_RL_diameter(region.major_axis_length, region.minor_axis_length, orientation,
                                 [i / upscale for i in dim])
    # TODO: compute major_axis_length/minor_axis_length by summing weighted voxels along axis
    # Deal with https://github.com/spinalcordtoolbox/spinalcordtoolbox/issues/2307
    if any(x in platform.platform() for x in ['Darwin-15', 'Darwin-16']):
        solidity = np.nan
    else:
        solidity = region.solidity
    # Fill up dictionary
    properties = {
        'area': area,
        'diameter_AP': diameter_AP,
        'diameter_RL': diameter_RL,
        'centroid': region.centroid,
        'eccentricity': region.eccentricity,
        'orientation': orientation,
        'solidity': solidity,  # convexity measure
    }

    return properties


def fix_orientation(orientation):
    """Re-map orientation from skimage.regionprops from [-pi/2,pi/2] to [0,90] and rotate by 90deg because image axis
    are inverted"""
    orientation_new = orientation * 180.0 / math.pi
    if 360 <= abs(orientation_new) <= 540:
        orientation_new = 540 - abs(orientation_new)
    if 180 <= abs(orientation_new) <= 360:
        orientation_new = 360 - abs(orientation_new)
    if 90 <= abs(orientation_new) <= 180:
        orientation_new = 180 - abs(orientation_new)
    return abs(orientation_new)


def _find_AP_and_RL_diameter(major_axis, minor_axis, orientation, dim):
    """
    This script checks the orientation of the and assigns the major/minor axis to the appropriate dimension, right-
    left (RL) or antero-posterior (AP). It also multiplies by the pixel size in mm.
    :param major_axis: major ellipse axis length calculated by regionprops
    :param minor_axis: minor ellipse axis length calculated by regionprops
    :param orientation: orientation in degree. Ranges between [0, 90]
    :param dim: pixel size in mm.
    :return: diameter_AP, diameter_RL
    """
    if 0 <= orientation < 45.0:
        diameter_AP = minor_axis
        diameter_RL = major_axis
    else:
        diameter_AP = major_axis
        diameter_RL = minor_axis
    # Adjust with pixel size
    diameter_AP *= dim[0]
    diameter_RL *= dim[1]
    return diameter_AP, diameter_RL
