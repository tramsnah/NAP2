'''
Module to provide wrapper class to plot histograms
from peilmerk measurements.
Plots made in matplotlib.
'''
from . import matplotwrapper as MPW

class HistoWrapper(MPW.MatPlotWrapper):
    '''
    Wrapper class to plot histograms
    from peilmerk measurements.
    Plots made in matplotlib.
    '''
    def __init__(self, name, mgr, **kwargs):
        MPW.MatPlotWrapper.__init__(self, name, mgr, "histo", **kwargs)
        
    def addPoints(self, df, zKey="", layer="", xLabel="", cumulative = True):
        '''
        Add a set of points to histogram. Data provided as pandas dataframe.
        Can be called multiple times.
        Column 'zKey' plotted on x-axis
        'xLabel' is shown as labels on x-axis. If called
        multiple times, last values used.
        'layer' annotates plot element in legend.
        if 'cumulative' is true, a cumulative distribution is plotted
        '''
        # Open the plot (if needed), ...
        if (self._ax is None):     
            self.openFigure()
            
        # Values
        zdiffs = list(df[zKey].values)
            
        # Range
        zmin = min(zdiffs)
        zmax = max(zdiffs)

        # Count positive values
        c = len([x for x in zdiffs if x > 0])

        # Create histogram
        ibins = 50
        n, bins, patches = self._ax.hist(zdiffs, ibins, density = True, cumulative = cumulative, 
                                facecolor = 'blue', alpha = 0.5, edgecolor = "black",
                                label=layer)
        self.addEntry(layer)
                                
        # Labels, etc.
        yLabel="P" if cumulative else "Frequency"
        #ax.set_xLabel(xLabel)
        #ax.set_yLabel(yLabel)
        self.setXLabel(xLabel)
        self.setYLabel(yLabel)

        self._ax.text(zmin*0.95+zmax*0.05, 0.9, 
                    f'Number of points: {str(len(zdiffs))}'+
                    f', positive: {(100*c/len(zdiffs)):.2f} %')
