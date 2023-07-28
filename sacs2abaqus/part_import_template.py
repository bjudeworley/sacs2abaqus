import json
from collections import defaultdict
from abaqusConstants import *
import regionToolset

OFFSET_TO_TOS = {offset_to_tos}


def _get_edge_ends(part, edge):
    verts_idxs = edge.getVertices()
    verts = [part.vertices[v] for v in verts_idxs]
    return [v.pointOn[0] for v in verts]


def _dot(a, b):
    return sum([i * j for i, j in zip(a, b)])


def _generate_wires(part, data):
    lines = [
        (m["jointA"]["position"], m["jointB"]["position"])
        for m in data["members"].values()
    ]
    mid_points = [([(i + j) / 2 for i, j in zip(start, end)]) for start, end in lines]
    # Find all plate edges that are near one of our beams
    edges = part.edges.getClosest(coordinates=mid_points, searchTolerance=0.1)
    # Any edges that we found indicate stringers, only create wires where we dont
    # have a stringer
    non_stringer_idxs = [i for i in range(len(lines)) if i not in edges]
    # Create stringers for all edges that we found
    num_stringers = 0
    for i in edges:
        edge, pt = edges[i]
        assert len(edge.getFaces()) > 0
        num_stringers += 1
        edge_seq = part.edges[edge.index : edge.index + 1]
        part.Stringer(edges=edge_seq, name="Stringer-{{}}".format(num_stringers))
    # Create wires for the non-stringer beam elements
    part.WirePolyLine(
        points=[lines[i] for i in non_stringer_idxs],
        mergeType=SEPARATE,
        meshable=ON,
    )
    set_edges = None
    for e, pt in edges.values():
        if set_edges is None:
            set_edges = part.edges[e.index : e.index + 1]
        else:
            set_edges = set_edges + part.edges[e.index : e.index + 1]


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
        l=sect["h"] if OFFSET_TO_TOS else sect["offset"],
        h=sect["h"],
        b1=sect["bf_bot"],
        b2=sect["bf_top"],
        t1=sect["tf_bot"],
        t2=sect["tf_top"],
        t3=sect["tw"],
    )


def _make_TEE_section(model, name, sect):
    # Force all Tee sections to be offset for use as plate stiffeners
    model.TProfile(
        name=name,
        l=0 if OFFSET_TO_TOS else sect["offset"],
        h=sect["h"],
        b=sect["bf"],
        tf=sect["tf"],
        tw=sect["tw"],
    )


def _make_L_section(model, name, sect):
    if "offset" in sect:
        # Assumes this is a stiffener type (offset base of web to beam axis)
        h = sect["h"]
        bf = sect["bf"]
        tf = sect["tf"]
        tw = sect["tw"]
        # Calculate the x offset of the centroid
        A_tot = (h * tw) + (bf * tf)
        x_off = (((bf / 2) * bf * tf)) / A_tot
        # Calculate y offset if we dont need to offset the section
        if OFFSET_TO_TOS:
            y_off = 0
        else:
            y_off = (((h / 2) * h * tw) + ((h - tf / 2) * bf * tf)) / A_tot
        # Build the section edges
        section_edges = (
            (-x_off, -y_off),
            (-x_off, h - y_off, tw),
            (bf - x_off, h - y_off, tf),
        )
        model.ArbitraryProfile(name=name, table=section_edges)
    else:
        model.LProfile(
            name=name, a=sect["bf"], b=sect["h"], t1=sect["tf"], t2=sect["tw"]
        )


def _make_CHL_section(model, name, sect):
    offset = sect["offset"]
    h = sect["h"]
    bf_bot = sect["bf_bot"]
    bf_top = sect["bf_top"]
    tf_bot = sect["tf_bot"]
    tf_top = sect["tf_top"]
    tw = sect["tw"]
    # Calculate the x offset of the centroid
    A_tot = (h * tw) + (bf_top * tf_top) + (bf_bot * tf_bot)
    x_off = (
        ((bf_top / 2) * bf_top * tf_top) + ((bf_bot / 2) * bf_bot * tf_bot)
    ) / A_tot
    # Build the section edges
    section_edges = (
        (bf_bot - x_off, -offset),
        (0 - x_off, -offset, tf_bot),
        (0 - x_off, h - offset, tw),
        (bf_top - x_off, h - offset, tf_top),
    )
    model.ArbitraryProfile(name=name, table=section_edges)


def _make_ARBITRARY_section(model, name, sect):
    model.GeneralizedProfile(
        name=name,
        area=sect["area"],
        i11=sect["I11"],
        i12=sect["I12"],
        i22=sect["I22"],
        j=sect["J"],
        gammaO=0,
        gammaW=0,
    )


# endregion


def _generate_sections(model, data):
    # fmt: off
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
    # fmt: on
    # Create Dummy material for now
    # TODO: Handle creating all the materials we need from GRUP cards
    model.Material(name="DUMMY_MAT")
    model.materials["DUMMY_MAT"].Density(table=((7850.0,),))
    model.materials["DUMMY_MAT"].Elastic(table=((200000000000.0, 0.3),))
    model.materials["DUMMY_MAT"].Plastic(table=((235000000.0, 0.0),))
    # Loop through the incoming profiles and create the profile and section
    for name, sect in data["profiles"].items():
        name = str(name)
        FUNCTION_MAP[sect["type"]](model, name, sect)
        # TODO: Pass the correct material
        model.BeamSection(
            name=name,
            integration=DURING_ANALYSIS,
            poissonRatio=0.0,
            profile=name,
            material="DUMMY_MAT",
            temperatureVar=LINEAR,
            consistentMassMatrix=False,
        )


def _assign_sections(part, data):
    members = list(data["members"].values())
    lines = [(m["jointA"]["position"], m["jointB"]["position"]) for m in members]
    mid_points = [([(i + j) / 2 for i, j in zip(start, end)]) for start, end in lines]
    edges = part.edges.getClosest(coordinates=mid_points, searchTolerance=0.1)
    # Gather all edges/stringers that need to be assigned a given section
    edge_assignments = defaultdict(list)
    stringer_assignments = defaultdict(list)
    # Gather stringer info to speed up searching
    # fmt: off
    stringers = {{
        name: set(e.index for e in stringer.edges)
        for name, stringer in part.stringers.items()
    }}
    # fmt: on
    for i, mem in enumerate(members):
        edge, pt = edges[i]
        is_stringer = len(edge.getFaces()) > 0
        if is_stringer:
            found_stringer = False
            for stringer_name, stringer_edges in stringers.items():
                # NOTE: This currently assigns to all edges in a stringer
                # This is fine where each stringer is only 1 edge but if we want
                # to group stringers later on, we might need to rethink this
                if edge.index in stringer_edges:
                    stringer_assignments[str(mem["section"])].append(
                        (stringer_name, part.stringers[stringer_name].edges)
                    )
                    found_stringer = True
                    break
            assert found_stringer, "Could not find a stringer for this edge"
        else:
            edge_assignments[str(mem["section"])].append(edge.index)
    # Assign non-stringer sections
    for sect_name, edges in edge_assignments.items():
        edge_set = part.edges[edges[0] : edges[0] + 1]
        for e in edges[1:]:
            edge_set = edge_set + part.edges[e : e + 1]
        part.SectionAssignment(
            region=regionToolset.Region(edges=edge_set),
            sectionName=sect_name,
            offset=0.0,
            offsetType=MIDDLE_SURFACE,
            offsetField="",
            thicknessAssignment=FROM_SECTION,
        )
    # Assign stringer sections
    for sect_name, edge_set in stringer_assignments.items():
        part.SectionAssignment(
            region=regionToolset.Region(stringerEdges=edge_set),
            sectionName=sect_name,
            offset=0.0,
            offsetType=MIDDLE_SURFACE,
            offsetField="",
            thicknessAssignment=FROM_SECTION,
        )


def _align_edges(part, data):
    lines = [
        (m["jointA"]["position"], m["jointB"]["position"])
        for m in data["members"].values()
    ]
    mid_points = [([(i + j) / 2 for i, j in zip(start, end)]) for start, end in lines]
    # Find all plate edges that are near one of our beams
    edges = part.edges.getClosest(coordinates=mid_points, searchTolerance=0.1)
    flip_edges = None
    num_flipped = 0
    for i in edges:
        edge, pt = edges[i]
        edge_seq = part.edges[edge.index : edge.index + 1]
        # Check if the line is the same orientation as in SACS, add to flip list if not
        e_dir = [end - start for start, end in zip(*_get_edge_ends(part, edge))]
        l_dir = [end - start for start, end in zip(*lines[i])]
        if _dot(e_dir, l_dir) < 0:
            num_flipped += 1
            if flip_edges is None:
                flip_edges = edge_seq
            else:
                flip_edges += edge_seq
    # Flip any edges that are set up in the opposite direction to SACS
    part.flipTangent(regions=regionToolset.Region(edges=flip_edges))


def _assign_beam_orientations(part, data):
    # Gather stringer info to speed up searching
    # fmt: off
    stringers = {{
        name: set(e.index for e in stringer.edges)
        for name, stringer in part.stringers.items()
    }}
    # fmt: on
    members = list(data["members"].values())
    lines = [(m["jointA"]["position"], m["jointB"]["position"]) for m in members]
    mid_points = [([(i + j) / 2 for i, j in zip(start, end)]) for start, end in lines]
    edges = part.edges.getClosest(coordinates=mid_points, searchTolerance=0.1)
    # Loop through each all members and assign local orientation
    for i, mem in enumerate(members):
        edge, pt = edges[i]
        section_x = mem["local_y"]
        is_stringer = len(edge.getFaces()) > 0
        if is_stringer:
            region = None
            for stringer_name, stringer_edges in stringers.items():
                # NOTE: This currently assigns to all edges in a stringer
                # This is fine where each stringer is only 1 edge but if we want
                # to group stringers later on, we might need to rethink this
                if edge.index in stringer_edges:
                    region = regionToolset.Region(
                        stringerEdges=[
                            (
                                stringer_name,
                                part.stringers[stringer_name].edges,
                            )
                        ]
                    )
                    break
            assert region is not None, "Could not find a stringer for this edge"
        else:
            region = regionToolset.Region(edges=part.edges[edge.index : edge.index + 1])

        part.assignBeamSectionOrientation(
            region=region, method=N1_COSINES, n1=section_x
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
_generate_sections(mdb.models["{model_name}"], data)
_assign_sections(p, data)
_align_edges(p, data)
_assign_beam_orientations(p, data)
