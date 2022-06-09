'''
Module to provide wrapper class to plot crossplots
from peilmerk measurements.
Plots made in matplotlib.

TODO: add potion to plot trend
'''
from . import matplotwrapper as MPW

class CrossplotWrapper(MPW.MatPlotWrapper):
    '''
    Wrapper class to plot crossplots
    from peilmerk measurements.
    Plots made in matplotlib.
    '''
    def __init__(self, name, mgr, **kwargs):
        MPW.MatPlotWrapper.__init__(self, name, mgr, "xplot", **kwargs)
    
        
    def addPoints(self, df, zKeyX="", zKeyY="", labelKey="", 
                layer="", xLabel="", yLabel="", minScale=None):
        '''
        Add a set of points to crossplot. Data provided as pandas dataframe.
        Can be called multiple times.
        Column 'zKeyX' plotted on x-axis, 'zKeyY' on y-axis.
        'labelKey' provides column name that contains text for pop-up.
        'xLabel' and 'yLabel' are shown as labels on x- and y-axis. If called
        multiple times, last values used.
        'layer' annotates plot element in legend.
        'minScale' assures the minimum extent of x- and y-axis.
        '''
        # Open the plot (if needed), ...
        if (self._ax is None):     
            self.openFigure()
        ax = self._ax
        
        # Values
        x = list(df[zKeyX].values)
        y = list(df[zKeyY].values)
        indxs = list(df.index.values)
        
        # Create the plot
        ax.scatter(x, y, label=layer)
        self.addEntry(layer)
        
        # Labels
        #ax.set_xLabel(xLabel)
        #ax.set_yLabel(yLabel)
        self.setXLabel(xLabel)
        self.setYLabel(yLabel)
        ax.grid()
        
        # Fix axis (do not zoom in too much)
        # TODO: LEAVE THIS TO MATPLOTWRAPPER!?
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
        self.recordPlotted(df, x, y, indxs, labelKey, layer)
