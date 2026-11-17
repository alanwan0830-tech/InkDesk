Import('env')
from SCons.Script import COMMAND_LINE_TARGETS
if any('upload' in target or 'erase' in target for target in COMMAND_LINE_TARGETS):
    raise RuntimeError('Build only: review backup, active OTA slot and installation plan before flashing.')
