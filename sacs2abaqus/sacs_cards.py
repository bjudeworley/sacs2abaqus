from .helpers import memberMap, GetFloat


class SECT:
    # A section as defined from SACS
    def __init__(self, l):
        self.ID = l[5:12]
        if l[15:18] in memberMap:
            self.sect = memberMap[l[15:18]]
            self.AX = l[18:24]
            self.J = l[24:32]
            self.IY = l[32:40]
            self.IZ = l[40:48]
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
            if False in [
                s == " " * len(s) for s in (self.AX, self.J, self.IZ, self.IZ)
            ]:
                print("\t**\tSECT " + self.ID + " has stiffness property overrides!")
        else:
            self.sect = False


class PSTIF(SECT):
    # Section definition for a plate stiffener
    def __init__(self, line):
        assert line.startswith("PSTIF")
        sacs_section_type = line[6:9]
        assert sacs_section_type == "ANG", "Only ANG stiffeners are currently supported"
        self.sect = memberMap[sacs_section_type]
        self.ID = line[10:17]
        # Height
        self.A = GetFloat(line[20:27]) * 1e-2  # Convert from cm to m
        # Flange Width
        self.B = GetFloat(line[34:41]) * 1e-2  # Convert from cm to m
        # Web Thickness. Note that Stiffener sections can have different flange
        # and web thickness, whereas a standard SECT card cannot for ANG sections.
        # TODO: Make sure the section output can handle this
        self.C = GetFloat(line[41:48])
        # Flange Thickness
        self.D = GetFloat(line[55:62])


class PGRUP:
    # A plate group as defined from SACS
    # Note that this includes the section properties of the plate, as there
    # are no SECT lines for plates.
    def __init__(self, l, eltype):
        # PLATE sects and groups are defined together on the PGRUP line
        self.ID = l[6:9]
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


class GRUP:
    # A member group as defined from SACS
    def __init__(self, l, eltype):
        self.ID = l[5:8].strip()
        try:
            if l[8] == " ":
                self.taper = False
            else:
                self.taper = l[8]
            self.section = l[9:16]
            # If section is blank, compress to '' so it evaluates to False (this)
            # means the section is defined in the GRUP line, not by a SECT line)
            if self.section.strip() == "":
                self.section = ""
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


class PLATE:
    # A plate as defined by SACS; can connect either 3 or 4 joints
    def __init__(self, l):
        self.ID = l[6:10]
        self.ABQID = -1  # Initialise
        try:
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
        self.joint = l[7:11].strip()
        self.force = []
        # Add forces (convert from kN to N)
        self.force.append(GetFloat(l[16:23]) * 1e3)
        self.force.append(GetFloat(l[23:30]) * 1e3)
        self.force.append(GetFloat(l[30:37]) * 1e3)
        self.force.append(GetFloat(l[37:44]) * 1e3)
        self.force.append(GetFloat(l[45:52]) * 1e3)
        self.force.append(GetFloat(l[52:59]) * 1e3)
        self.remarks = l[72:80]


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
