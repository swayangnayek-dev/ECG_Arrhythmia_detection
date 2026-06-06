# Mapping MIT-BIH symbols to AAMI standard classes

# Class definitions
CLASS_NORMAL = 0
CLASS_AFIB = 1
CLASS_PVC = 2

# MIT-BIH uses characters to denote the beat type or rhythm change
# AAMI standard groups:
# N: Normal, LBBB, RBBB, atrial escape, nodal escape
# V: Premature ventricular contraction, ventricular escape beat
# S: Premature or ectopic supraventricular beat (Not tracked specifically, usually merged with Normal or distinct)
# F: Fusion of ventricular and normal beat
# Q: Unclassifiable

MIT_BIH_TO_AAMI = {
    'N': CLASS_NORMAL,
    'L': CLASS_NORMAL,
    'R': CLASS_NORMAL,
    'e': CLASS_NORMAL,
    'j': CLASS_NORMAL,
    
    'V': CLASS_PVC,
    'E': CLASS_PVC,
    
    # Note: AFib is typically a rhythm annotation (+), not a single beat symbol.
    # We map it during segment windowing by checking the 'aux_note' field.
}

def get_class_for_symbol(symbol: str) -> int:
    """
    Returns the mapped class for a given MIT-BIH beat symbol.
    Returns -1 if unmapped/ignored.
    """
    return MIT_BIH_TO_AAMI.get(symbol, -1)
