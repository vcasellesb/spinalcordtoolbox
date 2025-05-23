#!/usr/bin/env python
#
# Refresh `index.html` to reflect changes in `_assets/json`
#
# Copyright (c) 2024 Polytechnique Montreal <www.neuro.polymtl.ca>
# License: see the file LICENSE in the $SCT_DIR

"""
This script collects QC entries from the '_assets/json' folder, then writes them to the index.html file.

Usage:
  1. Modify/remove any of the .json files in `_assets/json`. (e.g. if you want to remove an entry before sharing)
  2. Re-run this script to update the `index.html` file.

Context: Ideally, we would load the QC entries dynamically from the '_assets/json' folder when opening the
         QC report. However, the QC report uses pure HTML + client-side (browser-based) JavaScript.
         Browser-based JavaScript is unable to access the filesystem automatically, which is why we use
         this "injecting" method to hardcode the QC entries as a JavaScript variable within the HTML file.

Note -- This script can be run two ways:
   1. When initially generating the QC report using SCT. (SCT will pass `path_qc` to the main function.)
   2. When a user wishes to update the QC report (i.e. they run the script from within the QC report after
      updating the .json files). In that case, `path_qc` will be inferred from the QC directory.
"""

import json
from pathlib import Path
import uuid


def main(path_qc):
    path_qc = Path(path_qc)

    path_json = path_qc / '_json'
    path_datasets_js = path_qc / 'js' / 'datasets.js'
    path_index_html = path_qc / 'index.html'

    # Collect all existing QC report entries
    json_data = []
    for path in sorted(path_json.glob('*.json')):
        with path.open() as file:
            json_data.append(json.load(file))

    report_uuid = uuid.uuid4()
    with open(path_datasets_js, mode='w', encoding="utf-8") as file_datasets_js:
        file_datasets_js.write(f"""
window.SCT_QC_UUID = '{report_uuid}';
window.SCT_QC_DATASETS = {json.dumps(json_data)};
""")

    return path_index_html


if __name__ == "__main__":
    main(path_qc=Path("..").resolve())
