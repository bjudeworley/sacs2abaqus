import os
import sys
import math
import logging

from sacs2abaqus.geom3 import BeamCSys, Vector3
from sacs2abaqus.sacs_cards import *

# SACS to ABAQUS converter
# Converts a SACS file to an Abaqus input file (.inp)


# CONFIGURATION
# Set the following to the main SACS file (keep the 'r' before the string)
# sacs_file1=r'sacinp.zpq_gravity'
sacs_file1 = r"SACINP.cp6s.top.1.inp"

# Set the following to another SACS file if required (eg. a section library)
# or set to r'' if not required
# sacs_file2=r'aiscwf.sacinp'
sacs_file2 = r""

# GENERAL NOTES
# - All plate elements are assigned material 'Mtl-Plate'
# - All beam elements are assignmed material 'Mtl-Beam'
# - A map of joint IDs to Abaqus node IDs is printed to <outputname>_nmap.txt
# - Joint-based loads are output for all load cases to <outputname>_loads.txt
# - Member-based loads are not parsed
# - Script attempts to rearrange node ordering of plate elements to ensure they
#   do not self-intersect
#

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------
length_tol = 1.0e-6
beam_type = "B31"


# ------------------------------------------------------------------------------
# FUNCTIONS
# ------------------------------------------------------------------------------
def GetDistance(n1, n2):
    """
    Returns the distance between two nodes points n1 and n2 (x,y,z)
    Returns False if there is an error
    """
    try:
        return math.sqrt((n1.x - n2.x) ** 2 + (n1.y - n2.y) ** 2 + (n1.z - n2.z) ** 2)
    except:
        return False


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def ccw(A, B, C):
    return (C.y - A.y) * (B.x - A.x) > (B.y - A.y) * (C.x - A.x)


def Intersect(A, B, C, D):
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)


def OrderJoints(jlist):
    """
    Given 4 joint instances, returns the joint ABQIDs in order such that they
    do not result in a self-intersecting plate element
    This is done in a way that retains the local coordinate system of the plate, 
    which is defined by the joint ordering
    """
    j1, j2, j3, j4 = [Vector3(j.x, j.y, j.z) for j in jlist]
    local_x = (j2 - j1).normalise()
    # Calculate the angle between the (j1 to j2) and (j1 to j3)
    j3_ang = math.acos(local_x.dot(j3 - j1) / (j3 - j1).length())
    j4_ang = math.acos(local_x.dot(j4 - j1) / (j4 - j1).length())
    if j3_ang > j4_ang:
        return [jlist[i] for i in [0, 1, 3, 2]]
    return list(jlist)

# ------------------------------------------------------------------------------
# MAIN PROGRAM
# ------------------------------------------------------------------------------

# import Tkinter, tkFileDialog, tkMessageBox

# Temporary disable of Tkinter method since Abaqus doesn't like it
dialog_import = False

if dialog_import:
    if len(sys.argv) > 1:
        pass
    else:
        root = Tkinter.Tk()
        root.withdraw()
        # Get file names from user
        sacs_file = tkFileDialog.askopenfile(
            parent=root, mode="rb", title="Choose SACS input file"
        )
        if sacs_file == None:
            print("No SACS file selected, exiting...")
            os.system("pause")
            exit(0)
        else:
            file_list = [sacs_file.name]
            if tkMessageBox.askyesno(
                "Additional SACS File",
                "Import an addition SACS file (e.g. section library)?",
            ):
                sacs_file = tkFileDialog.askopenfile(
                    parent=root, mode="rb", title="Choose SACS input file"
                )
                if sacs_file == None:
                    print("No SACS file selected, exiting...")
                    os.system("pause")
                    exit(0)
                else:
                    file_list.append(sacs_file.name)
else:
    file_list = [sacs_file1]
    if sacs_file2:
        file_list.append(sacs_file2)

inp_file = file_list[0] + ".inp"

logging.basicConfig(filename=file_list[0] + ".log", level=logging.DEBUG)

print("Reading from SACS files...")


def parse_sacs_file(input_file: str, secondary_input: str = None):
    stru = SacsStructure()
    file_list = [input_file] + (
        [secondary_input] if secondary_input is not None else []
    )
    for fname in file_list:
        with open(fname, "rt") as f_in:
            lines = f_in.readlines()
        for l in lines:
            # Make sure all lines are 80 characters long, extending any shorter ones with spaces
            l = l.rstrip() + " " * (80 - len(l.rstrip()))
            if not l.rstrip() == "JOINT" and l[:5] == "JOINT":
                # JOINT
                if l[54:60] == "ELASTI" and l[6:10] in stru.joints:
                    # Elastic spring definition
                    stru.joints[l[6:10]].Elastic(l)
                elif l[54:60] == "ELASTI":
                    # Spring definition before JOINT
                    print(
                        "WARNING: A joint spring is defined before its joint is defined! Skipping...\n"
                    )
                else:
                    # JOINT geometry definition line
                    stru.abq_n += 1
                    j = JOINT(l, stru.abq_n)
                    stru.joints[j.ID] = j
                    stru.nmap.append((j.ABQID, j.ID))
            elif (
                l[:6] == "MEMBER"
                and not l.rstrip() == "MEMBER"
                and not l[7:14] == "OFFSETS"
            ):
                # MEMBER
                m = MEMBER(l)
                stru.members[m.ID] = m
            elif (
                l[:5] == "PLATE"
                and not l.rstrip() == "PLATE"
                and not l[7:14] == "OFFSETS"
            ):
                # PLATE
                p = PLATE(l)
                stru.plates[p.ID] = p
            elif not l.rstrip() == "SECT" and l[:4] == "SECT":
                if not l[5:12] in stru.sects:
                    # Add this section to sects list
                    s = SECT(l)
                    stru.sects[s.ID] = s
            elif not l.strip() == "PSTIF" and l[:5] == "PSTIF":
                if not l[10:17].strip() in stru.sects:
                    s = PSTIF(l)
                    stru.sects[s.ID] = s
            elif not l.rstrip() == "GRUP" and l[:4] == "GRUP":
                # GROUP
                if not l[5:8] in stru.grups:
                    # First group line for this group
                    g = GRUP(l, "MEMBER")
                    stru.grups[g.ID] = g
            elif not l.rstrip() == "PGRUP" and l[:5] == "PGRUP":
                # PLATE GROUP
                if not l[5:8] in stru.pgrups:
                    # First group line for this group
                    pg = PGRUP(l, "PLATE")
                    stru.pgrups[pg.ID] = pg
            elif l[:6] == "LOADCN":
                # NEW LOAD CASE
                stru.load_case = l[7:12].strip()
                stru.loadcases[stru.load_case] = LOADCASE()
            elif l[:6] == "LOADLB":
                # LOAD CASE LABEL
                stru.loadcases[stru.load_case].description = l[6:80]
            elif l[:4] == "LOAD":
                if l[60:64] == "GLOB" and l[65:69] == "JOIN":
                    # Point load
                    stru.loadcases[stru.load_case].AddLoad(l)
            elif l[:5] == "LCOMB":
                # LOAD COMBINATION
                lc = l[6:10].strip()
                if lc in stru.lcombs:
                    # Already defined, so just add loads to this load combo
                    stru.lcombs[lc].AddLoads(l)
                else:
                    # Create new combo instance and populate with this line
                    stru.lcombs[lc] = LCOMB()
                    stru.lcombs[lc].AddLoads(l)
    return stru



def merge_small_members(stru: SacsStructure) -> None:
    strip_count = 0
    for m in stru.members.keys():
        if (
            GetDistance(
                stru.joints[stru.members[m].jointA], stru.joints[stru.members[m].jointB]
            )
            < length_tol
        ):
            strip_count += 1
            # Merge the end joints of this member to retain continuity in the model
            # and record the merge in the nmap list
            stru.nmap[stru.joints[stru.members[m].jointB].ABQID - 1].append(
                "MERGED WITH {}".format(stru.joints[stru.members[m].jointA].ABQID)
            )
            stru.joints[stru.members[m].jointB].ABQID = stru.joints[
                stru.members[m].jointA
            ].ABQID
    print("\n {} members were removed.".format(strip_count))



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
            "*Element, type={}, elset=MG-{}\n".format(beam_type, g.replace(".", "-"))
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
            out.write("{}, {}, {}\n".format(local_z.x, local_z.y, local_z.z))
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


stru = parse_sacs_file(file_list[0], file_list[1] if len(file_list) == 2 else None)
print(
    "\nReading complete:\n\t"
    + str(len(stru.joints))
    + " joints were successfully read\n\t"
    + str(len(stru.members))
    + " elements (members) were successfully read"
)

print("\nRemoving elements with length smaller than specified tolerance")
merge_small_members(stru)

print("\nGenerating orphan mesh:")
with open(inp_file, "w") as out:
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

print("\nWriting node number map to " + inp_file + "_nmap.txt...")
try:
    out = open(inp_file + "_nmap.txt", "w")
except:
    print(
        "Error trying to open "
        + inp_file
        + "_nmap.txt, check that you have permission to do so. Exiting"
    )
    exit(2)
out.write("ABQ\t->\tSACS\n")
for n in stru.nmap:
    if len(n) == 3:
        out.write("{}\t->\t{}->\t{}\n".format(n[0], n[1], n[2]))
    else:
        out.write("{}\t->\t{}\n".format(n[0], n[1]))
out.close()

print("\nWriting element number map to " + inp_file + "_elmap.txt...")
try:
    out = open(inp_file + "_elmap.txt", "w")
except:
    print(
        "Error trying to open "
        + inp_file
        + "_elmap.txt, check that you have permission to do so. Exiting"
    )
    exit(2)
out.write("ABQ\t->\tSACS\n")
elmap = []
for m in stru.members:
    elmap.append([stru.members[m].ABQID, m])
for e in sorted(elmap):
    out.write("{}\t->\t{}\n".format(e[0], e[1]))
out.close()

print("\nWriting load cases to " + inp_file + "_loads.txt...")
try:
    out = open(inp_file + "_loads.txt", "w")
except:
    print(
        "Error trying to open "
        + inp_file
        + "_loads.txt, check that you have permission to do so. Exiting"
    )
    exit(2)
out.write("** INDIVIDUAL LOAD CASES **\n**\n")
try:
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
                    "{}, {}, {}\n".format(stru.joints[l.joint].ABQID, d + 1, l.force[d])
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
except Exception as e:
    print("Error writing loads, skipping.")
    logging.error("**ERROR WRITING LOADS, TERMINATING EARLY: {}\n".format(e))
out.close()

print("\nConversion complete. Please check .log file for warnings and errors.")

exit(0)

# Temp - convert point loads into point masses
lcm_list = ["A91", "B91", "C91", "D91"]
out = open("point_masses.inp", "w")
mass_num = 1
loadset = {}
for lcm in lcm_list:
    for lc in stru.lcombs[lcm].loadcases:
        if lc[0] in stru.loadcases:
            for l in stru.loadcases[lc[0]].loads:
                j = l.joint
                if not j in loadset:
                    loadset[j] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                for i in range(6):
                    loadset[j][i] += l.force[i] * lc[1]
        else:
            print("{} not in load case definitions!".format(lc))
for j in loadset:
    mass = abs(loadset[j][2] / 9.8)
    out.write("*Element, type=MASS, elset=MASS-{}\n".format(mass_num))
    out.write("{}, {}\n".format(elnum, stru.joints[j].ABQID))
    out.write("*Mass, elset=MASS-{}\n".format(mass_num))
    out.write("{}\n".format(mass))
    mass_num += 1
    elnum += 1
out.close()

os.system("pause")
exit(0)
