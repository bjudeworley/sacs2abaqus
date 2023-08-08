import math

from .geom3 import Vector3

# Maps of SACS section definitions to ABQ section definitions
memberMap = {
    "TUB": "PIPE",  # Tubular or pipe
    "WF ": "I",  # Wide flange
    "WFC": "I",  # Wide flange compact
    "PGB": "BOX",  # (Not in SACS manual; derived)
    "BOX": "BOX",  # Rectangular box
    "PRI": "ARBITRARY",  # General prismatic shape
    "PLG": "I",  # PLATE girder section
    "TEE": "TEE",  # Tee section
    "CHL": "CHL",  # Channel cross section
    "ANG": "L",  # Angle cross section
    "CON": "CON",  # Conical transition section
    "SCY": "PIPE",  # Stiffened cylindrical section
    "SBX": "BOX",  # Stiffened box section
}


def GetFloat(s):
    """
    Attempts to convert a string to a float. Returns False if there is an error
    """
    try:
        # Handle scientific notation in SACS.
        # SACS records a number like 1.23e-2 as "1.23-2" so we need to replace
        # the final "-" by "E-" for python to parse it correctly. Simply doing a
        # string replace can fail in the case of a negative number, where both
        # the negative sign for the number and the exponent will be replaced.
        # Here we take the leading "-" off if it is present, do a string
        # replacement and then merge them again.
        s = s.strip()
        prefix, s = ("-", s[1:]) if s.startswith('-') else ("", s)
        s = prefix + s.replace("-", "E-")
        return float(s)
    except ValueError:
        return False

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
