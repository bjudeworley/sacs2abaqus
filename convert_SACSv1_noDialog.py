import os
import sys
import math
import logging

from sacs2abaqus.geom3 import BeamCSys, Vector3
from sacs2abaqus.sacs_cards import *
from sacs2abaqus.inp_writer import *

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


stru = SacsStructure.parse_sacs_file(
    file_list[0], file_list[1] if len(file_list) == 2 else None
)
print(
    "\nReading complete:\n\t"
    + str(len(stru.joints))
    + " joints were successfully read\n\t"
    + str(len(stru.members))
    + " elements (members) were successfully read"
)

print("\nRemoving elements with length smaller than specified tolerance")
stru.merge_small_members()

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
write_node_map(stru, inp_file + "_nmap.txt")

print("\nWriting element number map to " + inp_file + "_elmap.txt...")
write_element_map(stru, inp_file + "_elmap.txt")

print("\nWriting load cases to " + inp_file + "_loads.txt...")
try:
    write_loads(stru, inp_file + "_loads.txt")
except Exception as e:
    print("Error writing loads, skipping.")
    logging.error("**ERROR WRITING LOADS, TERMINATING EARLY: {}\n".format(e))

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
