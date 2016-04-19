"""
    Linker utility.
"""

import logging
from .objectfile import ObjectFile, Image
from ..common import CompilerError
from .layout import Layout, Section, SymbolDefinition, Align
from .debuginfo import DebugLocation, DebugVariable, DebugFunction


class Linker:
    """ Merges the sections of several object files and
        performs relocation """
    logger = logging.getLogger('linker')

    def __init__(self, arch, reporter):
        self.arch = arch
        self.reporter = reporter

    def link(self, input_objects, layout, partial_link=False, debug=False):
        """ Link together the given object files using the layout """
        assert isinstance(input_objects, (list, tuple))
        assert isinstance(layout, Layout)

        self.reporter.heading(2, 'Linking')

        # Check all incoming objects for same architecture:
        for input_object in input_objects:
            assert input_object.arch == self.arch

        # Create new object file to store output:
        dst = ObjectFile(self.arch)

        # First merge all sections into output sections:
        self.merge_objects(input_objects, dst, debug)

        # Apply layout rules:
        self.layout_sections(dst, layout)

        if not partial_link:
            self.do_relocations(dst)

        for section in dst.sections:
            self.reporter.message('{} at {}'.format(section, section.address))
        for image in dst.images:
            self.reporter.message('{} at {}'.format(image, image.location))
        dst.polish()
        self.reporter.message('Linking complete')
        return dst

    def merge_objects(self, input_objects, dst, debug):
        """ Merge object files into a single object file """
        for input_object in input_objects:
            offsets = {}
            # Merge sections:
            for input_section in input_object.sections:
                # Get or create the output section:
                output_section = dst.get_section(
                    input_section.name, create=True)

                # Align section:
                while output_section.size % input_section.alignment != 0:
                    output_section.add_data(bytes([0]))

                # Alter the output section alignment if required:
                if input_section.alignment > output_section.alignment:
                    output_section.alignment = input_section.alignment

                # Add new section:
                offset = output_section.size
                offsets[input_section.name] = offset
                output_section.add_data(input_section.data)
                self.logger.debug(
                    '%d %s(%s)', offsets[input_section.name],
                    str(input_object), input_section.name)

            # Merge symbols:
            for sym in input_object.symbols:
                value = offsets[sym.section] + sym.value
                dst.add_symbol(sym.name, value, sym.section)

            # Merge relocations:
            for reloc in input_object.relocations:
                offset = offsets[reloc.section] + reloc.offset
                dst.add_relocation(reloc.sym, offset, reloc.typ, reloc.section)

            # Merge debug info:
            if debug:
                def adj(v):
                    assert isinstance(v, tuple), str(v)
                    return (v[0], offsets[v[0]] + v[1])
                for debug_location in input_object.debug_info.locations:
                    dst.debug_info.add(DebugLocation(
                        debug_location.loc,
                        address=adj(debug_location.address)))
                for debug_function in input_object.debug_info.functions:
                    dst.debug_info.add(DebugFunction(
                        debug_function.name, debug_function.loc,
                        begin=adj(debug_function.begin),
                        end=adj(debug_function.end)))
                for debug_type in input_object.debug_info.types:
                    dst.debug_info.add(debug_type)
                for debug_var in input_object.debug_info.variables:
                    dst.debug_info.add(DebugVariable(
                        debug_var.name, debug_var.typ, debug_var.loc,
                        address=adj(debug_var.address)))

    def layout_sections(self, dst, layout):
        """ Use the given layout to place sections into memories """
        # Create sections with address:
        for mem in layout.memories:
            image = Image(mem.name, mem.location)
            current_address = mem.location
            for memory_input in mem.inputs:
                if isinstance(memory_input, Section):
                    section = dst.get_section(
                        memory_input.section_name, create=True)
                    while current_address % section.alignment != 0:
                        current_address += 1
                    section.address = current_address
                    self.logger.debug(
                        'Memory: {} Section: {} Address: 0x{:X} Size: 0x{:X}'
                        .format(mem.name, section.name,
                                section.address, section.size))
                    current_address += section.size
                    image.add_section(section)
                elif isinstance(memory_input, SymbolDefinition):
                    # Create a new section, and place it at current spot:
                    section_name = '_${}_'.format(memory_input.symbol_name)

                    # Each section must be unique:
                    assert not dst.has_section(section_name)

                    section = dst.get_section(section_name, create=True)
                    section.address = current_address
                    section.alignment = 1
                    dst.add_symbol(memory_input.symbol_name, 0, section_name)
                    image.add_section(section)
                elif isinstance(memory_input, Align):
                    while (current_address % memory_input.alignment) != 0:
                        current_address += 1
                else:  # pragma: no cover
                    raise NotImplementedError(str(memory_input))

            # Check that the memory fits!
            if image.size > mem.size:
                raise CompilerError(
                    'Memory exceeds size ({} > {})'
                    .format(image.size, mem.size))
            dst.add_image(image)

    def do_relocations(self, dst):
        """ Perform the correct relocation as listed """
        for reloc in dst.relocations:
            # Lookup symbol:
            if not dst.has_symbol(reloc.sym):
                raise CompilerError(
                    'Undefined reference "{}"'.format(reloc.sym))

            sym_value = dst.get_symbol_value(reloc.sym)
            section = dst.get_section(reloc.section)

            # Determine location in memory of reloc patchup position:
            reloc_value = section.address + reloc.offset

            f = self.arch.get_reloc(reloc.typ)
            data = section.data[reloc.offset:]
            f(sym_value, data, reloc_value)
            section.data[reloc.offset:] = data
