import os
import sys
import math

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
# - Script attempts to assign beam orientations correctly for vertical and
#   non-vertical members
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
    Assumes planar plate aligned to x-y, x-z or y-z plane
    """
    # Determine which plane we are operating in
    j1, j2, j3, j4 = jlist[0], jlist[1], jlist[2], jlist[3]
    if j1.x == j2.x == j3.x == j4.x:
        v1 = "y"
        v2 = "z"
    elif j1.y == j2.y == j3.y == j4.y:
        v1 = "x"
        v2 = "z"
    elif j1.z == j2.z == j3.z == j4.z:
        v1 = "x"
        v2 = "y"
    else:
        # Not aligned to a global plane
        return j1, j2, j3, j4

    # Set points for corners in terms of planar coordinates
    p1 = Point(eval("j1." + v1), eval("j1." + v2))
    p2 = Point(eval("j2." + v1), eval("j2." + v2))
    p3 = Point(eval("j3." + v1), eval("j3." + v2))
    p4 = Point(eval("j4." + v1), eval("j4." + v2))
    if Intersect(p1, p2, p3, p4) or Intersect(p2, p3, p1, p4):
        j2, j3 = j3, j2
        if Intersect(p2, p3, p1, p4):
            j3, j4 = j4, j3
    return j1, j2, j3, j4


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
try:
    log = open(file_list[0] + ".log", "w")
except:
    exit(1)

members = {}
plates = {}
grups = {}
pgrups = {}
sects = {}
joints = {}
nmap = []
abq_n = 0
lcombs = {}
loadcases = {}
load_case = ""
missing_sect_members = []
intersections = []

print("Reading from SACS files...")
for fname in file_list:
    try:
        f = open(fname, "r")
    except:
        print("Error trying to open " + fname + ", exiting")
        exit(1)
    for l in f:
        # Make sure all lines are 80 characters long, extending any shorter ones with spaces
        l = l.rstrip() + " " * (80 - len(l.rstrip()))
        if not l.rstrip() == "JOINT" and l[:5] == "JOINT":
            # JOINT
            if l[54:60] == "ELASTI" and l[6:10] in joints:
                # Elastic spring definition
                joints[l[6:10]].Elastic(l)
            elif l[54:60] == "ELASTI":
                # Spring definition before JOINT
                print(
                    "WARNING: A joint spring is defined before its joint is defined! Skipping...\n"
                )
            else:
                # JOINT geometry definition line
                abq_n += 1
                j = JOINT(l, abq_n)
                joints[j.ID] = j
                nmap.append([j.ABQID, j.ID])
        elif (
            l[:6] == "MEMBER"
            and not l.rstrip() == "MEMBER"
            and not l[7:14] == "OFFSETS"
        ):
            # MEMBER
            m = MEMBER(l)
            members[m.ID] = m
        elif (
            l[:5] == "PLATE" and not l.rstrip() == "PLATE" and not l[7:14] == "OFFSETS"
        ):
            # PLATE
            p = PLATE(l)
            plates[p.ID] = p
        elif not l.rstrip() == "SECT" and l[:4] == "SECT":
            if not l[5:12] in sects:
                # Add this section to sects list
                s = SECT(l)
                sects[s.ID] = s
        elif not l.strip() == "PSTIF" and l[:5] == "PSTIF":
            if not l[10:17].strip() in sects:
                s = PSTIF(l)
                sects[s.ID] = s
        elif not l.rstrip() == "GRUP" and l[:4] == "GRUP":
            # GROUP
            if not l[5:8] in grups:
                # First group line for this group
                g = GRUP(l, "MEMBER")
                grups[g.ID] = g
        elif not l.rstrip() == "PGRUP" and l[:5] == "PGRUP":
            # PLATE GROUP
            if not l[5:8] in pgrups:
                # First group line for this group
                pg = PGRUP(l, "PLATE")
                pgrups[pg.ID] = pg
        elif l[:6] == "LOADCN":
            # NEW LOAD CASE
            load_case = l[7:12].strip()
            loadcases[load_case] = LOADCASE()
        elif l[:6] == "LOADLB":
            # LOAD CASE LABEL
            loadcases[load_case].description = l[6:80]
        elif l[:4] == "LOAD":
            if l[60:64] == "GLOB" and l[65:69] == "JOIN":
                # Point load
                loadcases[load_case].AddLoad(l)
        elif l[:5] == "LCOMB":
            # LOAD COMBINATION
            lc = l[6:10].strip()
            if lc in lcombs:
                # Already defined, so just add loads to this load combo
                lcombs[lc].AddLoads(l)
            else:
                # Create new combo instance and populate with this line
                lcombs[lc] = LCOMB()
                lcombs[lc].AddLoads(l)

    f.close()
print(
    "\nReading complete:\n\t"
    + str(len(joints))
    + " joints were successfully read\n\t"
    + str(len(members))
    + " elements (members) were successfully read"
)

print("\nRemoving elements with length smaller than specified tolerance")
strip_count = 0
for m in members.keys():
    if GetDistance(joints[members[m].jointA], joints[members[m].jointB]) < length_tol:
        strip_count += 1
        # Merge the end joints of this member to retain continuity in the model
        # and record the merge in the nmap list
        nmap[joints[members[m].jointB].ABQID - 1].append(
            "MERGED WITH {}".format(joints[members[m].jointA].ABQID)
        )
        joints[members[m].jointB].ABQID = joints[members[m].jointA].ABQID
print("\n {} members were removed.".format(strip_count))

print("\nIdentifying vertical members")
for m in members:
    if (
        abs((joints[members[m].jointA].x) - (joints[members[m].jointB].x)) <= 0.001
        and abs((joints[members[m].jointA].y) - (joints[members[m].jointB].y)) <= 0.001
    ):
        members[m].vertical = True

print("\nGenerating orphan mesh:")
print("\tWriting nodes to input file...")
try:
    out = open(inp_file, "w")
except:
    print(
        "Error trying to open "
        + inp_file
        + ", check that you have permission to do so. Exiting"
    )
    exit(2)

out.write("*Node, nset=N-AllNodes\n")
for j in sorted(joints.keys()):
    out.write(
        "{}, {}, {}, {}\n".format(
            joints[j].ABQID, joints[j].x, joints[j].y, joints[j].z
        )
    )

print("\tWriting elements to input file...")
elnum = 1
for g in grups:
    out.write("*Element, type={}, elset=MG-{}\n".format(beam_type, g.replace(".", "-")))
    for m in members:
        if members[m].group == g:
            members[m].ABQID = elnum
            out.write(
                "{}, {}, {}\n".format(
                    members[m].ABQID,
                    joints[members[m].jointA].ABQID,
                    joints[members[m].jointB].ABQID,
                )
            )
            elnum += 1
for pg in pgrups:
    for p in plates:
        if plates[p].group == pg:
            plates[p].ABQID = elnum
            if plates[p].jointD == "":
                # 3-element shell
                out.write(
                    "*Element, type=S3, elset=PG-{}\n".format(pg.replace(".", "-"))
                )
                out.write(
                    "{}, {}, {}, {}\n".format(
                        plates[p].ABQID,
                        joints[plates[p].jointA].ABQID,
                        joints[plates[p].jointB].ABQID,
                        joints[plates[p].jointC].ABQID,
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
                j1 = joints[plates[p].jointA]
                j2 = joints[plates[p].jointB]
                j3 = joints[plates[p].jointC]
                j4 = joints[plates[p].jointD]
                pl = OrderJoints((j1, j2, j3, j4))
                out.write(
                    "{}, {}, {}, {}, {}\n".format(
                        elnum, pl[0].ABQID, pl[1].ABQID, pl[2].ABQID, pl[3].ABQID
                    )
                )
            elnum += 1
print("\t Generating Element Sets...")
out.write("****MEMBER ELEMENT SETS****\n")
for m in members:
    out.write(
        "*Elset, elset=M-{}\n{}\n".format(
            members[m].ID.replace(".", "-"), members[m].ABQID
        )
    )
out.write("****PLATE ELEMENT SETS****\n")
for p in plates:
    out.write(
        "*Elset, elset=P-{}\n{}\n".format(
            plates[p].ID.replace(".", "-"), plates[p].ABQID
        )
    )

print("\tWriting beam section assignments to input file...")
out.write("**\n** BEAM SECTIONS **\n")
# Have to assign sections to individual members, not groups, as we can not
# guarentee that all members in a group are vertical or non-vertical, so
# can't give a blanket orientation assignment
for m in members:
    g = members[m].group
    assigned = False
    if g in grups:
        if grups[g].section:
            # This group uses a section definition: get values from that
            try:
                s = sects[grups[g].section]
            except KeyError:
                # This occurs if a SECT is specified in the GRUP, but there
                # is no corresponding SECT definition in the SACS file, so
                # use the section properties from the GRUP line instead.
                s = ""
            except:
                # Unexpected error, log
                log.write(
                    "ERROR: {} when trying to use section of GROUP: {}".format(
                        sys.exc_value, g
                    )
                )
            if s:
                if s.sect in ("ARBITRARY", "CHL", "CON"):
                    log.write(
                        "Members in group {} are assigned ARBITRARY, CHL or CON section; skipping\n".format(
                            g
                        )
                    )
                elif s.sect == "PIPE":
                    out.write(
                        "*Beam Section, elset=M-{}, section={}, material=Mtl-Beam\n".format(
                            m.replace(".", "-"), s.sect
                        )
                    )
                    # Abaqus requires input of outside radii, whereas SACS is in OD
                    if s.C != 0.0 and s.D != 0.0:
                        # Tapered pipe
                        out.write(
                            "{}, {}, {}, {}\n".format(s.A / 2.0, s.B, s.C / 2.0, s.D)
                        )
                    else:
                        # Normal pipe
                        out.write(
                            "{}, {}\n".format(s.A / 2.0, s.B)
                        )  # outside radius, wall thickness
                    assigned = True
                elif s.sect == "I":
                    out.write(
                        "*Beam Section, elset=M-{}, section={}, material=Mtl-Beam\n".format(
                            m.replace(".", "-"), s.sect
                        )
                    )
                    # l, h, b1, b2, t1, t2, t3
                    out.write(
                        "{}, {}, {}, {}, {}, {}, {}\n".format(
                            s.C / 2.0, s.C, s.A, s.A, s.B, s.B, s.D
                        )
                    )
                    assigned = True
                elif s.sect == "TEE":
                    out.write(
                        "*Beam Section, elset=M-{}, section={}, material=Mtl-Beam\n".format(
                            m.replace(".", "-"), "I"
                        )
                    )
                    # l, h, b1, b2, t1, t2, t3 -- set b1 and t1 to zero for t-section
                    out.write(
                        "{}, {}, {}, {}, {}, {}, {}\n".format(
                            s.C / 2.0, s.C, 0.0, s.A, 0.0, s.B, s.D
                        )
                    )
                    assigned = True
                elif s.sect == "BOX":
                    # (z-dim, z-wall thick, y-dim, y-wall thick)
                    # y-width, z-height, y-thk, z-thk, y-thk, z-thk
                    out.write(
                        "*Beam Section, elset=M-{}, section={}, material=Mtl-Beam\n".format(
                            m.replace(".", "-"), s.sect
                        )
                    )
                    out.write(
                        "{}, {}, {}, {}, {}, {}\n".format(s.C, s.A, s.D, s.B, s.D, s.B)
                    )
                    assigned = True
                else:
                    log.write(
                        "Unknown section assignment in group {}, skipping\n.".format(g)
                    )
        else:
            # This group defines its owns sects without a discrete SECT line
            if grups[g].OD != 0.0:
                # Pipe
                out.write(
                    "*Beam Section, elset=M-{}, section={}, material=Mtl-Beam\n".format(
                        m.replace(".", "-"), "PIPE"
                    )
                )
                # Abaqus requires input of outside radii, whereas SACS is in OD
                out.write(
                    "{}, {}\n".format(grups[g].OD / 2, grups[g].thickness)
                )  # outside radius, wall thickness
                assigned = True
            else:
                log.write(
                    "Unable to determine section properties for group {}, skipping.".format(
                        g
                    )
                )
    else:
        # Member group not found, report as error
        missing_sect_members.append(m)
        log.write(
            "No group definition found for member {}, no section can be assigned!".format(
                m.replace(".", "-")
            )
        )
    if assigned:
        if members[m].vertical == True:
            out.write("{}, {}, {}\n".format(1.0, 0.0, 0.0))  # Set local-z to global-x
        else:
            out.write("{}, {}, {}\n".format(0.0, 0.0, 1.0))  # Set local-z to global-z
    else:
        try:
            missing_sect_members.append(m)
            log.write(
                "Missing section assignment for member {} (Group {}, Section ID {})\n".format(
                    m.replace(".", "-"), members[m].group, grups[g].section
                )
            )
        except:
            log.write("** Unhandled error for group {}\n".format(g))
out.write("*Material, name=Mtl-Beam\n*Density\n7850.,\n*Elastic\n2e+11, 0.3\n")

if missing_sect_members:
    out.write("*Elset, elset=ErrMissingSections-Vertical\n")
    for m in missing_sect_members:
        if members[m].vertical:
            out.write("M-{}\n".format(m))
    out.write("*Elset, elset=ErrMissingSections-Other\n")
    for m in missing_sect_members:
        if not members[m].vertical:
            out.write("M-{}\n".format(m))
    print(
        "\n**NOTE: {} members have sections not defined in the SACS or Library files. These are added to sets ErrMissingSections-Vertical and ErrMissingSections-Other\n".format(
            len(missing_sect_members)
        )
    )

print("\tWriting plate section assignments to input file...")
out.write("**\n** PLATE SECTIONS **\n")
for pg in pgrups:
    out.write(
        "*Shell General Section, elset=PG-{}, material={}\n".format(
            pgrups[pg].ID.replace(".", "-"), "Mtl-Plate"
        )
    )
    out.write("{}\n".format(pgrups[pg].thickness))
out.write("*Material, name=Mtl-Plate\n*Density\n7850.,\n*Elastic\n2e+11, 0.3\n")

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
for n in nmap:
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
for m in members:
    elmap.append([members[m].ABQID, m])
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
    for lc in loadcases:
        out.write(
            "**\n** LOAD CASE {}\n** {}\n**\n".format(lc, loadcases[lc].description)
        )
        if loadcases[lc].loads:
            out.write("*Cload\n")
        for l in loadcases[lc].loads:
            for d in range(6):
                out.write(
                    "{}, {}, {}\n".format(joints[l.joint].ABQID, d + 1, l.force[d])
                )
        out.write("*" * 80 + "\n")
    out.write("** COMBINATION LOAD CASES **\n**\n")
    for lcm in lcombs:
        loadset = {}
        for lc in lcombs[lcm].loadcases:
            if lc[0] in loadcases:
                for l in loadcases[lc[0]].loads:
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
                        "{}, {}, {}\n".format(joints[jl].ABQID, i + 1, loadset[jl][i])
                    )
            out.write("*" * 80 + "\n")
except:
    print("Error writing loads, skipping.")
    log.write("**ERROR WRITING LOADS, TERMINATING EARLY\n")
out.close()

log.close()

print("\nConversion complete. Please check .log file for warnings and errors.")

exit(0)

# Temp - convert point loads into point masses
lcm_list = ["A91", "B91", "C91", "D91"]
out = open("point_masses.inp", "w")
mass_num = 1
loadset = {}
for lcm in lcm_list:
    for lc in lcombs[lcm].loadcases:
        if lc[0] in loadcases:
            for l in loadcases[lc[0]].loads:
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
    out.write("{}, {}\n".format(elnum, joints[j].ABQID))
    out.write("*Mass, elset=MASS-{}\n".format(mass_num))
    out.write("{}\n".format(mass))
    mass_num += 1
    elnum += 1
out.close()

os.system("pause")
exit(0)
