import copy
from collections import defaultdict
import logging

from .helpers import memberMap, GetFloat
from .geom3 import CSys, Vector3

LENGTH_TOL = 1.0e-6


class SECT:
    def _from_grup(self, grup: "GRUP"):
        self.ID = grup.ID
        self.sect = "PIPE"
        self.AX = None
        self.J = None
        self.IY = None
        self.IZ = None
        self.A = grup.OD
        self.B = grup.thickness
        self.C = False

    # A section as defined from SACS
    def __init__(self, l):
        if isinstance(l, GRUP):
            self._from_grup(l)
            return
        self.ID = l[5:12].strip()
        if l[15:18] in memberMap:
            self.sect = memberMap[l[15:18]]
            self.AX = GetFloat(l[18:24]) * 1e-4 or None  # Convert cm^2 to m^2
            self.J = GetFloat(l[24:32]) * 1e-8 or None  # Convert cm^4 to m^4
            self.IY = GetFloat(l[32:40]) * 1e-8 or None  # Convert cm^4 to m^4
            self.IZ = GetFloat(l[40:48]) * 1e-8 or None  # Convert cm^4 to m^4
            self.A = GetFloat(l[49:55]) * 1e-2  # Convert from cm to m
            self.B = GetFloat(l[55:60]) * 1e-2  # Convert from cm to m
            self.C = GetFloat(l[60:66]) * 1e-2  # Convert from cm to m
            if self.sect == "PRI":
                self.D = GetFloat(l[66:71]) * 1e-4  # Convert from cm^2 to m^2
                self.E = GetFloat(l[71:76]) * 1e-4  # Convert from cm^2 to m^2
            else:
                self.D = GetFloat(l[66:71]) * 1e-2  # Convert from cm to m
                self.E = GetFloat(l[71:76]) * 1e-2  # Convert from cm to m
            if l[15:18] in ("PLG", "TEE", "CHL", "ANG", "CON"):
                # These types have additional datum F
                self.F = GetFloat(l[76:80])
            # Check if any of the stiffness override values are non-blank
            if any(s is not None for s in (self.AX, self.J, self.IZ, self.IZ)):
                print("\t**\tSECT " + self.ID + " has stiffness property overrides!")
        else:
            self.sect = False

    def abaqus_section_defn(self, label: str) -> str:
        FUNCTION_MAP = {
            "PIPE": self._abq_PIPE_section,
            "I": self._abq_I_section,
            "TEE": self._abq_TEE_section,
            "L": self._abq_L_section,
            "CHL": self._abq_CHL_section,
            "ARBITRARY": self._abq_ARBITRARY_section,
            "BOX": self._abq_BOX_section,
        }
        LABEL_MAP = {"TEE": "I", "CHL": "CHANNEL", "ARBITRARY": "GENERAL"}
        GENERAL_SECTIONS = ["CHL", "ARBITRARY"]

        abq_section = LABEL_MAP.get(self.sect, self.sect)
        if self.sect in GENERAL_SECTIONS:
            header = "*Beam General Section, elset=M-{}, section={}, material=Mtl-Beam\n".format(
                label.replace(".", "-"), abq_section
            )
        else:
            header = (
                "*Beam Section, elset=M-{}, section={}, material=Mtl-Beam\n".format(
                    label.replace(".", "-"), abq_section
                )
            )
        return header + FUNCTION_MAP[self.sect]()

    def to_dict(self) -> dict:
        FUNCTION_MAP = {
            "PIPE": self._int_PIPE_dict,
            "I": self._int_I_dict,
            "TEE": self._int_TEE_dict,
            "L": self._int_L_dict,
            "CHL": self._int_CHL_dict,
            "ARBITRARY": self._int_ARBITRARY_dict,
            "BOX": self._int_BOX_dict,
        }
        return FUNCTION_MAP[self.sect]()

    # region ABQ_SECTION
    def _abq_PIPE_section(self) -> str:
        # Abaqus requires input of outside radii, whereas SACS is in OD
        if self.C != 0.0 and self.D != 0.0:
            # Tapered pipe
            return "{}, {}, {}, {}\n".format(self.A / 2.0, self.B, self.C / 2.0, self.D)
        else:
            # Normal pipe
            # outside radius, wall thickness
            return "{}, {}\n".format(self.A / 2.0, self.B)

    def _abq_I_section(self) -> str:
        # l, h, b1, b2, t1, t2, t3
        definition = "{}, {}, {}, {}, {}, {}, {}\n".format(
            self.C / 2.0, self.C, self.A, self.A, self.B, self.B, self.D
        )
        return definition

    def _abq_TEE_section(self) -> str:
        # l, h, b1, b2, t1, t2, t3 -- set b1 and t1 to zero for t-section
        definition = "{}, {}, {}, {}, {}, {}, {}\n".format(
            self.A / 2.0, self.A, 0.0, self.B, 0.0, self.D, self.C
        )
        return definition

    def _abq_L_section(self) -> str:
        # a, b, t1, t2
        definition = "{}, {}, {}, {}\n".format(self.B, self.A, self.C, self.C)
        return definition

    def _abq_CHL_section(self) -> str:
        # l, h, b1, b2, t1, t2, t3
        definition = "{}, {}, {}, {}, {}, {}, {}\n".format(
            self.A / 2, self.A, self.B, self.B, self.D, self.D, self.C
        )
        return definition

    def _abq_ARBITRARY_section(self) -> str:
        # A, I11, I12, I22, J, gamma0, gammaW -- gammas are optional
        definition = "{}, {}, {}, {}, {}\n".format(
            self.AX, self.IY, 0.0, self.IZ, self.J
        )
        return definition

    def _abq_BOX_section(self) -> str:
        # (z-dim, z-wall thick, y-dim, y-wall thick)
        # y-width, z-height, y-thk, z-thk, y-thk, z-thk
        definition = "{}, {}, {}, {}, {}, {}\n".format(
            self.C, self.A, self.D, self.B, self.D, self.B
        )
        return definition

    # endregion
    # region INT_DICT
    def _int_PIPE_dict(self) -> dict:
        # Abaqus requires input of outside radii, whereas SACS is in OD
        if self.C != 0.0 and self.D != 0.0:
            # Tapered pipe
            return {
                "type": "TAPER_PIPE",
                "radius1": self.A / 2,
                "t1": self.B,
                "radius2": self.C / 2,
                "t2": self.D,
            }
        else:
            # Normal pipe
            # outside radius, wall thickness
            return {"type": "PIPE", "radius": self.A / 2, "t": self.B}

    def _int_I_dict(self) -> dict:
        # l, h, b1, b2, t1, t2, t3
        return {
            "type": "I",
            "offset": self.C / 2.0,
            "h": self.C,
            "bf_bot": self.A,
            "bf_top": self.A,
            "tf_bot": self.B,
            "tf_top": self.B,
            "tw": self.D,
        }

    def _int_TEE_dict(self) -> dict:
        # l, h, b1, b2, t1, t2, t3 -- set b1 and t1 to zero for t-section
        return {
            "type": "TEE",
            "offset": self.A / 2.0,
            "h": self.A,
            "bf": self.B,
            "tf": self.D,
            "tw": self.C,
        }

    def _int_L_dict(self) -> dict:
        # a, b, t1, t2
        return {
            "type": "L",
            "bf": self.B,
            "h": self.A,
            "tf": self.C,
            "tw": self.C,
        }

    def _int_CHL_dict(self) -> dict:
        return {
            "type": "CHL",
            "offset": self.A / 2,
            "h": self.A,
            "bf_bot": self.B,
            "bf_top": self.B,
            "tf_bot": self.D,
            "tf_top": self.D,
            "tw": self.C,
        }

    def _int_ARBITRARY_dict(self) -> dict:
        return {
            "type": "ARBITRARY",
            "area": float(self.AX),
            "I11": float(self.IY),
            "I12": 0.0,
            "I22": float(self.IZ),
            "J": float(self.J),
        }

    def _int_BOX_dict(self) -> dict:
        return {"type": "BOX", "bf": self.C, "h": self.A, "tw": self.D, "tf": self.D}

    # endregion


class PSTIF(SECT):
    # Section definition for a plate stiffener
    def __init__(self, line):
        assert line.startswith("PSTIF")
        sacs_section_type = line[6:9].strip()
        assert sacs_section_type == "ANG", "Only ANG stiffeners are currently supported"
        self.sect = memberMap[sacs_section_type]
        self.ID = line[10:17].strip()
        # Height
        self.A = GetFloat(line[20:27]) * 1e-2  # Convert from cm to m
        # Flange Width
        self.B = GetFloat(line[34:41]) * 1e-2  # Convert from cm to m
        # Web Thickness. Note that Stiffener sections can have different flange
        # and web thickness, whereas a standard SECT card cannot for ANG sections.
        # TODO: Make sure the section output can handle this
        self.C = GetFloat(line[41:48]) * 1e-2
        # Flange Thickness
        self.D = GetFloat(line[55:62]) * 1e-2

    def _abq_L_section(self) -> str:
        # a, b, t1, t2
        definition = "{}, {}, {}, {}\n".format(self.B, self.A, self.D, self.C)
        return definition

    def to_dict(self) -> dict:
        # a, b, t1, t2
        return {
            "type": "L",
            "offset": self.A,
            "bf": self.B,
            "h": self.A,
            "tf": self.D,
            "tw": self.C,
        }


class PGRUP:
    # A plate group as defined from SACS
    # Note that this includes the section properties of the plate, as there
    # are no SECT lines for plates.
    def __init__(self, l, eltype):
        # PLATE sects and groups are defined together on the PGRUP line
        self.ID = l[6:9].strip()
        # Neutral axis offset
        self.NA = l[9]
        # Convert from cm to m
        self.thickness = GetFloat(l[10:16]) * 1e-2
        # PLATE section - (I=Isotropic, M=Membrane, S=Shear Stiff Only, X=x-dir corrugated, Y=y-dir corrugated)
        self.sect = l[16]
        # Modulus, convert from kN/cm^2 to Pa
        self.E = GetFloat(l[17:23]) * 1e10
        # Poisson's ratio
        self.v = GetFloat(l[23:29])
        # Yield stress, convert from kN/cm^2 to Pa
        self.FY = GetFloat(l[29:35]) * 1e7
        # Local z-offset, convert from cm to m
        self.Zoffset = GetFloat(l[35:41]) * 1e-2
        # Stiffener section
        self.stiffener_section = l[41:48].strip()
        # Stiffener spacing, convert from cm to m
        self.stiffener_spacing = GetFloat(l[48:54]) * 1e-2
        # Stiffener direction (X or Y) and placement (T or B)
        self.stiffener_direction = l[54]
        self.stiffener_placement = l[55]
        # Set all stiffener properties to None if no stiffener present
        if not self.stiffener_section:
            self.stiffener_section = None
            self.stiffener_spacing = None
            self.stiffener_direction = None
            self.stiffener_placement = None
        # Stiffening plates not included
        self.density = GetFloat(l[72:80]) * 1e3  # Convert from t/m^3 to kg/m^3

    def to_material_dict(self):
        return {
            "youngs": self.E,
            "poisson": self.v,
            "yield": self.FY,
            "density": self.density,
        }


class GRUP:
    # A member group as defined from SACS
    def __init__(self, l, eltype):
        self.ID = l[5:8].strip()
        try:
            if l[8] == " ":
                self.taper = False
            else:
                self.taper = l[8]
            self.section = l[9:16].strip()
            self.redesign = l[16]
            self.OD = GetFloat(l[17:23]) * 1e-2  # Convert from cm to m
            self.thickness = GetFloat(l[23:29]) * 1e-2  # Convert from cm to m
            self.gap = l[29]
            self.E = GetFloat(l[30:35]) * 1e10
            self.G = GetFloat(l[35:40]) * 1e10
            self.FY = GetFloat(l[40:45]) * 1e7
            self.memberClass = l[46]
            self.jointThickness = GetFloat(l[47:51])
            self.KY = GetFloat(l[51:55])
            self.KZ = GetFloat(l[55:59])
            self.spacing = GetFloat(l[59:64])
            self.shearMod = GetFloat(l[64:69])
            self.flooding = l[69]
            self.density = GetFloat(l[70:76]) * 1e3  # Convert from t/m^3 to kg/m^3
            self.segLength = GetFloat(l[76:80])
        except:
            pass

    def to_material_dict(self):
        poisson = self.E / (2 * self.G) - 1
        return {
            "youngs": self.E,
            "poisson": poisson,
            "yield": self.FY,
            "density": self.density,
        }


class MEMBER:
    # A member as defined from SACS
    def __init__(self, l):
        self.offset = l[6]
        self.jointA = l[7:11].strip()
        self.jointB = l[11:15].strip()
        self.ID = self.jointA + self.jointB
        self.vertical = False  # Initialise
        self.ABQID = -1  # Initialise
        try:
            self.addData = l[15]
            self.group = l[16:19].strip()
            self.stressOutput = l[19:21]
            self.gap = l[21]
            self.fixityA = [f == "1" for f in l[22:28]]  # True = free, False = fixed
            self.fixityB = [f == "1" for f in l[28:34]]  # True = free, False = fixed
            self.chordAngle = GetFloat(l[35:41])
            self.Zref = l[41:45]
            self.flood = l[45]
            self.KorL = l[46]
            self.thickness = l[47:51]
            self.KY = l[51:55]
            self.KZ = l[55:59]
            self.unbracedLength = l[59:64]
            self.density = GetFloat(l[64:70]) * 1e3  # Convert from t/m^3 to kg/m^3
            self.segments = int(GetFloat(l[70:72]))
            self.effectiveDiameter = GetFloat(l[72:78]) * 1e-2  # Convert from cm to m
        except:
            pass

    def local_csys(self, joints: dict[str, "JOINT"]) -> CSys:
        start = joints[self.jointA].as_vector()
        end = joints[self.jointB].as_vector()
        beam_csys = CSys.from_beam_ends(start, end)
        if self.chordAngle:
            beam_csys = beam_csys.rotated_about_x(self.chordAngle)
        return beam_csys


class PLATE:
    # A plate as defined by SACS; can connect either 3 or 4 joints
    def __init__(self, l):
        self.ID = l[6:10]
        self.ABQID = -1  # Initialise
        try:
            # NOTE: local coords defined as follows:
            #  X: joint_b - joint_a
            #  Y: In the plane of X and (joint_c - joint_a), normal to X
            #  Z: cross product of X and Y
            self.jointA = l[11:15].strip()  # SACS IDs of connecting joints
            self.jointB = l[15:19].strip()
            self.jointC = l[19:23].strip()
            self.jointD = l[23:27].strip()  # Stripped so we get '' if no jointD
            self.group = l[27:30].strip()
            self.SK = l[30:32]
            self.thickness = GetFloat(l[32:38]) * 1e-2  # Convert from cm to m
            self.offsetOption = l[42]  # '1' for global coords, '2' for local
            # Modulus - convert from 1000 kN/cm^2 to Pa
            self.E = GetFloat(l[47:54]) * 1e10
            self.v = GetFloat(l[54:59])  # Poisson's ratio
            # Yield stress - convert from kN/cm^2 to Pa
            self.FY = GetFloat(l[59:64]) * 1e7
            # Seastate weight density - convert from t/m^3 to kg/m^3
            self.density = GetFloat(l[69:74]) * 1e3
            self.remarks = l[74:80]
        except:
            pass

    def centroid(self, joints: list["JOINT"]) -> Vector3:
        pts = [
            joints[j].as_vector()
            for j in (
                [self.jointA, self.jointB, self.jointC]
                + ([self.jointD] if self.jointD else [])
            )
        ]
        return sum(pts, start=Vector3(0, 0, 0)) / len(pts)

    def local_csys(self, joints: list["JOINT"]) -> CSys:
        local_x = joints[self.jointB].as_vector() - joints[self.jointA].as_vector()
        local_y = joints[self.jointC].as_vector() - joints[self.jointA].as_vector()
        local_z = local_x.cross(local_y)
        local_y = local_z.cross(local_x)
        return CSys(local_x, local_y, local_z)


class LCOMB:
    # Load combinations
    def __init__(self):
        self.loadcases = []

    def AddLoads(self, l):
        # Add loads to this load combination
        for loadcase_name, loadcase_factor in (
            (l[11:15], l[15:21]),
            (l[21:25], l[25:31]),
            (l[31:35], l[35:41]),
            (l[41:45], l[45:51]),
            (l[51:55], l[55:61]),
            (l[61:65], l[65:71]),
        ):
            if loadcase_name.strip():
                self.loadcases.append(
                    (loadcase_name.strip(), GetFloat(loadcase_factor))
                )

    def to_basic(
        self, loadcases: dict[str, "LOADCASE"], lcombs: dict[str, "LCOMB"]
    ) -> "LOADCASE":
        case = LOADCASE()
        for lc, factor in self.loadcases:
            if lc in loadcases:
                for load in loadcases[lc].loads:
                    case.loads.append(load.scale(factor))
            elif lc in lcombs:
                for load in lcombs[lc].to_basic(loadcases, lcombs).loads:
                    case.loads.append(load.scale(factor))
            else:
                logging.warning("Could not find Load Case {}".format(lc))
        return case


class LOADCASE:
    # Load container
    def __init__(self):
        self.description = ""
        self.loads = []

    def AddLoad(self, l):
        # Add info from new LOAD line
        self.loads.append(LOAD(l))


class LOAD:
    # Load line as taken from SACS
    def __init__(self, l):
        self.load_type = l[65:69]
        self.load_csys = l[60:64]
        if self.load_csys == "GLOB":
            if self.load_type == "JOIN":
                self.type = "joint"
                self.joint = l[7:11].strip()
                self.load = []
                # Add forces (convert from kN to N)
                self.load.append(GetFloat(l[16:23]) * 1e3)
                self.load.append(GetFloat(l[23:30]) * 1e3)
                self.load.append(GetFloat(l[30:37]) * 1e3)
                self.load.append(GetFloat(l[37:44]) * 1e3)
                self.load.append(GetFloat(l[45:52]) * 1e3)
                self.load.append(GetFloat(l[52:59]) * 1e3)
            else:
                assert self.load_type == "UNIF"
                self.type = "beam"
                self.dirn = l[5]
                self.beam = l[7:15]
                self.start_offset = GetFloat(l[16:23]) or 0
                self.load_length = GetFloat(l[30:37]) or 0
                # Get line loads (convert from kN/m to N/m)
                self.load = [GetFloat(l[23:30]) * 1e3, GetFloat(l[37:44]) * 1e3]
        elif self.load_csys == "PRES":
            self.type = "pressure"
            self.plate = l[7:11].strip()
            # Get pressure (convert from kN/m^2 to N/m^2)
            self.load = GetFloat(l[16:23]) * 1e3
            if l[5] == "-":
                # Convert all pressures to positive face
                self.load *= -1
        else:
            logging.info("Unknown load type {}".format(l))
        self.remarks = l[72:80].strip()

    def scale(self, factor: float) -> "LOAD":
        out = copy.deepcopy(self)
        if self.type == "joint" or self.type == "beam":
            out.load = [factor * l for l in out.load]
        else:
            assert self.type == "pressure"
            out.load *= factor
        return out

    def to_dict(self):
        if self.type == "joint":
            return {"joint": self.joint, "load": self.load, "label": self.remarks}
        elif self.type == "beam":
            return {
                "beam": self.beam,
                "load": self.load,
                "start_offset": self.start_offset,
                "load_length": self.load_length,
            }
        elif self.type == "pressure":
            return {
                "plate": self.plate,
                "load": self.load,
            }


class Spring:
    # Container for organisation of JOINT Spring parameters
    pass


class JOINT:
    # A joint as defined from SACS
    def __init__(self, l, abq_n):
        self.ABQID = abq_n  # Abaqus node number - integer
        self.ID = l[6:10].strip()
        self.x = GetFloat(l[11:18]) + GetFloat(l[32:39]) * 1e-2
        self.y = GetFloat(l[18:25]) + GetFloat(l[39:46]) * 1e-2
        self.z = GetFloat(l[25:32]) + GetFloat(l[46:53]) * 1e-2
        try:
            self.fixity = [f == "1" for f in l[54:60]]  # true = free, false = fixed
            self.remarks = l[61:69]
        except:
            pass

    def Elastic(self, l):
        # If the SACS input has 'ELASTI' in l[54:60] then it's an elastic spring definition
        # and we should add it to the existing JOINT instance
        self.spring = Spring()
        # Convert kg/cm to N/m
        disp_rates = [GetFloat(x) * 1e3 for x in (l[11:18], l[18:25], l[25:32])]
        # Convert kg.cm/rad to N.m/rad
        rot_rates = [GetFloat(x) * 0.1 for x in (l[32:39], l[39:46], l[46:53])]
        self.spring.rates = disp_rates + rot_rates  # [dx, dy, dz, rx, ry, rz]
        self.spring.comments = l[61:69]
        # Support coord sys orientation joint. Defines x-axis line.
        self.spring.joint2 = l[72:76].strip()
        # Support coord sys orientation joint. Defines x-z plane.
        self.spring.joint3 = l[76:80].strip()

    def as_vector(self) -> Vector3:
        return Vector3(self.x, self.y, self.z)


class SacsStructure:
    members: dict[str, MEMBER] = {}
    plates: dict[str, PLATE] = {}
    grups: dict[str, GRUP] = {}
    pgrups: dict[str, PGRUP] = {}
    sects: dict[str, SECT] = {}
    joints: dict[str, JOINT] = {}
    nmap: list[tuple[int, str]] = []
    abq_n = 0
    lcombs: dict[str, LCOMB] = {}
    loadcases: dict[str, LOADCASE] = {}
    load_case = ""
    missing_sect_members: list[MEMBER] = []

    @staticmethod
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
                        if not g.section:
                            # Section properties defined in GRUP, not SECT.
                            # Create a section object for this section
                            s = SECT(g)
                            stru.sects[s.ID] = s
                            g.section = s.ID
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
                elif l.strip() != "LOAD" and l[:4] == "LOAD":
                    load_type = (l[60:64], l[65:69])
                    if load_type in [
                        ("GLOB", "JOIN"),
                        ("GLOB", "UNIF"),
                        ("PRES", "UNIF"),
                    ]:
                        # Point load
                        stru.loadcases[stru.load_case].AddLoad(l)
                    else:
                        print(
                            "Unknown load type: {} {}".format(
                                load_type[0], load_type[1]
                            )
                        )
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

    def merge_small_members(self) -> None:
        strip_count = 0
        for m in self.members.keys():
            jA = self.joints[self.members[m].jointA].as_vector()
            jB = self.joints[self.members[m].jointB].as_vector()
            if (jA - jB).length() < LENGTH_TOL:
                strip_count += 1
                # Merge the end joints of this member to retain continuity in the model
                # and record the merge in the nmap list
                self.nmap[self.joints[self.members[m].jointB].ABQID - 1].append(
                    "MERGED WITH {}".format(self.joints[self.members[m].jointA].ABQID)
                )
                self.joints[self.members[m].jointB].ABQID = self.joints[
                    self.members[m].jointA
                ].ABQID
        print("\n {} members were removed.".format(strip_count))

    def to_dict(self, mass_loadcase: str = None):
        joints = {
            name: {"position": (joint.x, joint.y, joint.z)}
            for name, joint in self.joints.items()
        }
        # Get all the materials from grups and plate grups. Since we have
        # significant duplication we then gather all grups/pgrups with identical
        # properties and map them to the same material for export. This also needs
        # a dict to map from SACS name to our new unique material name
        sacs_materials = {
            name: pgrup.to_material_dict() for name, pgrup in self.pgrups.items()
        } | {name: grup.to_material_dict() for name, grup in self.grups.items()}
        # Deduplicate materials
        materials = defaultdict(list)
        for name, props in sacs_materials.items():
            materials[
                tuple(props[x] for x in ["youngs", "poisson", "yield", "density"])
            ].append(name)
        # Build the name map
        material_map = {}
        for i, grups in enumerate(materials.values()):
            material_map |= {g: f"Material_{i + 1}" for g in grups}
        materials = {
            f"Material_{i + 1}": {"youngs": e, "poisson": v, "yield": fy, "density": rho}
            for i, (e, v, fy, rho) in enumerate(materials.keys())
        }
        members = {
            name: {
                "jointA": joints[mem.jointA],
                "jointB": joints[mem.jointB],
                "section": self.grups[mem.group].section,
                "local_x": mem.local_csys(self.joints).x.as_tuple(),
                "local_y": mem.local_csys(self.joints).y.as_tuple(),
                "local_z": mem.local_csys(self.joints).z.as_tuple(),
                "material": material_map[mem.group]
            }
            for name, mem in self.members.items()
        }
        plates = {
            name: {
                "centroid": pl.centroid(self.joints).as_tuple(),
                "thickness": round(self.pgrups[pl.group].thickness, 5),
                "local_x": pl.local_csys(self.joints).x.as_tuple(),
                "local_y": pl.local_csys(self.joints).y.as_tuple(),
                "local_z": pl.local_csys(self.joints).z.as_tuple(),
                "material": material_map[pl.group]
            }
            for name, pl in self.plates.items()
        }
        profiles = {name: sect.to_dict() for name, sect in self.sects.items()}
        if mass_loadcase is not None:
            masses = [
                load.to_dict()
                for load in (
                    self.loadcases[mass_loadcase].loads
                    if mass_loadcase in self.loadcases
                    else self.lcombs[mass_loadcase]
                    .to_basic(self.loadcases, self.lcombs)
                    .loads
                )
            ]
        else:
            masses = {}
        return {
            "joints": joints,
            "members": members,
            "plates": plates,
            "profiles": profiles,
            "masses": masses,
            "materials": materials,
        }
