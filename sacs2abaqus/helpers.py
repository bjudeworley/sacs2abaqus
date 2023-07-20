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
        return float(s)
    except:
        return False
