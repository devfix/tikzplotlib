# -*- coding: utf-8 -*-
# ==============================================================================
#
# Copyright (C) 2010-2011 Nico Schl"omer
#
# This file is part of matplotlib2tikz.
#
# matplotlib2tikz is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# matplotlib2tikz is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with matplotlib2tikz.  If not, see <http://www.gnu.org/licenses/>.
#
# ==============================================================================
'''Script to convert Matplotlib generated figures into TikZ/Pgfplots figures.
'''
# ==============================================================================
# imported modules
import matplotlib as mpl
import numpy
import types
import os
import sys
from itertools import izip
# ==============================================================================
# meta info
__author__     = 'Nico Schl"omer'
__copyright__  = 'Copyright (c) 2010, 2011, Nico Schl"omer <nico.schloemer@gmail.com>'
__credits__    = []
__license__    = 'GNU Lesser General Public License (LGPL), Version 3'
__version__    = '0.1.0'
__maintainer__ = 'Nico Schl"omer'
__email__      = 'nico.schloemer@gmail.com'
__status__     = 'Development'
# ==============================================================================
def save( filepath,
          figurewidth = None,
          figureheight = None,
          textsize = 10.0,
          tex_relative_path_to_data = None,
          strict = False,
          draw_rectangles = False,
          wrap = True,
          extra = None
        ):
    '''Main function. Here, the recursion into the image starts and the contents
    are picked up. The actual file gets written in this routine.

    :param filepath: The file to which the TikZ output will be written.
    :type filepath: str.

    :param figurewidth: If not ``None``, this will be used as figure width
                        within the TikZ/Pgfplot output. If ``figureheight``
                        is not given, ``matplotlib2tikz`` will try to preserve
                        the original width/height ratio.
                        Note that ``figurewidth`` can be a string literal,
                        such as ``'\\figurewidth'``.
    :type figurewidth: str.

    :param figureheight: If not ``None``, this will be used as figure height
                         within the TikZ/Pgfplot output. If ``figurewidth`` is
                         not given, ``matplotlib2tikz`` will try to preserve the
                         original width/height ratio.
                         Note that ``figurewidth`` can be a string literal,
                         such as ``'\\figureheight'``.
    :type figureheight: str.

    :param textsize: The text size (in pt) that the target latex document is using.
                     Default is 10.0.
    :type textsize: float.

    :param tex_relative_path_to_data: In some cases, the TikZ file will have to
                                      refer to another file, e.g., a PNG for
                                      image plots. When ``\\input`` into a
                                      regular LaTeX document, the additional
                                      file is looked for in a folder relative
                                      to the LaTeX file, not the TikZ file.
                                      This arguments optionally sets the
                                      relative path from the LaTeX file to the
                                      data.
    :type tex_relative_path_to_data: str.

    :param strict: Whether or not to strictly stick to matplotlib's appearance.
                   This influences, for example, whether tick marks are set
                   exactly as in the matplotlib plot, or if TikZ/Pgfplots
                   can decide where to put the ticks.
    :type strict: bool.

    :param draw_rectangles: Whether or not to draw Rectangle objects.
                            You normally don't want that as legend, axes, and
                            other entities which are natively taken care of by
                            Pgfplots are represented as rectangles in
                            matplotlib. Some plot types (such as bar plots)
                            cannot otherwise be represented though.
                            Don't expect working or clean output when using
                            this option.
    :type draw_rectangles: bool.

    :param wrap: Whether ``'\\begin{tikzpicture}'`` and ``'\\end{tikzpicture}'``
                 will be written. One might need to provide custom arguments to
                 the environment (eg. scale= etc.). Default is ``True``
    :type wrap: bool.

    :param extra: Extra axis options to be passed (as a dict) to pgfplots. Default
                  is ``None``.
    :type extra: dict.

    :returns: None.
    '''
    data = {}
    data['fwidth']  = figurewidth
    data['fheight'] = figureheight
    data['rel data path'] = tex_relative_path_to_data
    data['output dir'] = os.path.dirname(filepath)
    data['strict'] = strict
    data['draw rectangles'] = draw_rectangles
    data['tikz libs'] = set()
    data['pgfplots libs'] = set()
    data['font size'] = textsize
    data['custom colors'] = {}
    if extra:
        data['extra axis options'] = extra
    else:
        data['extra axis options'] = set()

    # open file
    file_handle = open( filepath, "w" )

    # gather the file content
    data, content = _handle_children( data, mpl.pyplot.gcf() )

    # write the contents
    if wrap:
        file_handle.write( "\\begin{tikzpicture}\n\n" )

    coldefs = _get_color_definitions( data )
    if coldefs:
        file_handle.write( "\n".join( coldefs ) )
        file_handle.write( "\n\n" )

    file_handle.write( ''.join(content) )
    if wrap:
        file_handle.write( "\\end{tikzpicture}" )

    # close file
    file_handle.close()
    
    # print message about necessary pgfplot libs to command line
    _print_pgfplot_libs_message( data )
    return
# ==============================================================================
def _print_tree( obj, indent = "" ):
    '''Recursively prints the tree structure of the matplotlib object.
    '''
    print indent, type(obj)
    for child in obj.get_children():
        _print_tree( child, indent + "   " )
    return
# ==============================================================================
def _get_color_definitions( data ):
    '''Returns the list of custom color definitions for the TikZ file.
    '''
    definitions = []
    for ( color, name ) in data['custom colors'].items():
        definitions.append( "\\definecolor{%s}{rgb}{%g,%g,%g}" % \
                            ( (name,) + color  )
                          )

    return definitions
# ==============================================================================
def _draw_axes( data, obj ):
    '''Returns the Pgfplots code for an axis environment.
    '''
    content = []

    # Are we dealing with an axis that hosts a colorbar?
    # Skip then.
    # TODO instead of testing here, rather blacklist the colorbar axis
    #      plots as soon as they have been found, e.g., by
    #      _find_associated_colorbar()
    if _extract_colorbar(obj):
        return

    # instantiation
    nsubplots = 1
    subplot_index = 0
    is_subplot = False

    if isinstance( obj, mpl.axes.Subplot ):
        geom = obj.get_geometry()
        nsubplots = geom[0]*geom[1]
        if nsubplots > 1:
            is_subplot = True
            subplot_index = geom[2]
            if subplot_index == 1:
                content.append( "\\begin{groupplot}[group style=" \
                                "{group size=%.d by %.d}]\n" % (geom[1],geom[0])
                              )
                data['pgfplots libs'].add( "groupplots" )

    axis_options = []

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # check if axes need to be displayed at all
    if not obj.axison:
        axis_options.append( "hide x axis" )
        axis_options.append( "hide y axis" )
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # get plot title
    title = obj.get_title()
    if title:
        axis_options.append( "title={" + title + "}" )
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # get axes titles
    xlabel = obj.get_xlabel()
    if xlabel:
        axis_options.append( "xlabel={" + xlabel + "}" )
    ylabel = obj.get_ylabel()
    if ylabel:
        axis_options.append( "ylabel={" + ylabel + "}" )
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Axes limits.
    # Sort the limits so make sure that the smaller of the two is actually
    # *min.
    xlim = sorted( list( obj.get_xlim() ) )
    axis_options.append(     "xmin=%e" % xlim[0]
                         + ", xmax=%e" % xlim[1] )
    ylim = sorted( list( obj.get_ylim() ) )
    axis_options.append(     "ymin=%e" % ylim[0]
                         + ", ymax=%e" % ylim[1] )
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # axes scaling
    xscale = obj.get_xscale()
    yscale = obj.get_yscale()
    if xscale == 'log'  and  yscale == 'log':
        env = 'loglogaxis'
    elif xscale == 'log':
        env = 'semilogxaxis'
    elif yscale == 'log':
        env = 'semilogyaxis'
    else:
        env = 'axis'
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if not obj.get_axisbelow():
        axis_options.append( "axis on top" )
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # aspect ratio, plot width/height
    aspect = obj.get_aspect()
    if aspect == "auto"  or  aspect == "normal":
        aspect_num = None # just take the given width/height values
    elif aspect == "equal":
        aspect_num = 1.0
    else:
        try:
            aspect_num = float(aspect)
        except ValueError:
            print "Aspect ratio not a number?!"

    if data['fwidth'] and data['fheight']: # width and height overwrite aspect ratio
        axis_options.append( "width="+data['fwidth'] )
        axis_options.append( "height="+data['fheight'] )
    elif data['fwidth']: # only data['fwidth'] given. calculate height by the aspect ratio
        axis_options.append( "width="+data['fwidth'] )
        if aspect_num:
            alpha = aspect_num * (ylim[1]-ylim[0])/(xlim[1]-xlim[0])
            if alpha != 1.0:
                # Concatenate the literals, as data['fwidth'] could as well be
                # a LaTeX length variable such as \figurewidth.
                data['fheight'] = str(alpha) + "*" + data['fwidth']
            else:
                data['fheight'] = data['fwidth']
            axis_options.append( "height="+data['fheight'] )
    elif data['fheight']: # only data['fheight'] given. calculate width by the aspect ratio
        axis_options.append( "height="+data['fheight'] )
        if aspect_num:
            alpha = aspect_num * (ylim[1]-ylim[0])/(xlim[1]-xlim[0])
            if alpha != 1.0:
                # Concatenate the literals, as data['fheight'] could as well be
                # a LaTeX length variable such as \figureheight.
                data['fwidth'] = str(1.0/alpha) + "*" + data['fheight']
            else:
                data['fwidth'] = data['fheight']
            axis_options.append( "width="+data['fwidth'] )
    else:
        if aspect_num:
            print "Non-automatic aspect ratio demanded, but neither height " \
                  "nor width of the plot are given. Discard aspect ratio."
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # get ticks
    axis_options.extend( _get_ticks( data, 'x', obj.get_xticks(),
                                         obj.get_xticklabels() ) )
    axis_options.extend( _get_ticks( data, 'y', obj.get_yticks(),
                                         obj.get_yticklabels() ) )
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Don't use get_{x,y}gridlines for gridlines; see discussion on
    # <http://sourceforge.net/mailarchive/forum.php?thread_name=AANLkTima87pQkZmJhU2oNb8uxD2dfeV-Pa-uXWAFc2-v%40mail.gmail.com&forum_name=matplotlib-users>
    # Coordinate of the lines are entirely meaningless, but styles (colors,...
    # are respected.
    if obj.xaxis._gridOnMajor:
        axis_options.append( "xmajorgrids" )
    elif obj.xaxis._gridOnMinor:
        axis_options.append( "xminorgrids" )

    if obj.yaxis._gridOnMajor:
        axis_options.append( "ymajorgrids" )
    elif obj.yaxis._gridOnMinor:
        axis_options.append( "yminorgrids" )
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # find color bar
    colorbar = _find_associated_colorbar( obj )
    if colorbar:
        colorbar_styles = []

        orientation = colorbar.orientation
        limits = colorbar.get_clim()
        if orientation == 'horizontal':
            axis_options.append( "colorbar horizontal" )

            colorbar_ticks = colorbar.ax.get_xticks()
            axis_limits = colorbar.ax.get_xlim()

            # In matplotlib, the colorbar color limits are determined by
            # get_clim(), and the tick positions are as usual with respect to
            # {x,y}lim. In Pgfplots, however, they are mixed together.
            # Hence, scale the tick positions just like {x,y}lim are scaled
            # to clim.
            colorbar_ticks = (colorbar_ticks - axis_limits[0]) \
                             / (axis_limits[1] - axis_limits[0]) \
                             * (limits[1] - limits[0]) \
                             + limits[0]

            # Getting the labels via get_* might not actually be suitable:
            # they might not reflect the current state.
            # http://sourceforge.net/mailarchive/message.php?msg_name=AANLkTikdNFwSAhMIlLjnd4Ai8-XIdJYGmrwq6PrHkbgi%40mail.gmail.com
            colorbar_ticklabels = colorbar.ax.get_xticklabels()
            colorbar_styles.extend( _get_ticks( data, 'x', colorbar_ticks,
                                                    colorbar_ticklabels ) )

        elif orientation == 'vertical':
            axis_options.append( "colorbar" )
            colorbar_ticks = colorbar.ax.get_yticks()
            axis_limits = colorbar.ax.get_ylim()

            # In matplotlib, the colorbar color limits are determined by
            # get_clim(), and the tick positions are as usual with respect to
            # {x,y}lim. In Pgfplots, however, they are mixed together.
            # Hence, scale the tick positions just like {x,y}lim are scaled
            # to clim.
            colorbar_ticks = (colorbar_ticks - axis_limits[0]) \
                             / (axis_limits[1] - axis_limits[0]) \
                             * (limits[1] - limits[0]) \
                             + limits[0]

            # Getting the labels via get_* might not actually be suitable:
            # they might not reflect the current state.
            # http://sourceforge.net/mailarchive/message.php?msg_name=AANLkTikdNFwSAhMIlLjnd4Ai8-XIdJYGmrwq6PrHkbgi%40mail.gmail.com
            colorbar_ticklabels = colorbar.ax.get_yticklabels()
            colorbar_styles.extend( _get_ticks( data, 'y', colorbar_ticks,
                                                    colorbar_ticklabels ) )
        else:
            sys.exit( "Unknown color bar orientation \"%s\". Abort." % \
                      orientation )


        mycolormap, is_custom_cmap = _mpl_cmap2pgf_cmap( colorbar.get_cmap() )
        if is_custom_cmap:
            axis_options.append( "colormap=" + mycolormap )
        else:
            axis_options.append( "colormap/" + mycolormap )

        axis_options.append( 'point meta min=%e' % limits[0] )
        axis_options.append( 'point meta max=%e' % limits[1] )

        if colorbar_styles:
            axis_options.append( "colorbar style={%s}" % ",".join(colorbar_styles) )
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # actually print the thing
    if is_subplot:
        content.append( "\\nextgroupplot" )
    else:
        content.append( "\\begin{%s}" % env )

    # Run through the children objects, gather the content, and give them the
    # opportunity to contribute to data['extra axis options'].
    data, children_content = _handle_children( data, obj )

    if data['extra axis options']:
        axis_options.extend( data['extra axis options'] )

    if axis_options:
        options = ",\n".join( axis_options )
        content.append( "[\n" + options + "\n]\n" )

    content.extend( children_content )

    if not is_subplot:
        content.append( "\\end{%s}\n\n" % env )
    elif is_subplot  and  nsubplots == subplot_index:
        content.append( "\\end{groupplot}\n\n" )
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    return data, content
# ==============================================================================
def _get_ticks( data, xy, ticks, ticklabels ):
    '''
    Gets a {'x','y'}, a number of ticks and ticks labels, and returns the
    necessary axis options for the given configuration.
    '''
    axis_options = []
    pgfplots_ticks = []
    pgfplots_ticklabels = []
    is_label_necessary = False
    for (tick, ticklabel) in izip(ticks, ticklabels):
        pgfplots_ticks.append( tick )
        # store the label anyway
        label = ticklabel.get_text()
        pgfplots_ticklabels.append( label )
        # Check if the label is necessary.
        # If *one* of the labels is, then all of them must
        # appear in the TikZ plot.
        is_label_necessary  =  (label and label != str(tick))
        # TODO This seems not quite to be the test whether labels are necessary.

    # Leave the ticks to Pgfplots if not in STRICT mode and if there are no
    # explicit labels.
    if data['strict'] or is_label_necessary:
        if pgfplots_ticks:
            axis_options.append( "%stick={%s}" % \
                                ( xy,
                                  ",".join(["%e" % el for el in pgfplots_ticks]) )
                              )
        else:
            axis_options.append( "%stick=\\empty" % xy )

        if is_label_necessary:
            axis_options.append( "%sticklabels={%s}" % \
                                ( xy, ",".join( pgfplots_ticklabels ) )
                              )
    return axis_options
# ==============================================================================
def _mpl_cmap2pgf_cmap( cmap ):
    '''Converts a color map as given in matplotlib to a color map as represented
    in Pgfplots.
    '''
    if not isinstance( cmap, mpl.colors.LinearSegmentedColormap ):
        print "Don't know how to handle color map. Using 'blackwhite'."
        is_custom_colormap = False
        return ('blackwhite', is_custom_colormap)

    if cmap.is_gray():
        is_custom_colormap = False
        return ('blackwhite', is_custom_colormap)


    segdata = cmap._segmentdata
    red    = segdata['red']
    green  = segdata['green']
    blue   = segdata['blue']

    # loop over the data, stop at each spot where the linear
    # interpolations is interrupted, and set a color mark there
    # set initial color
    k_red   = 0
    k_green = 0
    k_blue  = 0
    x = 0.0
    colors = []
    X = numpy.array([])
    while True:
        # find next x
        x = min( red[k_red][0], green[k_green][0], blue[k_blue][0] )

        if ( red[k_red][0]==x ):
            red_comp = red[k_red][1]
            k_red    = k_red+1
        else:
            red_comp = _linear_interpolation( x,
                                             ( red[k_red-1][0], red[k_red][0] ),
                                             ( red[k_red-1][2], red[k_red][1] )
                                            )

        if ( green[k_green][0]==x ):
            green_comp = green[k_green][1]
            k_green    = k_green+1
        else:
            green_comp = _linear_interpolation( x,
                                                ( green[k_green-1][0],
                                                  green[k_green]  [0]  ),
                                                ( green[k_green-1][2],
                                                  green[k_green]  [1]  )
                                              )

        if ( blue[k_blue][0]==x ):
            blue_comp = blue[k_blue][1]
            k_blue    = k_blue+1
        else:
            blue_comp = _linear_interpolation( x,
                                              ( blue[k_blue-1][0],
                                                blue[k_blue]  [0]  ),
                                              ( blue[k_blue-1][2],
                                                blue[k_blue]  [1]  )
                                            )

        X = numpy.append( X, x )
        colors.append( (red_comp, green_comp, blue_comp) )

        if x >= 1.0:
            break

    # The Pgfplots color map has an actual physical scale, like
    # (0cm,10cm), and the points where the colors change is also given
    # in those units. As of now (2010-05-06) it is crucial for Pgfplots
    # that the difference between two successive points is an integer
    # multiple of a given unity (parameter to the colormap; e.g., 1cm).
    # At the same time, TeX suffers from significant round-off errors,
    # so make sure that this unit is not too small such that the round-
    # off errors don't play much of a role. A unit of 1pt, e.g., does
    # most often not work
    unit = 'pt'

    # Scale to integer
    X = _scale_to_int( X )

    color_changes = []
    for (k, x) in enumerate(X):
        color_changes.append( "rgb(%d%s)=(%.3f,%.3f,%.3f)" % \
                              ( ( x, unit ) + colors[k] )
                            )

    colormap_string = "{mymap}{[1%s] %s }" % \
                      ( unit, "; ".join( color_changes ) )
    is_custom_colormap = True
    return ( colormap_string, is_custom_colormap )
# ==============================================================================
def _scale_to_int( X ):
    '''
    Scales the array X such that it contains only integers.
    '''
    X = X / _gcd_array( X )
    return [int(entry) for entry in X]
# ==============================================================================
def _gcd_array( X ):
    '''
    Return the largest real value h such that all elements in x are integer
    multiples of h.
    '''
    greatest_common_divisor = 0.0
    for x in X:
        greatest_common_divisor = _gcd( greatest_common_divisor, x )

    return greatest_common_divisor
# ==============================================================================
def _gcd( a, b ):
    '''Euclidean algorithm for calculating the GCD of two numbers a, b.
    This algoritm also works for real numbers:
    Find the greatest number h such that a and b are integer multiples of h.
    '''
    # Keep the tolerance somewhat significantly about machine precision,
    # as otherwise round-off errors will be accounted for, returning 1.0e-10
    # instead of 1 for the values
    #   [ 1.0, 2.0000000001, 3.0, 4.0 ].
    while a > 1.0e-5:
        a, b = b % a, a
    return b
# ==============================================================================
def _linear_interpolation( x, X, Y ):
    '''Given two data points [X,Y], linearly interpolate those at x.
    '''
    return ( Y[1]*(x-X[0]) + Y[0]*(X[1]-x) ) / ( X[1]-X[0] )
# ==============================================================================
TIKZ_LINEWIDTHS = { 0.1: 'ultra thin',
                    0.2: 'very thin',
                    0.4: 'thin',
                    0.6: 'semithick',
                    0.8: 'thick',
                    1.2: 'very thick',
                    1.6: 'ultra thick' }
# ------------------------------------------------------------------------------
def _draw_line2d( data, obj ):
    '''Returns the Pgfplots code for an Line2D environment.
    '''
    content = []
    addplot_options = []

    # --------------------------------------------------------------------------
    # get the linewidth (in pt)
    line_width = obj.get_linewidth()

    if data['strict']:
        # Takes the matplotlib linewidths, and just translate them
        # into Pgfplots.
        try:
            addplot_options.append( TIKZ_LINEWIDTHS[ line_width ] )
        except KeyError:
            # explicit line width
            addplot_options.append( "line width=%spt" % line_width )
    else:
        # The following is an alternative approach to line widths.
        # The default line width in matplotlib is 1.0pt, in Pgfplots 0.4pt
        # ("thin").
        # Match the two defaults, and scale for the rest.
        scaled_line_width = line_width / 1.0  # scale by default line width
        if scaled_line_width == 0.25:
            addplot_options.append( "ultra thin" )
        elif scaled_line_width == 0.5:
            addplot_options.append( "very thin" )
        elif scaled_line_width == 1.0:
            pass # Pgfplots default line width, "thin"
        elif scaled_line_width == 1.5:
            addplot_options.append( "semithick" )
        elif scaled_line_width == 2:
            addplot_options.append( "thick" )
        elif scaled_line_width == 3:
            addplot_options.append( "very thick" )
        elif scaled_line_width == 4:
            addplot_options.append( "ultra thick" )
        else:
            # explicit line width
            addplot_options.append( "line width=%spt" % 0.4*line_width )
    # --------------------------------------------------------------------------
    # get line color
    color = obj.get_color()
    data, xcolor, _ = _mpl_color2xcolor( data, color )
    if xcolor:
        addplot_options.append( xcolor )

    linestyle = _mpl_linestyle2pgfp_linestyle( obj.get_linestyle() )
    if linestyle:
        addplot_options.append( linestyle )

    marker_face_color = obj.get_markerfacecolor()
    marker_edge_color = obj.get_markeredgecolor()
    data, marker, extra_mark_options = \
        _mpl_marker2pgfp_marker( data, obj.get_marker(), marker_face_color )
    if marker:
        addplot_options.append( "mark=" + marker )

        mark_options = []
        if extra_mark_options:
            mark_options.append( extra_mark_options )
        if marker_face_color:
            data, col, _ = _mpl_color2xcolor( data, marker_face_color )
            mark_options.append( "fill=" + col )
        if marker_edge_color  and  marker_edge_color != marker_face_color:
            data, col, _ = _mpl_color2xcolor( data, marker_edge_color )
            mark_options.append( "draw=" + col )
        if mark_options:
            addplot_options.append( "mark options={%s}" % \
                                    ",".join(mark_options)
                                  )

    if marker and not linestyle:
        addplot_options.append( "only marks" )

    # process options
    content.append( "\\addplot " )
    if addplot_options:
        options = ", ".join( addplot_options )
        content.append( "[" + options + "]\n" )

    content.append( "coordinates {\n" )


    # print the hard numerical data
    xdata, ydata = obj.get_data()
    try:
        has_mask = ydata.mask.any()
    except AttributeError:
        has_mask = 0

    if has_mask:
        # matplotlib jumps at masked images, while Pgfplots by default
        # interpolates. Hence, if we have a masked plot, make sure that Pgfplots
        # jump as well.
        data['extra axis options'].add( 'unbounded coords=jump' )
        for (x, y, is_masked) in izip(xdata, ydata, ydata.mask):
            if is_masked:
                content.append( "(%e,nan) " % x )
            else:
                content.append( "(%e,%e) " % (x, y) )
    else:
        for (x, y) in izip(xdata, ydata):
            content.append( "(%e,%e) " % (x, y) )
    content.append( "\n};\n" )

    return data, content
# ==============================================================================
# for matplotlib markers, see
# http://matplotlib.sourceforge.net/api/artist_api.html#matplotlib.lines.Line2D.set_marker
MP_MARKER2PGF_MARKER = { '.'   : '*', # point
                         'o'   : 'o', # circle
                         '+'   : '+', # plus
                         'x'   : 'x', # x
                         'None': None,
                         ' '   : None,
                         ''    : None
                       }
# the following markers are only available with PGF's plotmarks library
MP_MARKER2PLOTMARKS = { 'v' : ('triangle', 'rotate=180'), # triangle down
                        '1' : ('triangle', 'rotate=180'), 
                        '^' : ('triangle', None), # triangle up
                        '2' : ('triangle', None),
                        '<' : ('triangle', 'rotate=270'), # triangle left
                        '3' : ('triangle', 'rotate=270'),
                        '>' : ('triangle', 'rotate=90'), # triangle right
                        '4' : ('triangle', 'rotate=90'),
                        's' : ('square', None),
                        'p' : ('pentagon', None),
                        '*' : ('asterisk', None),
                        'h' : ('star', None), # hexagon 1
                        'H' : ('star', None), # hexagon 2
                        'd' : ('diamond', None), # diamond
                        'D' : ('diamond', None), # thin diamond
                        '|' : ('|', None), # vertical line
                        '_' : ('_', None)  # horizontal line
                      }
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
def _mpl_marker2pgfp_marker( data, mpl_marker, is_marker_face_color ):
    '''Translates a marker style of matplotlib to the corresponding style
    in Pgfplots.
    '''
    # try default list
    try:
        pgfplots_marker = MP_MARKER2PGF_MARKER[ mpl_marker ]
        if is_marker_face_color and pgfplots_marker == 'o':
            pgfplots_marker = '*'
            data['pgfplots libs'].add( 'plotmarks' )
        marker_options = None
        return ( data, pgfplots_marker, marker_options )
    except KeyError:
        pass

    # try plotmarks list    
    try:
        data['pgfplots libs'].add( 'plotmarks' )
        pgfplots_marker, marker_options = MP_MARKER2PLOTMARKS[ mpl_marker ]
        if is_marker_face_color and not pgfplots_marker in ['|', '_']:
            pgfplots_marker += '*'
        return ( data, pgfplots_marker, marker_options )
    except KeyError:
        pass

    if mpl_marker == ',': # pixel
        print 'Unsupported marker \"' + mpl_marker + '\".'
    else:
        print 'Unknown marker \"' + mpl_marker + '\".'

    return ( data, None, None )
# ==============================================================================
MPLLINESTYLE_2_PGFPLOTSLINESTYLE = { '-'   : None,
                                     'None': None,
                                     ':'   : 'dotted',
                                     '--'  : 'dashed',
                                     '-.'  : 'dash pattern=on 1pt off 3pt ' \
                                             'on 3pt off 3pt'
                                   }
# ------------------------------------------------------------------------------
def _mpl_linestyle2pgfp_linestyle( line_style ):
    '''Translates a line style of matplotlib to the corresponding style
    in Pgfplots.
    '''
    try:
        return MPLLINESTYLE_2_PGFPLOTSLINESTYLE[ line_style ]
    except KeyError:
        print 'Unknown line style \"' + str(line_style) + '\".'
        return None
# ==============================================================================
def _draw_image( data, obj ):
    '''Returns the Pgfplots code for an image environment.
    '''
    content = []

    if not 'img number' in data.keys():
        data['img number'] = 0

    # Make sure not to overwrite anything.
    file_exists = True
    while file_exists:
        data['img number'] = data['img number'] + 1
        filename = os.path.join( data['output dir'],
                                 "img" + str(data['img number']) + ".png"
                               )
        file_exists = os.path.isfile( filename )
        
      

    # store the image as in a file
    img_array = obj.get_array()

    dims = img_array.shape
    if len(dims)==2: # the values are given as one real number: look at cmap
        clims = obj.get_clim()
        mpl.pyplot.imsave( fname = filename,
                           arr   = img_array ,
                           cmap  = obj.get_cmap(),
                           vmin  = clims[0],
                           vmax  = clims[1] )
    elif len(dims) == 3 and dims[2] in [3, 4]:
        # RGB (+alpha) information at each point
        # convert to PIL image (after upside-down flip)
        import Image
        image = Image.fromarray( numpy.flipud(img_array) )
        image.save( filename )
    else:
        sys.exit( 'Unable to store image array.' )

    # write the corresponding information to the TikZ file
    extent = obj.get_extent()

    # the format specification will only accept tuples, not lists
    if isinstance(extent, list): # convert to () list
        extent = tuple(extent)

    if data['rel data path']:
        rel_filepath = os.path.join( data['rel data path'], os.path.basename(filename) )
    else:
        rel_filepath = os.path.basename(filename)

    # Explicitly use \pgfimage as includegrapics command, as the default
    # \includegraphics fails unexpectedly in some cases
    content.append(  "\\addplot graphics [includegraphics cmd=\pgfimage," \
                                          "xmin=%e, xmax=%e, " \
                                          "ymin=%e, ymax=%e] {%s};\n" % \
                                          ( extent + (rel_filepath,) )
                  )

    data, cont = _handle_children( data, obj )
    content.extend( cont )

    return data, content
# ==============================================================================
def _find_associated_colorbar( obj ):
    ''' Rather poor way of telling whether an axis has a colorbar associated:
    Check the next axis environment, and see if it is de facto a color bar;
    if yes, return the color bar object.
    '''
    for child in obj.get_children():
        try:
            cbar = child.colorbar
        except AttributeError:
            continue
        if not cbar == None: # really necessary?
            # if fetch was successful, cbar contains
            # ( reference to colorbar,
            #   reference to axis containing colorbar )
            return cbar[0]
    return None
# ==============================================================================
def _is_colorbar( obj ):
    '''
    Returns 'True' if 'obj' is a  color bar, and 'False' otherwise.
    '''
    # TODO Are the colorbars exactly the l.collections.PolyCollection's?
    if isinstance( obj, mpl.collections.PolyCollection ):
        arr = obj.get_array()
        dims = arr.shape
        if len(dims) == 1:
            return True # o rly?
        else:
            return False
    else:
        return False
# ==============================================================================
def _extract_colorbar( obj ):
    '''
    Search for color bars as subobjects of obj, and return the first found.
    If none is found, return None.
    '''
    colorbars = mpl.pyplot.findobj( obj, _is_colorbar )

    if not colorbars:
        return None
    if not _equivalent( colorbars ):
        print "More than one color bar found. Use first one."

    return colorbars[0]
# ==============================================================================
def _equivalent( array ):
    '''
    Checks if the vectors consists of all the same objects.
    '''
    if not array:
        return False
    else:
        for elem in array:
            if elem != array[0]:
                return False

    return True
# ==============================================================================
def _draw_polycollection( data, obj ):
    '''Returns Pgfplots code for a number of polygons. Currently empty.
    '''
    print "matplotlib2tikz: Don't know how to draw a PolyCollection."
    return data, ''
# ==============================================================================
def _draw_patchcollection( data, obj ):
    '''Returns Pgfplots code for a number of patch objects.
    '''
    content = []

    for path in obj.get_paths():
        data, cont = _draw_path( data, path#,
                                 #fillcolor = facecolors[0],
                                 #edgecolor = edgecolors[0]
                               )
        content.append( cont )

    return data, content
# ==============================================================================
def _get_draw_options( data, ec, fc ):
    '''Get the draw options for a given (patch) object.'''
    draw_options = []

    if ec is not None:
        data, col, ec_rgba = _mpl_color2xcolor( data, ec )
        draw_options.append( 'draw=%s' % col )

    if fc is not None:
        data, col, fc_rgba = _mpl_color2xcolor( data, fc )
        draw_options.append( 'fill=%s' % col )

    # handle transparency
    if ec is not None and fc is not None and \
       ec_rgba[3] != 1.0 and ec_rgba[3] == fc_rgba[3]:
        draw_options.append( 'opacity=%g' % ec[3] )
    else:
        if ec is not None and ec_rgba[3] != 1.0:
            draw_options.append( 'draw opacity=%g' % ec_rgba[3] )
        if fc is not None and  fc_rgba[3] != 1.0:
            draw_options.append( 'fill opacity=%g' % fc_rgba[3] )

    # TODO Use those properties
    #linewidths = obj.get_linewidths()

    return data, draw_options
# ==============================================================================
def _draw_patch( data, obj ):
    '''Return the Pgfplots code for patches.
    '''

    # Gather the draw options.
    data, draw_options = _get_draw_options( data,
                                            obj.get_edgecolor(),
                                            obj.get_facecolor()
                                          )

    if ( isinstance( obj, mpl.patches.Rectangle ) ):
        # rectangle specialization
        return _draw_rectangle( data, obj, draw_options )
    elif ( isinstance( obj, mpl.patches.Ellipse ) ):
        # ellipse specialization
        return _draw_ellipse( data, obj, draw_options )
    else:
        # regular patch
        return  _draw_path( data, obj.get_path(),
                            draw_options = draw_options
                          )
# ==============================================================================
def _draw_rectangle( data, obj, draw_options ):
    '''Return the Pgfplots code for rectangles.
    '''
    if not data['draw rectangles']:
        return data, []

    left_lower_x = obj.get_x()
    left_lower_y = obj.get_y()
    cont = '\draw[%s] (axis cs:%g,%g) rectangle (axis cs:%g,%g);\n' % \
        ( ','.join(draw_options),
          left_lower_x,
          left_lower_y,
          left_lower_x + obj.get_width(),
          left_lower_y + obj.get_height()
        )

    return data, cont
# ==============================================================================
def _draw_ellipse( data, obj, draw_options ):
    '''Return the Pgfplots code for ellipses.
    '''
    if ( isinstance( obj, mpl.patches.Circle ) ):
        # circle specialization
        return _draw_circle( data, obj, draw_options )

    x, y = obj.center
    cont = '\draw[%s] (axis cs:%g,%g) ellipse (%g and %g);\n' % \
        ( ','.join(draw_options),
          x, y,
          0.5 * obj.width, 0.5 * obj.height
        )

    return data, cont
# ==============================================================================
def _draw_circle( data, obj, draw_options ):
    '''Return the Pgfplots code for circles.
    '''
    x, y = obj.center
    cont = '\draw[%s] (axis cs:%g,%g) circle (%g);\n' % \
        ( ','.join(draw_options),
          x, y,
          obj.get_radius()
        )

    return data, cont
# ==============================================================================
def _draw_pathcollection( data, obj ):
    '''Returns Pgfplots code for a number of patch objects.
    '''
    content = []

    # TODO Use those properties
    #linewidths = obj.get_linewidths()

    # gather the draw options
    ec = obj.get_edgecolors()
    fc = obj.get_facecolors()

    paths = obj.get_paths()

    # TODO always use [0]?
    if ec is not None and len(ec) > 0:
        ec = ec[0]
    else:
        ec = None
    if fc is not None and len(fc) > 0:
        fc = fc[0]
    else:
        fc = None

    for path in paths:
        data, do = _get_draw_options( data, ec, fc )
        data, cont = _draw_path( data, path,
                                 draw_options = do
                               )
        content.append( cont )

    return data, content
# ==============================================================================
def _draw_path( data, path,
                draw_options = None
              ):
    '''Adds code for drawing an ordinary path in Pgfplots (TikZ).
    '''

    nodes = []
    for vert, code in path.iter_segments():
        # For path codes see
        #      <http://matplotlib.sourceforge.net/api/path_api.html#matplotlib.path.Path>
        if code == mpl.path.Path.STOP:
            pass
        elif code == mpl.path.Path.MOVETO:
            nodes.append( '(axis cs:%s,%s)' % ( str(vert[0]), str(vert[1]) ) )
        elif code == mpl.path.Path.LINETO:
            nodes.append( '--(axis cs:%s,%s)' % ( str(vert[0]), str(vert[1]) ) )
        elif code == mpl.path.Path.CURVE3:
            # This is actually a quadratic Bezier curve,
            # but can't deal with this yet.
            print 'Warning: Quadratic Bezier curves not yet supported.'
            nodes.append( '--(axis cs:%s,%s)' % ( str(vert[0]), str(vert[1]) ) )
            nodes.append( '--(axis cs:%s,%s)' % ( str(vert[2]), str(vert[3]) ) )
        elif code == mpl.path.Path.CURVE4:
            # This is actually a cubic Bezier curve,
            # but can't deal with this yet.
            print 'Warning: Cubic Bezier curves not yet supported.'
            nodes.append( '--(axis cs:%s,%s)' % ( str(vert[0]), str(vert[1]) ) )
            nodes.append( '--(axis cs:%s,%s)' % ( str(vert[2]), str(vert[3]) ) )
            nodes.append( '--(axis cs:%s,%s)' % ( str(vert[4]), str(vert[5]) ) )
        elif code == mpl.path.Path.CLOSEPOLY:
            nodes.append( '--cycle' )
        else:
            sys.exit( "Unknown path code %d. Abort." % code )

    nodes_string = ''.join( nodes )
    if draw_options:
        path_command = '\\path [%s] %s;\n\n' % \
                       ( ', '.join(draw_options), nodes_string )
    else:
        path_command = '\\path %s;\n\n' % nodes_string

    return data, path_command
# ==============================================================================
RGB_2_XCOLOR = { # RGB values (as taken from xcolor.dtx):
                 (1,    0,    0   ): 'red',
                 (0,    1,    0   ): 'green',
                 (0,    0,    1   ): 'blue',
                 (0.75, 0.5,  0.25): 'brown',
                 (0.75, 1,    0   ): 'lime',
                 (1,    0.5,  0   ): 'orange',
                 (1,    0.75, 0.75): 'pink',
                 (0.75, 0,    0.25): 'purple',
                 (0,    0.5,  0.5 ): 'teal',
                 (0.5,  0,    0.5 ): 'violet',
                 (0,    0,    0   ): 'black',
                 (0.25, 0.25, 0.25): 'darkgray',
                 (0.5 , 0.5 , 0.5 ): 'gray',
                 (0.75, 0.75, 0.75): 'lightgray',
                 (1,    1,    1   ): 'white'
                 # The colors cyan, magenta, yellow, and olive are also
                 # predefined by xcolor, but their RGB approximation of the
                 # native CMYK values is not very good. Don't use them here.
               }
# ------------------------------------------------------------------------------
def _mpl_color2xcolor( data, matplotlib_color ):
    '''Translates a matplotlib color specification into a proper LaTeX xcolor.
    '''
    # Convert it to RGBA.
    rgba_col = mpl.colors.ColorConverter().to_rgba( matplotlib_color )

    try:
        # Try to lookup the color in the default color table.
        xcol = RGB_2_XCOLOR[ rgba_col[0:3] ]
    except KeyError:
        # Lookup failed, add it to the custom list.
        data, xcol = _add_rgbcolor_definition( data, rgba_col[0:3] )

    return data, xcol, rgba_col
# ==============================================================================
def _add_rgbcolor_definition( data, color_tuple ):
    '''Takes an RGB color tuple, adds it to the list of colors that will
    need to be defined in the TikZ file, and returns the label with which the
    color can be used.
    '''
    if color_tuple not in data['custom colors']:
        data['custom colors'][ color_tuple ] = \
             'color' + str(len(data['custom colors']))

    return data, data['custom colors'][ color_tuple ]
# ==============================================================================
def _draw_legend( data, obj ):
    '''Adds legend code to the EXTRA_AXIS_OPTIONS.
    '''
    texts = []
    for text in obj.texts:
        texts.append( "%s" % text.get_text() )

    cont = 'legend entries={%s}' % ",".join( texts )
    if data['extra axis options']:
        data['extra axis options'].add( cont )
    else:
        data['extra axis options'] = [ cont ]

    return data
# ==============================================================================
def _draw_text( data, obj ):
    '''Paints text on the graph.
    '''
    content = []
    properties = []
    style = []
    if( isinstance(obj, mpl.text.Annotation) ):
        ann_xy = obj.xy
        ann_xycoords = obj.xycoords
        ann_xytext = obj.xytext
        ann_textcoords = obj.textcoords
        if ann_xycoords != "data" or ann_textcoords != "data":
            print( "Warning: Anything else except for explicit positioning " +
                   "is not supported for annotations yet :(" )
            return data, content
        else: # Create a basic tikz arrow
            arrow_style = []
            if obj.arrowprops is not None:
                if obj.arrowprops['arrowstyle'] is not None:
                    if obj.arrowprops['arrowstyle'] in ['-', '->', '<-', '<->']:
                        arrow_style.append(obj.arrowprops['arrowstyle'])
                        data, col, _ = _mpl_color2xcolor( data,
                                                        obj.arrow_patch.get_ec()
                                                      )
                        arrow_style.append( col )
                    elif obj.arrowprops['ec'] is not None:
                        data, col, _ = _mpl_color2xcolor( data,
                                                        obj.arrowprops['ec']
                                                      )
                        arrow_style.append( col )
                    elif obj.arrowprops['edgecolor'] is not None:
                        data, col, _ = _mpl_color2xcolor( data,
                                                        obj.arrowprops['edgecolor']
                                                      )
                        arrow_style.append( col )
                    else:
                        pass

            arrow_proto = "\\draw[%s] (axis cs:%e,%e) -- (axis cs:%e,%e);\n"
            the_arrow = arrow_proto % ( ",".join(arrow_style),
                                        ann_xytext[0],
                                        ann_xytext[1],
                                        ann_xy[0],
                                        ann_xy[1]
                                      )
            content.append( the_arrow )
    
    # 1: coordinates in axis system
    # 2: properties (shapes, rotation, etc)
    # 3: text style
    # 4: the text
    #                   -------1--------2---3--4--
    proto = "\\node at (axis cs:%e,%e)[\n  %s\n]{%s %s};\n"
    pos = obj.get_position()
    text = obj.get_text()
    size = obj.get_size()
    bbox = obj.get_bbox_patch()
    converter = mpl.colors.ColorConverter()
    scaling = 0.5*size / data['font size']  # XXX: This is ugly
    properties.append("scale=%g" % scaling )
    if bbox is not None:
        bbox_style = bbox.get_boxstyle()
        if bbox.get_fill():
            data, fc, _ = _mpl_color2xcolor( data, bbox.get_facecolor() )
            if fc:
                properties.append("fill=%s" % fc)
        data, ec, _ = _mpl_color2xcolor( data, bbox.get_edgecolor() )
        if ec:
            properties.append("draw=%s" % ec )
        properties.append("line width=%gpt"%(bbox.get_lw()*0.4)) # XXX: This is ugly, too
        properties.append( "inner sep=%gpt" %
                           (bbox_style.pad * data['font size'])
                         )
        # Rounded boxes
        if( isinstance(bbox_style, mpl.patches.BoxStyle.Round) ):
            properties.append("rounded corners")
        elif( isinstance(bbox_style, mpl.patches.BoxStyle.RArrow) ):
            data['tikz libs'].add("shapes.arrows")
            properties.append("single arrow")
        elif( isinstance(bbox_style, mpl.patches.BoxStyle.LArrow) ):
            data['tikz libs'].add("shapes.arrows")
            properties.append("single arrow")
            properties.append("shape border rotate=180")
        # Sawtooth, Roundtooth or Round4 not supported atm
        # Round4 should be easy with "rounded rectangle"
        # directive though.
        else:
            pass # Rectangle
        # Line style
        if bbox.get_ls() == "dotted":
            properties.append( "dotted" )
        elif bbox.get_ls() == "dashed":
            properties.append("dashed")
        # XXX: Is there any way to extract the dashdot
        # pattern from matplotlib instead of hardcoding
        # an approximation?
        elif(bbox.get_ls() == "dashdot"):
            properties.append("dash pattern=on %.3gpt off %.3gpt on %.3gpt off %.3gpt" % \
                              (1.0/scaling, 3.0/scaling, 6.0/scaling, 3.0/scaling))
        else: pass # solid

    ha = obj.get_ha()
    va = obj.get_va()
    anchor = _transform_positioning( ha, va )
    if anchor is not None:
        properties.append(anchor)
    data, col, _ = _mpl_color2xcolor( data, converter.to_rgb(obj.get_color()) )
    properties.append( "text=%s" % col )
    properties.append( "rotate=%.1f" % obj.get_rotation() )
    if obj.get_style() != "normal":
        style.append("\\itshape")
    try:
        if int(obj.get_weight()) > 550:
            style.append('\\bfseries')
    except: # Not numeric
        vals = [ 'semibold',
                 'demibold',
                 'demi',
                 'bold',
                 'heavy',
                 'extra bold',
                 'black'
               ]
        if str(obj.get_weight()) in vals:
            style.append('\\bfseries')
    content.append( proto %
                    ( pos[0], pos[1],
                      ",\n  ".join(properties), " ".join(style), text
                    )
                  )

    return data, content
# ==============================================================================
def _transform_positioning( ha, va ):
    '''Converts matplotlib positioning to pgf node positioning.
    Not quite accurate but the results are equivalent more or less.'''
    if ha == "center" and va == "center":
        return None
    else:
        ha_mpl_to_tikz = { 'right' : 'east',
                           'left'  : 'west',
                           'center': ''
                         }
        va_mpl_to_tikz = { 'top'     : 'north',
                           'bottom'  : 'south',
                           'center'  : '',
                           'baseline': 'base'
                         }
        return ( "anchor=%s %s" % ( va_mpl_to_tikz[va], ha_mpl_to_tikz[ha] )
               ).strip()
# ==============================================================================
def _handle_children( data, obj ):
    '''Iterates over all children of the current object, gathers the contents
    contributing to the resulting Pgfplots file, and returns those.'''

    content = []
    for child in obj.get_children():
        if ( isinstance( child, mpl.axes.Axes ) ):
            data, cont = _draw_axes( data, child )
            content.extend( cont )
        elif ( isinstance( child, mpl.lines.Line2D ) ):
            data, cont = _draw_line2d( data, child )
            content.extend( cont )
        elif ( isinstance( child, mpl.image.AxesImage ) ):
            data, cont = _draw_image( data, child )
            content.extend( cont )
        elif ( isinstance( child, mpl.patches.Patch ) ):
            data, cont = _draw_patch( data, child )
            content.extend( cont )
        elif ( isinstance( child, mpl.collections.PolyCollection ) ):
            data, cont = _draw_polycollection( data, child )
            content.extend( cont )
        elif ( isinstance( child, mpl.collections.PatchCollection ) ):
            data, cont = _draw_patchcollection( data, child )
            content.extend( cont )
        elif ( isinstance( child, mpl.collections.PathCollection ) ):
            data, cont = _draw_pathcollection( data, child )
            content.extend( cont )
        elif ( isinstance( child, mpl.legend.Legend ) ):
            data = _draw_legend( data, child )
        elif (   isinstance( child, mpl.axis.XAxis )
              or isinstance( child, mpl.axis.YAxis )
              or isinstance( child, mpl.spines.Spine )
              or isinstance( child, mpl.text.Text )
              or isinstance( child, mpl.collections.QuadMesh )
             ):
            pass
        else:
            print "matplotlib2tikz: Don't know how to handle object \"%s\"." % \
                  type(child)

    # XXX: This is ugly
    if isinstance(obj, mpl.axes.Subplot) or isinstance(obj, mpl.figure.Figure):
        for text in obj.texts:
            data, cont = _draw_text( data, text )
            content.extend( cont )

    return data, content
# ==============================================================================
def _print_pgfplot_libs_message( data ):
    '''Prints message to screen indicating the use of Pgfplots and its
    libraries.'''
    pgfplotslibs = ",".join( list( data['pgfplots libs'] ) )
    tikzlibs = ",".join( list( data['tikz libs'] ) )

    print "========================================================="
    print "Please add the following line to your LaTeX preamble:\n"
    print "\usepackage{pgfplots}"
    if tikzlibs:
        print "\usetikzlibrary{"+ tikzlibs +"}"
    if pgfplotslibs:
        print "\usepgfplotslibrary{" + pgfplotslibs + "}"
    print "========================================================="

    return
# ==============================================================================