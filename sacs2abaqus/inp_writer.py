import logging

from .helpers import OrderJoints
from .geom3 import BeamCSys, Vector3
from .sacs_cards import SacsStructure

BEAM_TYPE = "B31"


def write_abaqus_input(stru: SacsStructure, outfile_name: str, write_secondary: bool):
    print("\nGenerating orphan mesh:")
    with open(outfile_name, "w") as out:
        print("\tWriting nodes to input file...")
        write_nodes(stru, out)
        print("\tWriting elements to input file...")
        write_elements(stru, out)
        print("\t Generating Element Sets...")
        write_sets(stru, out)
        print("\tWriting beam section assignments to input file...")
        write_beam_sections(stru, out)
        print("\tWriting plate section assignments to input file...")
        write_plate_sections(stru, out)

    if write_secondary:
        print("\nWriting node number map to " + outfile_name + "_nmap.txt...")
        write_node_map(stru, outfile_name + "_nmap.txt")

        print("\nWriting element number map to " + outfile_name + "_elmap.txt...")
        write_element_map(stru, outfile_name + "_elmap.txt")

        print("\nWriting load cases to " + outfile_name + "_loads.txt...")
        try:
            write_loads(stru, outfile_name + "_loads.txt")
        except Exception as e:
            print("Error writing loads, skipping.")
            logging.error("**ERROR WRITING LOADS, TERMINATING EARLY: {}\n".format(e))


def write_nodes(stru: SacsStructure, out):
    out.write("*Node, nset=N-AllNodes\n")
    for j in sorted(stru.joints.keys()):
        out.write(
            "{}, {}, {}, {}\n".format(
                stru.joints[j].ABQID,
                stru.joints[j].x,
                stru.joints[j].y,
                stru.joints[j].z,
            )
        )


def write_elements(stru: SacsStructure, out):
    elnum = 1
    for g in stru.grups:
        out.write(
            "*Element, type={}, elset=MG-{}\n".format(BEAM_TYPE, g.replace(".", "-"))
        )
        for m in stru.members:
            if stru.members[m].group == g:
                stru.members[m].ABQID = elnum
                out.write(
                    "{}, {}, {}\n".format(
                        stru.members[m].ABQID,
                        stru.joints[stru.members[m].jointA].ABQID,
                        stru.joints[stru.members[m].jointB].ABQID,
                    )
                )
                elnum += 1
    for pg in stru.pgrups:
        for p in stru.plates:
            if stru.plates[p].group == pg:
                stru.plates[p].ABQID = elnum
                if stru.plates[p].jointD == "":
                    # 3-element shell
                    out.write(
                        "*Element, type=S3, elset=PG-{}\n".format(pg.replace(".", "-"))
                    )
                    out.write(
                        "{}, {}, {}, {}\n".format(
                            stru.plates[p].ABQID,
                            stru.joints[stru.plates[p].jointA].ABQID,
                            stru.joints[stru.plates[p].jointB].ABQID,
                            stru.joints[stru.plates[p].jointC].ABQID,
                        )
                    )
                else:
                    # 4-element shell
                    out.write(
                        "*Element, type=S4R, elset=PG-{}\n".format(pg.replace(".", "-"))
                    )
                    # Sometimes the order of joints in SACS results in a self-intersecting
                    # element in Abaqus. Try to fix this assuming all plates are roughly
                    # rectangular and checking that the next node defined is never the furthest away
                    j1 = stru.joints[stru.plates[p].jointA]
                    j2 = stru.joints[stru.plates[p].jointB]
                    j3 = stru.joints[stru.plates[p].jointC]
                    j4 = stru.joints[stru.plates[p].jointD]
                    j1, j2, j3, j4 = OrderJoints([j1, j2, j3, j4])
                    out.write(
                        "{}, {}, {}, {}, {}\n".format(
                            elnum, j1.ABQID, j2.ABQID, j3.ABQID, j4.ABQID
                        )
                    )
                elnum += 1


def write_sets(stru: SacsStructure, out):
    out.write("****MEMBER ELEMENT SETS****\n")
    for m in stru.members:
        out.write(
            "*Elset, elset=M-{}\n{}\n".format(
                stru.members[m].ID.replace(".", "-"), stru.members[m].ABQID
            )
        )
    out.write("****PLATE ELEMENT SETS****\n")
    for p in stru.plates:
        out.write(
            "*Elset, elset=P-{}\n{}\n".format(
                stru.plates[p].ID.replace(".", "-"), stru.plates[p].ABQID
            )
        )


def write_beam_sections(stru: SacsStructure, out):
    out.write("**\n** BEAM SECTIONS **\n")
    # Have to assign sections to individual members, not groups, as we can not
    # guarentee that all members in a group are vertical or non-vertical, so
    # can't give a blanket orientation assignment
    for m in stru.members:
        g = stru.members[m].group
        assigned = False
        if g in stru.grups:
            if stru.grups[g].section:
                # This group uses a section definition: get values from that
                try:
                    s = stru.sects[stru.grups[g].section]
                except KeyError:
                    # This occurs if a SECT is specified in the GRUP, but there
                    # is no corresponding SECT definition in the SACS file, so
                    # use the section properties from the GRUP line instead.
                    s = ""
                except Exception as e:
                    # Unexpected error, log
                    logging.error(
                        "ERROR: {} when trying to use section of GROUP: {}".format(e, g)
                    )
                if s:
                    if s.sect in ["CON"]:
                        logging.warning(
                            "Members in group {} are assigned CON section; skipping\n".format(
                                g
                            )
                        )
                    elif s.sect in ["PIPE", "I", "TEE", "L", "CHL", "ARBITRARY", "BOX"]:
                        out.write(s.abaqus_section_defn(m))
                        assigned = True
                    else:
                        logging.warning(
                            "Unknown section assignment in group {}, skipping\n.".format(
                                g
                            )
                        )
            else:
                # This group defines its owns sects without a discrete SECT line
                if stru.grups[g].OD != 0.0:
                    # Pipe
                    out.write(
                        "*Beam Section, elset=M-{}, section={}, material=Mtl-Beam\n".format(
                            m.replace(".", "-"), "PIPE"
                        )
                    )
                    # Abaqus requires input of outside radii, whereas SACS is in OD
                    out.write(
                        "{}, {}\n".format(stru.grups[g].OD / 2, stru.grups[g].thickness)
                    )  # outside radius, wall thickness
                    assigned = True
                else:
                    logging.warning(
                        "Unable to determine section properties for group {}, skipping.".format(
                            g
                        )
                    )
        else:
            # Member group not found, report as error
            stru.missing_sect_members.append(m)
            logging.warning(
                "No group definition found for member {}, no section can be assigned!".format(
                    m.replace(".", "-")
                )
            )
        if assigned:
            start = Vector3(
                stru.joints[stru.members[m].jointA].x,
                stru.joints[stru.members[m].jointA].y,
                stru.joints[stru.members[m].jointA].z,
            )
            end = Vector3(
                stru.joints[stru.members[m].jointB].x,
                stru.joints[stru.members[m].jointB].y,
                stru.joints[stru.members[m].jointB].z,
            )
            beam_csys = BeamCSys.from_sacs_points(start, end).rotated_about_x(-90)
            if stru.members[m].chordAngle:
                beam_csys = beam_csys.rotated_about_x(stru.members[m].chordAngle)
            local_z = beam_csys.z
            out.write("{}, {}, {}\n".format(*local_z.as_tuple()))
        else:
            try:
                stru.missing_sect_members.append(m)
                logging.warning(
                    "Missing section assignment for member {} (Group {}, Section ID {})\n".format(
                        m.replace(".", "-"),
                        stru.members[m].group,
                        stru.grups[g].section,
                    )
                )
            except Exception as e:
                logging.error("** Unhandled error for group {}: {}\n".format(g, e))
    out.write("*Material, name=Mtl-Beam\n*Density\n7850.,\n*Elastic\n2e+11, 0.3\n")

    if stru.missing_sect_members:
        out.write("*Elset, elset=ErrMissingSections\n")
        for m in stru.missing_sect_members:
            out.write("M-{}\n".format(m))
        print(
            "\n**NOTE: {} members have sections not defined in the SACS or Library files. These are added to sets ErrMissingSections\n".format(
                len(stru.missing_sect_members)
            )
        )


def write_plate_sections(stru: SacsStructure, out):
    out.write("**\n** PLATE SECTIONS **\n")
    for pg in stru.pgrups:
        out.write(
            "*Shell General Section, elset=PG-{}, material={}\n".format(
                stru.pgrups[pg].ID.replace(".", "-"), "Mtl-Plate"
            )
        )
        out.write("{}\n".format(stru.pgrups[pg].thickness))
    out.write("*Material, name=Mtl-Plate\n*Density\n7850.,\n*Elastic\n2e+11, 0.3\n")


def write_node_map(stru, filename: str):
    with open(filename, "w") as out:
        out.write("ABQ\t->\tSACS\n")
        for nodes in stru.nmap:
            out.write("\t->\t".join([str(node) for node in nodes]) + "\n")


def write_element_map(stru, filename: str):
    with open(filename, "w") as out:
        out.write("ABQ\t->\tSACS\n")
        elmap = [(mem.ABQID, mem_name) for mem_name, mem in stru.members.items()]
        for e in sorted(elmap):
            out.write("{}\t->\t{}\n".format(e[0], e[1]))


def write_loads(stru: SacsStructure, filename: str):
    with open(filename, "w") as out:
        out.write("** INDIVIDUAL LOAD CASES **\n**\n")
        for lc in stru.loadcases:
            out.write(
                "**\n** LOAD CASE {}\n** {}\n**\n".format(
                    lc, stru.loadcases[lc].description
                )
            )
            if stru.loadcases[lc].loads:
                out.write("*Cload\n")
            for l in stru.loadcases[lc].loads:
                for d in range(6):
                    out.write(
                        "{}, {}, {}\n".format(
                            stru.joints[l.joint].ABQID, d + 1, l.force[d]
                        )
                    )
            out.write("*" * 80 + "\n")
        out.write("** COMBINATION LOAD CASES **\n**\n")
        for lcm in stru.lcombs:
            loadset = {}
            for lc in stru.lcombs[lcm].loadcases:
                if lc[0] in stru.loadcases:
                    for l in stru.loadcases[lc[0]].loads:
                        j = l.joint
                        if not j in loadset:
                            loadset[j] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                        for i in range(6):
                            loadset[j][i] += l.force[i] * lc[1]
            if loadset:
                out.write("*** COMBINATION LOAD CASE {} ***\n".format(lcm))
                out.write("*Cload\n")
                for jl in loadset:
                    for i in range(6):
                        out.write(
                            "{}, {}, {}\n".format(
                                stru.joints[jl].ABQID, i + 1, loadset[jl][i]
                            )
                        )
                out.write("*" * 80 + "\n")
