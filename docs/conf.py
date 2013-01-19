# -*- coding: utf-8 -*-
"""
Sphinx configuration file for the Passlib documentation.

This file is execfile()d with the current directory set to its containing dir.
Note that not all possible configuration values are present in this
autogenerated file. All configuration values have a default; values that are
commented out serve to show the default.
"""
#=============================================================================
# environment setup
#=============================================================================
import sys, os

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
##sys.path.insert(0, os.path.abspath('.'))

# make sure root of source dir in sys.path
sys.path.insert(0, os.path.abspath(os.pardir))

#=============================================================================
# imports
#=============================================================================

# build option flags:
# "for-pypi" -- enable analytics tracker for pypi documentation
options = os.environ.get("PASSLIB_DOCS", "").split(",")

# building the docs requires the Cloud Sphinx theme & extensions (>= v1.4),
# which contains some sphinx extensions used by Passlib.
# (https://bitbucket.org/ecollins/cloud_sptheme)
import cloud_sptheme as csp

# hack to make autodoc generate documentation from the correct class...
import passlib.utils.md4 as md4_mod
md4_mod.md4 = md4_mod._builtin_md4

#=============================================================================
# General configuration
#=============================================================================

# If your documentation needs a minimal Sphinx version, state it here.
needs_sphinx = '1.1'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    # standard sphinx extensions
    'sphinx.ext.autodoc',
    'sphinx.ext.todo',

    # add autdoc support for ReST sections in class/function docstrings
    'cloud_sptheme.ext.autodoc_sections',

    # adds extra ids & classes to genindex html, for additional styling
    'cloud_sptheme.ext.index_styling',

    # inserts toc into right hand nav bar (ala old style python docs)
    'cloud_sptheme.ext.relbar_toc',

    # replace sphinx :samp: role handler with one that allows escaped {} chars
    'cloud_sptheme.ext.escaped_samp_literals',

    # add "issue" role
    'cloud_sptheme.ext.issue_tracker',

    # allow table column alignment styling
    'cloud_sptheme.ext.table_styling',
    ]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
source_encoding = 'utf-8'

# The master toctree document.
master_doc = 'contents'

# The frontpage document.
index_doc = 'index'

# General information about the project.
project = 'Passlib'
author = "Assurance Technologies, LLC"
copyright = "2008-2012, " + author

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.

# release: The full version, including alpha/beta/rc tags.
# version: The short X.Y version.
from passlib import __version__ as release
version = csp.get_version(release)

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
##language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
##today = ''
# Else, today_fmt is used as the format for a strftime call.
##today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = [
    # disabling documentation of this until module is more mature.
    "lib/passlib.utils.compat.rst",

    # may remove this in future release
    "lib/passlib.utils.md4.rst",
]

# The reST default role (used for this markup: `text`) to use for all documents.
##default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
##add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
##show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = ["passlib."]

#=============================================================================
# Options for all output
#=============================================================================
todo_include_todos = True
keep_warnings = True
issue_tracker_url = "gc:passlib"

#=============================================================================
# Options for HTML output
#=============================================================================

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = os.environ.get("SPHINX_THEME") or 'redcloud'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {}
if csp.is_cloud_theme(html_theme):
    html_theme_options.update(roottarget=index_doc, issueicon=None)
    if 'for-pypi' in options:
        html_theme_options.update(
            googleanalytics_id = 'UA-22302196-2',
            googleanalytics_path = '/passlib/',
        )

# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = [csp.get_theme_dir()]

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
html_title = "%s v%s Documentation" % (project, release)

# A shorter title for the navigation bar.  Default is the same as html_title.
html_short_title = "%s %s Documentation" % (project, version)

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = os.path.join("_static", "masthead.png")

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
html_favicon = "logo.ico"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
##html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
##html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
##html_additional_pages = {}

# If false, no module index is generated.
##html_domain_indices = True

# If false, no index is generated.
##html_use_index = True

# If true, the index is split into individual pages for each letter.
##html_split_index = False

# If true, links to the reST sources are added to the pages.
##html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
##html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
##html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
##html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
##html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = project + 'Doc'

#=============================================================================
# Options for LaTeX output
#=============================================================================

# The paper size ('letter' or 'a4').
##latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
##latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  (master_doc, project + '.tex', project + ' Documentation',
   author, 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
##latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
##latex_use_parts = False

# If true, show page references after internal links.
##latex_show_pagerefs = False

# If true, show URL addresses after external links.
##latex_show_urls = False

# Additional stuff for the LaTeX preamble.
##latex_preamble = ''

# Documents to append as an appendix to all manuals.
##latex_appendices = []

# If false, no module index is generated.
##latex_domain_indices = True

#=============================================================================
# Options for manual page output
#=============================================================================

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, project, project + ' Documentation',
     [author], 1)
]

#=============================================================================
# EOF
#=============================================================================
