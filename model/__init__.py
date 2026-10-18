"""Neural components for executable gap-program discovery."""

from .device import resolve_device
from .program_model import GeneratorProgramNet, ProgramModelOutput

__all__ = ["GeneratorProgramNet", "ProgramModelOutput", "resolve_device"]
