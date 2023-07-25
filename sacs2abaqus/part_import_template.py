import json
from abaqusConstants import *


def _generate_wires(part, data):
    lines = [
        (m["jointA"]["position"], m["jointB"]["position"])
        for m in data["members"].values()
    ]
    part.WirePolyLine(
        points=(lines),
        mergeType=SEPARATE,
        meshable=ON,
    )


iges = mdb.openIges(
    "{iges_path}",
    msbo=False,
    trimCurve=DEFAULT,
    scaleFromFile=OFF,
    topology=SHELL,
)
mdb.models["{model_name}"].PartFromGeometryFile(
    name="{part_name}",
    geometryFile=iges,
    combine=False,
    stitchTolerance=0.1,
    dimensionality=THREE_D,
    type=DEFORMABLE_BODY,
    convertToAnalytical=1,
    stitchEdges=1,
)

p = mdb.models["{model_name}"].parts["{part_name}"]
with open("{intermediate_file}", "r") as f_in:
    data = json.load(f_in)

_generate_wires(p, data)
