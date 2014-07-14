
"""
Defines task classes that can compile, link etc..
Task can depend upon one another.
"""

from .tasks import Task, TaskError, register_task
from .buildfunctions import c3compile, link, assemble, fix_object, construct
from pyyacc import ParserException
from . import CompilerError


@register_task("empty")
class EmptyTask(Task):
    """ Basic task that does nothing """
    def run(self):
        pass


@register_task("echo")
class EchoTask(Task):
    """ Simple task that echoes a message """
    def run(self):
        message = self.arguments['message']
        print(message)


@register_task("property")
class Property(Task):
    """ Sets a property to a value """
    def run(self):
        name = self.arguments['name']
        value = self.arguments['value']
        self.target.project.set_property(name, value)


@register_task("build")
class ConstructTask(Task):
    """ Builds another build description file (build.xml) """
    def run(self):
        project = self.get_argument('file')
        construct(project)


@register_task("assemble")
class AssembleTask(Task):
    """ Task that can runs the assembler over the source and enters the
        output into an object file """

    def run(self):
        target = self.get_argument('target')
        source = self.relpath(self.get_argument('source'))
        output_filename = self.relpath(self.get_argument('output'))

        try:
            output = assemble(source, target)
        except ParserException as e:
            raise TaskError('Error during assembly:' + str(e))
        except CompilerError as e:
            raise TaskError('Error during assembly:' + str(e))
        except OSError as e:
            raise TaskError('Error:' + str(e))
        with open(output_filename, 'w') as f:
            output.save(f)
        self.logger.debug('Assembling finished')


@register_task("compile")
class C3cTask(Task):
    """ Task that compiles C3 source for some target into an object file """
    def run(self):
        target = self.get_argument('target')
        sources = self.open_file_set(self.arguments['sources'])
        output_filename = self.relpath(self.get_argument('output'))
        if 'includes' in self.arguments:
            includes = self.open_file_set(self.arguments['includes'])
        else:
            includes = []

        output = c3compile(sources, includes, target)
        # Store output:
        with open(output_filename, 'w') as output_file:
            output.save(output_file)


@register_task("link")
class LinkTask(Task):
    """ Link together a collection of object files """
    def run(self):
        layout = self.relpath(self.get_argument('layout'))
        target = self.get_argument('target')
        objects = self.open_file_set(self.get_argument('objects'))
        output_filename = self.relpath(self.get_argument('output'))

        try:
            output_obj = link(objects, layout, target)
        except CompilerError as e:
            raise TaskError(e.msg)

        # Store output:
        with open(output_filename, 'w') as output_file:
            output_obj.save(output_file)


@register_task("objcopy")
class ObjCopyTask(Task):
    def run(self):
        image_name = self.get_argument('imagename')
        output_filename = self.relpath(self.get_argument('output'))
        object_filename = self.relpath(self.get_argument('objectfile'))

        obj = fix_object(object_filename)
        image = obj.get_image(image_name)
        with open(output_filename, 'wb') as output_file:
            output_file.write(image)