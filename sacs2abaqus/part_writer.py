import os
import json

from sacs2abaqus import iges
from .helpers import OrderJoints
from .sacs_cards import SacsStructure


def write_iges(stru: SacsStructure, filename: str):
    # Only write out the plate elements, wires will be passed in the intermediate file
    writer = iges.Iges()
    for plate in stru.plates.values():
        j1 = stru.joints[plate.jointA]
        j2 = stru.joints[plate.jointB]
        j3 = stru.joints[plate.jointC]
        if plate.jointD == "":
            writer.plane([(j.x, j.y, j.z) for j in (j1, j2, j3)])
        else:
            j4 = stru.joints[plate.jointD]
            writer.plane([(j.x, j.y, j.z) for j in OrderJoints([j1, j2, j3, j4])])
    writer.write(filename)


def write_import_script(
    import_script_name: str,
    iges_filepath: str,
    intermediate_file_path: str,
    offset_to_tos: bool = False,
):
    with open(os.path.dirname(__file__) + "/part_import_template.py") as f_temp:
        template = f_temp.read()
    script = template.format(
        iges_path=iges_filepath,
        model_name="Model-1",
        part_name="imported_part",
        intermediate_file=intermediate_file_path,
        offset_to_tos=offset_to_tos,
    ).replace("\\", "\\\\")
    with open(import_script_name, "wt") as f_out:
        f_out.write(script)


def write_intermediate_file(stru: SacsStructure, filename: str):
    with open(filename, "wt") as f_out:
        json.dump(stru.to_dict(), f_out)
