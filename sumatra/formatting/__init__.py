"""
The formatting module provides classes for formatting simulation/analysis
records in different ways: summary, list or table; and in different mark-up
formats: currently text or HTML.


:copyright: Copyright 2006-2014 by the Sumatra team, see doc/authors.txt
:license: CeCILL, see LICENSE for details.
"""

import textwrap
import cgi
import re
import operator

fields = ['label', 'timestamp', 'reason', 'outcome', 'duration', 'repository',
          'main_file', 'version', 'script_arguments', 'executable',
          'parameters', 'input_data', 'launch_mode', 'output_data',
          'user', 'tags', 'repeats']


class Formatter(object):

    def __init__(self, records, project=None, tags=None):
        self.records = records
        self.project = project
        self.tags = None

    def format(self, mode='short', keyword=None):
        """
        Format a record according to the given mode. ``mode`` may be 'short',
        'long' or 'table'.
        """
        return getattr(self, mode)


class TextFormatter(Formatter):
    """
    Format the information from a list of Sumatra records as text.
    """

    def short(self):
        """Return a list of record labels, one per line."""
        return "\n".join(record.label for record in self.records)

    def long(self, text_width=80, left_column_width=17):
        """
        Return detailed information about a list of records, as text with a
        limited column width. Lines that are too long will be wrapped round.
        """
        output = ""
        for record in self.records:
            output += "-" * text_width + "\n"
            left_column = []
            right_column = []
            for field in fields:
                left_column.append("%s%ds" % ("%-", left_column_width) % field.title())
                entry = getattr(record, field)
                if hasattr(entry, "pretty"):
                    new_lines = entry.pretty().split("\n")
                else:
                    if callable(entry):
                        entryStr = str(entry())
                    elif hasattr(entry, "items"):
                        entryStr = ", ".join(["%s=%s" % item for item in entry.items()])
                    elif isinstance(entry, set):
                        entryStr = ", ".join(entry)
                    else:
                        entryStr = str(entry)
                        if field == 'version' and getattr(record, 'diff'):
                            # if there is a diff, append '*' to the version
                            entryStr += "*"
                    entry_lines = entryStr.split("\n")
                    new_lines = []
                    for entry_line in entry_lines:
                        new_lines.extend(
                            textwrap.wrap(entry_line, width=text_width, replace_whitespace=False))
                if len(new_lines) == 0:
                    new_lines = ['']
                right_column.extend(new_lines)
                if len(new_lines) > 1:
                    left_column.extend([' ' * left_column_width] * (len(new_lines) - 1))
                #import pdb; pdb.set_trace()
            for left, right in zip(left_column, right_column):
                output += left + ": " + right + "\n"
        return output

    def table(self):
        """
        Return information about a list of records as text, in a simple
        tabular format.
        """
        tt = TextTable(fields, self.records)
        return str(tt)

    def params_show(self):
        """ Return parameter information about a list of records as text, in a simple tabular format."""
        tt = ParamsTable(self.records, seperator='|')
        return str(tt)

#    def params_filter(self):
#        """ Return parameter information about a list of records as text, in a simple tabular format."""
#        tt = ParamsTable(self.records, seperator='|')
#        return str(tt)

    def keyword(self, keyword=None):
        """Return a list of record labels plus one content of the record, one per line."""
        return "\n".join("%s\t%s" %(record.label, str(getattr(record, keyword))) for record in self.records if hasattr(record, keyword))

    def output_files(self):
        """Return a list of record files, one per line."""
        a = [[f.path for f in r.output_data] for r in self.records]
        return '\n'.join(reduce(operator.add, a))


class TextTable(object):
    """
    Very primitive implementation of a text table. There are more sophisticated
    implementations around, e.g. http://pypi.python.org/pypi/texttable/0.6.0/
    but for now I'd like to avoid too many dependencies.
    """

    def __init__(self, headers, rows, max_column_width=20, seperator='|'):
        self.headers = headers
        self.rows = rows
        self.max_column_width = max_column_width
        self.seperator = seperator

    def calculate_column_widths(self):
        column_widths = []
        for header in self.headers:
            column_width = max([len(header)] + [len(str(getattr(row, header))) for row in self.rows])
            column_widths.append(min(self.max_column_width, column_width))
        return column_widths

    def __str__(self):
        column_widths = self.calculate_column_widths()
        if self.seperator == '|':
            format = "| " + " | ".join("%%-%ds" % w for w in column_widths) + " |\n"
        else:
            format = self.seperator.join(len(column_widths)*["%s"]) + "\n"
        assert len(column_widths) == len(self.headers)
        output = format % tuple(h.title() for h in self.headers)
        for row in self.rows:
            output += format % tuple(str(getattr(row, header))[:self.max_column_width] for header in self.headers)
        return output


class ParamsTable(object):
    """
    Very primitive implementation of a text table. There are more sophisticated
    implementations around, e.g. http://pypi.python.org/pypi/texttable/0.6.0/
    but for now I'd like to avoid too many dependencies.
    """

    def __init__(self, rows, max_column_width=13, seperator='|'):
        self.rows = rows
        self.headers = self.get_headers()
        self.max_column_width = max_column_width
        self.seperator = seperator

    def get_headers(self):
        headers = [u'label',u'version',u'main_file']
        for row in self.rows:
            params = row.parameters
            if hasattr(params, 'as_dict'):
                params = params.as_dict()
            for key in params.keys():
                if key not in headers:
                    headers.append(key)
        return headers

    def calculate_column_widths(self):
        column_widths = []
        for header in self.headers:
            if header in [u'label', u'version',u'main_file']:
                column_width =max([len(header)] + [len(str(getattr(row, header))) for row in self.rows])
            else:
                column_width = max([len(header)] + [len(str(row.parameters.get(header))) for row in self.rows])
            column_widths.append(min(self.max_column_width, column_width))
        return column_widths

    def __str__(self):
        column_widths = self.calculate_column_widths()
        if self.seperator == '|':
            format = "| " + " | ".join("%%-%ds" % w for w in column_widths) + " |\n"
        else:
            format = self.seperator.join(len(column_widths)*["%s"]) + "\n"
        assert len(column_widths) == len(self.headers)
        output = format % tuple(h for h in self.headers)
        for row in self.rows:
            params = row.parameters
            if hasattr(params, 'as_dict'):
                params = params.as_dict()
            output += format % tuple(
                [str(getattr(row, header))[:self.max_column_width] for header in self.headers[:3]]
               +[str(params.get(header,''))[:self.max_column_width] for header in self.headers[3:]])
        return output


class ShellFormatter(Formatter):
    """
    Create a shell script that can be used to repeat a series of computations.
    """

    def short(self):
        import operator
        output = ("#!/bin/sh\n"
                  "#\n"
                  "# This script was generated by Sumatra (http://neuralensemble.org/sumatra)\n"
                  "# It replays computations from the project '%s'\n" % self.project.name)
        if self.tags:
            output += "# tagged with %s\n" % ",".join(tags)
        if self.project.description:
            output += textwrap.TextWrapper(initial_indent="# ", subsequent_indent="# ").fill(self.project.description)
        cleanup = "\n\n# Clean-up temporary files\n"

        output += "\n# Original hardware environment:\n"
        platforms = list(set(reduce(operator.add, [record.platforms for record in self.records])))
        for i, platform in enumerate(platforms):
            output += "#   Machine #%d: %s processor running %s. %s(%s)\n" % (i + 1, platform.machine, platform.version, platform.network_name, platform.ip_addr, )

        output += "\n# Original software environment:\n"
        repositories = set(record.repository for record in self.records)
        if len(repositories) > 1:
            raise NotImplementedError
        else:
            output += "#   %s repository at %s\n" % (record.repository.vcs_type, record.repository.upstream or record.repository.url)
        dependency_sets = list(set(tuple(sorted(record.dependencies)) for record in self.records))
        for i, dependency_set in enumerate(dependency_sets):
            output += "#   Dependency set #%d: %s\n" % (i + 1, dependency_set)

        current_directory = ''
        current_version = ''
        for record in reversed(self.records):  # oldest first
            output += "\n# " + "-" * 77 + "\n"
            output += "# %s\n" % record.label
            output += "# Originally run on %s by %s\n" % (record.timestamp.strftime("%Y-%m-%d at %H:%M:%S"), record.user)
            if len(platforms) > 1:
                output += "# on machines %s (see above)\n" % ", ".join(str(platforms.index(platform) + 1) for platform in record.platforms)
            if record.reason:
                output += "# for the following reason: '%s'\n" % record.reason
            if record.outcome:
                output += "# with the following outcome: '%s'\n" % record.outcome
            output += "# Duration: %s\n" % human_readable_duration(record.duration)
            output += "# %s version %s\n" % (record.executable.name, record.executable.version)
            if len(dependency_sets) > 1:
                output += "# Dependencies were as in set #%d above\n" % (dependency_sets.index(tuple(sorted(record.dependencies))) + 1,)
            if record.repeats:
                output += "# This was a repeat of a previous computation, #%s\n" % record.repeats
            output += "\n"
            # switch to the correct working directory
            if record.launch_mode.working_directory != current_directory:
                output += "cd %s\n" % record.launch_mode.working_directory
                current_directory = record.launch_mode.working_directory
            # checkout the correct version of the code from the repository
            # then patch if necessary
            if record.version != current_version or record.diff:
                output += "%s %s\n" % (record.repository.use_version_cmd, record.version)
                current_version = record.version
            if record.diff:
                diff_file = "%s.patch" % record.label
                with open(diff_file, 'wb') as fp:
                    fp.write(record.diff + '\n')
                output += "%s %s\n" % (record.repository.apply_patch_cmd, diff_file)
                cleanup += "rm -f %s\n" % diff_file
            # handle pre_run
            if hasattr(record.executable, 'pre_run'):
                output += record.executable.prerun + "\n"
            # build main run command
            # can we add assertions about the SHA1 hash of any input files?
            command_line = record.command_line
            if record.parameters:
                parameter_file_basename = record.label.replace("/", "_")
                parameter_file = record.executable.write_parameters(record.parameters, parameter_file_basename)
                command_line = command_line.replace("<parameters>", parameter_file)
                cleanup += "rm -f %s\n" % parameter_file
            output += command_line + "\n"
        output += cleanup
        return output

# could try embedding patches within shell script using heredoc

    def long(self):
        # perhaps have all the comments in the long version but not the short one
        return self.short()


class HTMLFormatter(Formatter):
    """
    Format information about a group of Sumatra records as HTML fragments, to
    be included in a larger document.
    """

    def short(self):
        """
        Return a list of record labels as an HTML unordered list.
        """
        return "<ul>\n<li>" + "</li>\n<li>".join(record.label for record in self.records) + "</li>\n</ul>"

    def long(self):
        """
        Return detailed information about a list of records as an HTML
        description list.
        """
        def format_record(record):
            output = "  <dt>%s</dt>\n  <dd>\n    <dl>\n" % record.label
            for field in fields:
                output += "      <dt>%s</dt><dd>%s</dd>\n" % (field, cgi.escape(str(getattr(record, field))))
            output += "    </dl>\n  </dd>"
            return output
        return "<dl>\n" + "\n".join(format_record(record) for record in self.records) + "\n</dl>"

    def table(self):
        """
        Return detailed information about a list of records as an HTML table.
        """
        def format_record(record):
            return "  <tr>\n    <td>" + "</td>\n    <td>".join(cgi.escape(str(getattr(record, field))) for field in fields) + "    </td>\n  </tr>"
        return "<table>\n" + \
               "  <tr>\n    <th>" + "</th>\n    <th>".join(field.title() for field in fields) + "    </th>\n  </tr>\n" + \
               "\n".join(format_record(record) for record in self.records) + \
               "\n</table>"


class LaTeXFormatter(Formatter):
    SUBSTITUTIONS = (
        (re.compile(r'\\'), r'\\textbackslash'),
        (re.compile(r'([{}_#%&$])'), r'\\\1'),
        (re.compile(r'~'), r'\~{}'),
        (re.compile(r'\^'), r'\^{}'),
        (re.compile(r'"'), r"''"),
        (re.compile(r'\.\.\.+'), r'\\ldots'),
        (re.compile(r'\<'), r'\\textless{}'),
        (re.compile(r'\>'), r'\\textgreater{}')
    )

    @staticmethod
    def _escape_tex(value):
        """Inspired by http://flask.pocoo.org/snippets/55/"""
        newval = value
        for pattern, replacement in LaTeXFormatter.SUBSTITUTIONS:
            newval = pattern.sub(replacement, newval)
        newval = newval.replace('/', '/ ')
        return newval

    def long(self):
        from os.path import dirname, join
        from jinja2 import Environment, FileSystemLoader
        template_paths = [dirname(__file__)]
        if self.project:
            template_paths.insert(0, join(self.project.path, ".smt"))
        env = Environment(loader=FileSystemLoader(template_paths))
        env.block_start_string = '{%'
        env.block_end_string = '%}'
        env.variable_start_string = '@'
        env.variable_end_string = '@'
        env.filters['human_readable_duration'] = human_readable_duration
        env.filters['escape_tex'] = LaTeXFormatter._escape_tex
        template = env.get_template('latex_template.tex')
        return template.render(records=self.records,
                               project=self.project,
                               paper_size='a4paper')


class CSVFormatter(Formatter):
    """
    Format the information from a list of Sumatra records as text.
    """

    def short(self):
        """Return a list of record labels, one per line."""
        return ";".join(record.label for record in self.records)

    def long(self):
        """
        Return information about a list of records as text, in a simple
        tabular format.
        """
        tt = TextTable(fields, self.records, seperator=';')
        return str(tt)

    def table(self):
        # perhaps have all the comments in the long version but not the short one
        return self.long()

    def params_show(self):
        """
        Return information about a list of records as text, in a simple
        tabular format.
        """
        tt = ParamsTable(self.records, seperator=';')
        return str(tt)

#    def filter(self, keyword=None):
#        """Return a list of record value, one per line."""
#        return ";".join(str(getattr(record, keyword)) for record in self.records)

    def output_files(self):
        """Return a list of record files, one per line."""
        a = [[f.path for f in r.output_data] for r in self.records]
        return ";".join(reduce(operator.add, a))


class TSVFormatter(Formatter):
    """
    Format the information from a list of Sumatra records as text.
    """

    def short(self):
        """Return a list of record labels, one per line."""
        return "\t".join(record.label for record in self.records)

    def long(self):
        """
        Return information about a list of records as text, in a simple
        tabular format.
        """
        tt = TextTable(fields, self.records, seperator='\t')
        return str(tt)

    def table(self):
        # perhaps have all the comments in the long version but not the short one
        return self.long()

    def params_show(self):
        """
        Return information about a list of records as text, in a simple
        tabular format.
        """
        tt = ParamsTable(self.records, seperator='\t')
        return str(tt)

#    def filter(self, keyword=None):
#        """Return a list of record value, one per line."""
#        return "\t".join(str(getattr(record, keyword)) for record in self.records)

    def output_files(self):
        """Return a list of record files, one per line."""
        a = [[f.path for f in r.output_data] for r in self.records]
        return "\t".join(reduce(operator.add, a))


class TextDiffFormatter(Formatter):

    """
    Format information about the differences between two Sumatra records in
    text format.
    """

    def __init__(self, diff):
        self.diff = diff

    def short(self):
        """Return a summary of the differences between two records."""
        def yn(x):
            return x and "yes" or "no"
        D = self.diff
        output = textwrap.dedent("""\
            Record 1                : %s
            Record 2                : %s
            Executable differs      : %s
            Code differs            : %s
              Repository differs    : %s
              Main file differs     : %s
              Version differs       : %s
              Non checked-in code   : %s
              Dependencies differ   : %s 
            Launch mode differs     : %s
            Input data differ       : %s
            Script arguments differ : %s
            Parameters differ       : %s
            Data differ             : %s""" % (
            D.recordA.label,
            D.recordB.label,
            yn(D.executable_differs),
            yn(D.code_differs),
            yn(D.repository_differs), yn(D.main_file_differs),
            yn(D.version_differs), yn(D.diff_differs),
            yn(D.dependencies_differ),
            yn(D.launch_mode_differs),
            yn(D.input_data_differ),
            yn(D.script_arguments_differ),
            yn(D.parameters_differ),
            yn(D.output_data_differ))
        )
        return output

    def long(self):
        """
        Return a detailed description of the differences between two records.
        """
        output = ''
        if self.diff.executable_differs:
            output += "Executable differences:\n"
            for record in (self.diff.recordA, self.diff.recordB):
                output += "  %s: %s\n" % (record.label, record.executable)
        if self.diff.code_differs:
            output += "Code differences:\n"
            for record in (self.diff.recordA, self.diff.recordB):
                output += "  %s: main file '%s' at version %s in %s\n" % (record.label, record.main_file, record.version, record.repository)
            if self.diff.diff_differs:
                for record in (self.diff.recordA, self.diff.recordB):
                    output += "  %s:\n %s\n" % (record.label, record.diff)
        if self.diff.dependencies_differ:
            diffs = self.diff.dependency_differences
            output += "Dependency differences:\n"
            for name, (depA, depB) in diffs.items():
                if depA and depB:
                    output += "  %s\n" % name
                    output += "    A: version=%s\n" % depA.version
                    output += "       %s\n" % depA.diff.replace("\n", "\n       ")
                    output += "    B: version=%s\n" % depB.version
                    output += "       %s\n" % depA.diff.replace("\n", "\n       ")
                elif depB is None:
                    output += "  %s is a dependency of %s but not of %s\n" % (name, self.diff.recordA.label, self.diff.recordB.label)
                elif depA is None:
                    output += "  %s is a dependency of %s but not of %s\n" % (name, self.diff.recordB.label, self.diff.recordA.label)

        diffs = self.diff.launch_mode_differences
        if diffs:
            output += "Launch mode differences:\n"
            modeA, modeB = diffs
            output += "  %s: %s\n" % (self.diff.recordA.label, modeA)
            output += "  %s: %s\n" % (self.diff.recordB.label, modeB)
        if self.diff.parameters_differ:
            output += "Parameter differences:\n"
            for record in (self.diff.recordA, self.diff.recordB):
                output += "  %s:\n%s\n" % (record.label, record.parameters)
        if self.diff.input_data_differ:
            output += "Input data differences:\n"
            for record in (self.diff.recordA, self.diff.recordB):
                output += "  %s: %s\n" % (record.label, record.input_data)
        if self.diff.script_arguments_differ:
            output += "Script argument differences:\n"
            for record in (self.diff.recordA, self.diff.recordB):
                output += "  %s: %s\n" % (record.label, record.script_arguments)
        AnotB, BnotA = self.diff.output_data_differences
        if AnotB or BnotA:
            output += "Output data differences:\n"
            if AnotB:
                output += "  Generated by %s:\n" % self.diff.recordA.label
                for key in AnotB:
                    output += "    %s\n" % key
            if BnotA:
                output += "  Generated by %s:\n" % self.diff.recordB.label
                for key in BnotA:
                    output += "    %s\n" % key
        return output


formatters = {
    'text': TextFormatter,
    'html': HTMLFormatter,
    'latex': LaTeXFormatter,
    'shell': ShellFormatter,
    'csv': CSVFormatter,
    'tsv': TSVFormatter,
    'textdiff': TextDiffFormatter,

}


def get_formatter(format):
    """
    Return a :class:`Formatter` object of the appropriate type. ``format``
    may be 'text, 'html' or 'textdiff'
    """
    return formatters[format]


def get_diff_formatter():
    """
    Return a :class:`DiffFormatter` object of the appropriate type. Only
    text format is currently available.
    """
    return TextDiffFormatter


def _quotient_remainder(dividend, divisor):
    q = dividend // divisor
    r = dividend - q * divisor
    return (q, r)


def human_readable_duration(seconds):
    """
    Coverts seconds to human readable unit

    >>> human_readable_duration(((6 * 60 + 32) * 60 + 12))
    '6h 32m 12.00s'
    >>> human_readable_duration((((8 * 24 + 7) * 60 + 6) * 60 + 5))
    '8d 7h 6m 5.00s'
    >>> human_readable_duration((((8 * 24 + 7) * 60 + 6) * 60))
    '8d 7h 6m'
    >>> human_readable_duration((((8 * 24 + 7) * 60) * 60))
    '8d 7h'
    >>> human_readable_duration((((8 * 24) * 60) * 60))
    '8d'
    >>> human_readable_duration((((8 * 24) * 60) * 60) + 0.12)
    '8d 0.12s'

    """
    from math import modf
    (fractional_part, integer_part) = modf(seconds)
    (d, rem) = _quotient_remainder(int(integer_part), 60 * 60 * 24)
    (h, rem) = _quotient_remainder(rem, 60 * 60)
    (m, rem) = _quotient_remainder(rem, 60)
    s = rem + fractional_part

    return ' '.join(
        templ.format(val)
        for (val, templ) in [
            (d, '{0}d'),
            (h, '{0}h'),
            (m, '{0}m'),
            (s, '{0:.2f}s'),
        ]
        if val != 0
    )
