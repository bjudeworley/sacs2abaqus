import math
import json
from collections import defaultdict
from abaqusConstants import *
import regionToolset

OFFSET_TO_TOS = {offset_to_tos}
GRAVITY = 9.80665


def _index_list_to_seq(geom_seq, idxs):
    seq = geom_seq[idxs[0] : idxs[0] + 1]
    for idx in idxs[1:]:
        seq += geom_seq[idx : idx + 1]
    return seq


def _get_edge_ends(part, edge):
    verts_idxs = edge.getVertices()
    verts = [part.vertices[v] for v in verts_idxs]
    return [v.pointOn[0] for v in verts]


def _dot(a, b):
    return sum([i * j for i, j in zip(a, b)])


def _length(v):
    return math.sqrt(_dot(v, v))


def _flip_normals(part, data):
    plate_assignments = defaultdict(list)
    plates = list(data["plates"].values())
    centroids = [p["centroid"] for p in plates]
    faces = part.faces.getClosest(centroids, searchTolerance=0.01)
    to_flip = []
    for i, plate in enumerate(plates):
        face, pt = faces[i]
        normal = face.getNormal()
        if _dot(normal, plate["local_z"]) < 0:
            to_flip.append(face.index)
    part.flipNormal(
        regions=regionToolset.Region(faces=_index_list_to_seq(part.faces, to_flip))
    )
    print("Flipped {{}} faces".format(len(to_flip)))


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
        # Create stringer
        part.Stringer(edges=edge_seq, name="Stringer-{{}}".format(num_stringers))
    # Create wires for the non-stringer beam elements
    part.WirePolyLine(
        points=[lines[i] for i in non_stringer_idxs],
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


def _generate_materials(model, data):
    for name, props in data["materials"].items():
        name = str(name)
        model.Material(name=name)
        model.materials[name].Density(table=((props["density"],),))
        model.materials[name].Elastic(table=((props["youngs"], props["poisson"]),))
        model.materials[name].Plastic(table=((props["yield"], 0.0),))


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
    # Find all the unique pairs of section and material
    materials = defaultdict(list)
    for mem in data["members"].values():
        materials[mem["section"]].append(mem["material"])
    # Loop through the incoming profiles and create the profile and section
    for name, sect in data["profiles"].items():
        name = str(name)
        FUNCTION_MAP[sect["type"]](model, name, sect)
        # TODO: Pass the correct material
        for mat in materials[name]:
            mat = str(mat)
            model.BeamSection(
                name="{{}}_{{}}".format(name, mat),
                integration=DURING_ANALYSIS,
                poissonRatio=0.0,
                profile=name,
                material=mat,
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
        section_name = "{{}}_{{}}".format(mem["section"], mem["material"])
        if is_stringer:
            found_stringer = False
            for stringer_name, stringer_edges in stringers.items():
                # NOTE: This currently assigns to all edges in a stringer
                # This is fine where each stringer is only 1 edge but if we want
                # to group stringers later on, we might need to rethink this
                if edge.index in stringer_edges:
                    stringer_assignments[section_name].append(
                        (stringer_name, part.stringers[stringer_name].edges)
                    )
                    found_stringer = True
                    break
            assert found_stringer, "Could not find a stringer for this edge"
        else:
            edge_assignments[section_name].append(edge.index)
    # Assign non-stringer sections
    for sect_name, edge_idxs in edge_assignments.items():
        part.SectionAssignment(
            region=regionToolset.Region(
                edges=_index_list_to_seq(part.edges, edge_idxs)
            ),
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


def _assign_thicknesses(model, part, data):
    plate_assignments = defaultdict(list)
    plates = list(data["plates"].values())
    centroids = [p["centroid"] for p in plates]
    faces = part.faces.getClosest(centroids, searchTolerance=0.1)
    for i, plate in enumerate(plates):
        face, pt = faces[i]
        plate_assignments[(plate["thickness"], plate["material"])].append(face.index)
    for (t, mat), faces in plate_assignments.items():
        section_name = "PlateSection-{{:.3f}}mm-{{}}".format(1000 * t, mat)
        # TODO: Handle different materials here
        model.HomogeneousShellSection(
            name=section_name,
            preIntegrate=OFF,
            material=str(mat),
            thicknessType=UNIFORM,
            thickness=t,
            thicknessField="",
            nodalThicknessField="",
            idealization=NO_IDEALIZATION,
            poissonDefinition=DEFAULT,
            thicknessModulus=None,
            temperature=GRADIENT,
            useDensity=OFF,
            integrationRule=SIMPSON,
            numIntPts=5,
        )
        part.SectionAssignment(
            region=regionToolset.Region(faces=_index_list_to_seq(part.faces, faces)),
            sectionName=section_name,
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
    flip_edges = []
    for i in edges:
        edge, pt = edges[i]
        # Check if the line is the same orientation as in SACS, add to flip list if not
        e_dir = [end - start for start, end in zip(*_get_edge_ends(part, edge))]
        l_dir = [end - start for start, end in zip(*lines[i])]
        if _dot(e_dir, l_dir) < 0:
            flip_edges.append(edge.index)
    # Flip any edges that are set up in the opposite direction to SACS
    part.flipTangent(
        regions=regionToolset.Region(edges=_index_list_to_seq(part.edges, flip_edges))
    )


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


def _assign_point_masses(part, data):
    mass_assignments = defaultdict(list)
    point_masses = [mass for mass in data["masses"] if "joint" in mass]
    joints = [data["joints"][mass["joint"]]["position"] for mass in point_masses]
    verts = part.vertices.getClosest(joints, searchTolerance=0.01)
    for i, point_mass in enumerate(point_masses):
        vert, pt = verts[i]
        # Point masses are taken as the magnitude of the load, regardless of direction
        mass_assignments[_length(point_mass["load"][:3]) / GRAVITY].append(vert.index)
    for i, (point_mass, verts) in enumerate(mass_assignments.items()):
        # Gather faces into a face region
        region = regionToolset.Region(vertices=_index_list_to_seq(part.vertices, verts))
        # Apply the area mass
        part.engineeringFeatures.PointMassInertia(
            name="PointInertia-{{}}".format(i),
            region=region,
            mass=point_mass,
            alpha=0.0,
            composite=0.0,
        )


def _assign_line_masses(part, data):
    # Gather stringer edges
    stringer_map = dict()
    for stringer_name, stringer in part.stringers.items():
        for e in stringer.edges:
            stringer_map[e.index] = stringer_name
    # Gather all line mass assignments
    beam_mass_assignments = defaultdict(list)
    stringer_mass_assignments = defaultdict(list)
    line_masses = [mass for mass in data["masses"] if "beam" in mass]
    members = [data["members"][mass["beam"]] for mass in line_masses]
    lines = [(m["jointA"]["position"], m["jointB"]["position"]) for m in members]
    mid_points = [([(i + j) / 2 for i, j in zip(start, end)]) for start, end in lines]
    edges = part.edges.getClosest(coordinates=mid_points, searchTolerance=0.1)
    # Categorise the masses into beam and stringers
    for idx, (line, mass) in enumerate(zip(lines, line_masses)):
        beam_length = _length([j - i for i, j in zip(*line)])
        load_length = mass["load_length"] or (beam_length - mass["start_offset"])
        # Here we calculate the total load across the loaded segment of the beam
        # and redistribute it across the whole beam. Therefore this will not correctly
        # distribute an asymmetrically loaded beam correctly, but this happens
        # relatively rarely in practice.
        # We also assume that the loads are of the same sign. It doesnt make sense
        # for a mass-load to change signs across a beam but emit a warning if we have
        # that.
        if (mass["load"][0] >= 0) != (mass["load"][1] >= 0):
            print(
                "WARNING: Beam load on {{}} changes sign. This is unsupported".format(
                    mass["beam"]
                )
            )
        linear_mass = 0.5 * abs(sum(mass["load"])) * load_length / beam_length
        linear_mass /= GRAVITY
        edge, pt = edges[idx]
        if edge.index in stringer_map:
            stringer_mass_assignments[linear_mass].append(
                (stringer_map[edge.index], edge.index)
            )
        else:
            beam_mass_assignments[linear_mass].append(edge.index)
    for i, (line_mass, edges) in enumerate(beam_mass_assignments.items()):
        # Gather edges into a edge region
        region = regionToolset.Region(edges=_index_list_to_seq(part.edges, edges))
        # Apply the area mass
        part.engineeringFeatures.NonstructuralMass(
            name="BeamInertia-{{}}".format(i),
            region=region,
            units=MASS_PER_LENGTH,
            magnitude=line_mass,
            distribution=MASS_PROPORTIONAL,
        )
    for i, (line_mass, edges) in enumerate(stringer_mass_assignments.items()):
        region = regionToolset.Region(
            stringerEdges=[
                (stringer_name, part.edges[e : e + 1]) for stringer_name, e in edges
            ]
        )
        # Apply the area mass
        part.engineeringFeatures.NonstructuralMass(
            name="StringerInertia-{{}}".format(i),
            region=region,
            units=MASS_PER_LENGTH,
            magnitude=line_mass,
            distribution=MASS_PROPORTIONAL,
        )


def _assign_area_masses(part, data):
    mass_assignments = defaultdict(list)
    area_masses = [mass for mass in data["masses"] if "plate" in mass]
    plates = [data["plates"][mass["plate"]] for mass in area_masses]
    centroids = [p["centroid"] for p in plates]
    faces = part.faces.getClosest(centroids, searchTolerance=0.01)
    for i, area_mass in enumerate(area_masses):
        face, pt = faces[i]
        mass_assignments[abs(area_mass["load"]) / GRAVITY].append(face.index)
    for i, (area_mass, faces) in enumerate(mass_assignments.items()):
        # Gather faces into a face region
        region = regionToolset.Region(faces=_index_list_to_seq(part.faces, faces))
        # Apply the area mass
        part.engineeringFeatures.NonstructuralMass(
            name="AreaInertia-{{}}".format(i),
            region=region,
            units=MASS_PER_AREA,
            magnitude=area_mass,
            distribution=MASS_PROPORTIONAL,
        )


def _assign_mass_inertias(part, data):
    _assign_point_masses(part, data)
    _assign_line_masses(part, data)
    _assign_area_masses(part, data)


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

m = mdb.models["{model_name}"]
p = m.parts["{part_name}"]
with open("{intermediate_file}", "r") as f_in:
    data = json.load(f_in)

_flip_normals(p, data)
_generate_wires(p, data)
_generate_materials(m, data)
_generate_sections(m, data)
_assign_sections(p, data)
_assign_thicknesses(m, p, data)
_align_edges(p, data)
_assign_beam_orientations(p, data)
_assign_mass_inertias(p, data)
