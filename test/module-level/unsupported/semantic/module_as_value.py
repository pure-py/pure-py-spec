# A module name may be projected (sys.argv) but not used as a value:
# modules are not first-class. PurePy: error; Python: binds the module object.
import sys

z = sys
