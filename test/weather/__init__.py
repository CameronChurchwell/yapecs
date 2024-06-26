###############################################################################
# Configuration
###############################################################################


# Default configuration parameters to be modified
from .config import defaults

# Modify configuration
import yapecs
yapecs.configure('weather', defaults)
del defaults

# Import configuration parameters
from .config.defaults import *
from .config.static import *
