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


# region SECTION_BUILDERS
def _make_BOX_section(model, name, sect):
    model.BoxProfile(
        name=name,
        b=sect["h"],
        a=sect["b"],
        t1=sect["tw"],
        t2=sect["tf"],
        t3=sect["tw"],
        t4="tf",
    )


def _make_PIPE_section(model, name, sect):
    model.PipeProfile(name=name, r=sect["radius"], t=sect["t"]),


def _make_TAPER_PIPE_section(model, name, sect):
    model.PipeProfile(
        name=name,
        r=(sect["radius1"] + sect["radius2"]) / 2,
        t=(sect["t1"] + sect["t2"]) / 2,
    )


def _make_I_section(model, name, sect):
    model.IProfile(
        name=name,
        l=sect["offset"],
        h=sect["h"],
        b1=sect["bf_bot"],
        b2=sect["bf_top"],
        t1=sect["tf_bot"],
        t2=sect["tf_top"],
        t3=sect["tw"],
    )


def _make_TEE_section(model, name, sect):
    model.TProfile(
        name=name,
        l=sect["offset"],
        h=sect["h"],
        b=sect["bf"],
        tf=sect["tf"],
        tw=sect["tw"],
    )


def _make_L_section(model, name, sect):
    if "offset" in sect:
        # Model as at Tee since we cant offset L sections correctly
        model.TProfile(
            name=name,
            l=sect["offset"],
            h=sect["h"],
            b=sect["bf"],
            tf=sect["tf"],
            tw=sect["tw"],
        )
    else:
        model.LProfile(
            name=name, a=sect["bf"], b=sect["h"], t1=sect["tf"], t2=sect["tw"]
        )


def _make_CHL_section(model, name, sect):
    # Model as an I since CAE cant handle channels yet (2023)
    model.IProfile(
        name=name,
        l=sect["offset"],
        h=sect["h"],
        b1=sect["bf_bot"],
        b2=sect["bf_top"],
        t1=sect["tf_bot"],
        t2=sect["tf_top"],
        t3=sect["tw"],
    )


def _make_ARBITRARY_section(model, name, sect):
    model.GeneralizedProfile(
        name=name,
        area=sect["area"],
        i11=sect["I11"],
        i12=sect["I12"],
        i22=sect["I22"],
        j=sect["J"],
    )


# endregion


def _generate_sections(model, data):
    FUNCTION_MAP = {{
        "PIPE": _make_PIPE_section,
        "TAPER_PIPE": _make_TAPER_PIPE_section,
        "I": _make_I_section,
        "TEE": _make_TEE_section,
        "L": _make_L_section,
        "CHL": _make_CHL_section,
        "ARBITRARY": _make_ARBITRARY_section,
        "BOX": _make_BOX_section,
    }}
    for name, sect in data["profiles"].items():
        name = str(name)
        FUNCTION_MAP[sect["type"]](model, name, sect)


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
_generate_sections(mdb.models["{model_name}"], data)
