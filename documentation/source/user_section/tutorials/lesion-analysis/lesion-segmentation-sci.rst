Lesion segmentation in spinal cord injury (SCI)
###############################################

SCT provides a deep learning model called ``SCIseg`` for segmenting lesions in spinal cord injury (SCI) patients.
The model is available in SCT v6.2 and higher via ``sct_deepseg -task seg_sc_lesion_t2w_sci``. In SCT v6.4, the model was updated to ``SCIsegV2``, the command remains the same. In SCT v7.0, the command was changed to ``sct_deepseg lesion_sci_t2``.

The model was trained on raw T2-weighted images of SCI patients comprising traumatic (acute preoperative, intermediate, chronic) and non-traumatic (ischemic SCI and degenerative cervical myelopathy, DCM) SCI lesions.

The data included images with heterogeneous resolutions (axial/sagittal/isotropic) and scanner strengths (1T/1.5T/3T).

Given an input image, the model segments **both** the lesion and the spinal cord.

.. figure:: https://raw.githubusercontent.com/spinalcordtoolbox/doc-figures/master/lesion-analysis/sciseg.png
  :align: center
  :figwidth: 60%

Run the following command to segment the lesion using ``SCIseg`` from the input image:

.. code:: sh

   sct_deepseg lesion_sci_t2 -i t2.nii.gz -qc ~/qc_singleSubj

:Input arguments:
   - ``lesion_sci_t2`` : Task to perform. In our case, we use the ``SCIseg`` model via the ``lesion_sci_t2`` task
   - ``-i`` : Input T2w image with fake lesion
   - ``-qc`` : Directory for Quality Control reporting. QC reports allow us to evaluate the segmentation slice-by-slice

:Output files/folders:
   - ``t2_sc_seg.nii.gz`` : 3D binary mask of the segmented spinal cord
   - ``t2_lesion_seg.nii.gz`` : 3D binary mask of the segmented lesion
   - ``t2_lesion_seg.json`` : JSON file containing details about the segmentation model


Details:

* SCIsegV1: `Enamundram, N.K., Valošek, J., et al. Radiol. Artif. Intell. (2024) <https://doi.org/10.1148/ryai.240005>`_
* SCIsegV2: `Enamundram, N.K., Valošek, J., et al. Appl. Med. Artif. Intell. (2025) <https://doi.org/10.1007/978-3-031-82007-6_19>`_
