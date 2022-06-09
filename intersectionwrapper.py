'''
Module contains IntersectionWrapper class for 
plotting of intersections through subsidence grids 
(subsidence on y axis) in a matplotlib window,
either stand-alone or embedded in a tk window.
'''
import numpy as np
from . import matplotwrapper as MPW
from . import plotline as PL

class IntersectionWrapper(MPW.MatPlotWrapper):
    '''
    IntersectionWrapper class for 
    plotting of intersections through subsidence grids 
    (subsidence on y axis) in a matplotlib window,
    either stand-alone or embedded in a tk window.

    Adds only intersection related methods to
    'MatPlotWrapper' base class.
    '''
    def __init__(self, name, mgr, line=None, xy=(0,0), angleDeg=0, **kwargs):
        '''
        Intialize intersection wrapper 'name'.
        Mgr is the master object.
        Intersection line is specified by anchor point xy and 'angleDeg'.

        See MatPlotWrapper for additional arguments.
        '''
        MPW.MatPlotWrapper.__init__(self, name, mgr, "intersection", **kwargs)
        
        if (line is None):
            line = PL.PlotLine(xy, angleDeg)

        self._line = line
        
    def addPoints(self, df, zKey="", labelKey=None, layer="", xLabel="",
                    yLabel="", distMax=500, minScale=None, bounds=None):
        '''
        Add points to plot. 
        Data is provided in pandas dataframe df.
            zKey: column that contains z data
            labelKey: column that contains descriptive text
            distMax: maximum distance from line
            minScale: minimum extent of y-scale
            bounds: (xmin,ymin,xmax,ymax) limiting extent of points to be considered
            yLabel: label for y axis

        '''
        # Project onto the line
        xs = self._line.project(df[self.xkey].values, df[self.ykey].values, distMax)
        
        # Subsidences
        zs = df[zKey].values
        indxs = df.index.values
        
        # Open the plot (if needed), ...
        ax = self.getAxesObject()
        
        # Create the plot
        ax.scatter(xs, zs, label=layer)
        self.addEntry(layer)
        
        # Labels
        if (xLabel == ""): xLabel = "[m]" 
        #ax.set_xlabel(xLabel)
        #ax.set_ylabel(yLabel)
        self.setXLabel(xLabel)
        self.setYLabel(yLabel)
        ax.grid()
        
        # Fix axis (do not zoom in too much)
        if not (minScale is None):
            (ymin, ymax)=ax.get_ylim()
            ymax = max(ymax,0)
            ymin = min(ymin, ymax-minScale)
            ax.set_ylim((ymin, ymax))
            (xmin, xmax)=ax.get_xlim()
            xmax = max(xmax,0)
            xmin = min(xmin, xmax-minScale)
            ax.set_xlim((xmin, xmax))
        
        # Record what we have plotted for pop-ups
        self.recordPlotted(df, xs, zs, indxs, labelKey, layer)
