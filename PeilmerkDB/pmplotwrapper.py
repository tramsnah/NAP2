'''
Module that contains class to make peilmerk plots:
Height or difference vs. time for one or
more peilmerken, on one or more surveys.
Used by SubsAnalysis.
'''
from . import messagelogger as ML
from . import matplotwrapper as MPW
from . import peilmerkdatabase as PM # For special keys MEDIAN, MERGE

# TODO: NEEDS IMPLEMENTATION OF TIME PERIOD IMPACT ON Y-AXIS

AUTO_ZKEY="auto"

class PmPlotWrapper(MPW.MatPlotWrapper):
    '''
    Module that contains class to make peilmerk plots:
    Height or difference vs. time for one or more peilmerken, on one or more surveys.
    Used by SubsAnalysis.

    The type of height plotted on the vertical axis (i.e. raw NAP or differential) is
    postponed until the first data is offered.
    '''
    def __init__(self, name, mgr, hkey=AUTO_ZKEY, **kwargs):
        MPW.MatPlotWrapper.__init__(self, name, mgr, "pmplot", hkey=hkey, **kwargs)
        # Cache the curves being displayed
        self._allSeriesKeys = dict()
        
        # Let the base class know the x-axis label
        self.setXLabel("Date")
        
    def getDisplayedSeries(self, key):
        '''
        Get list of the displayed Series for 'key' (i.e. all peilmerken
        plotted if key=PM.PEILMERK_KEY, or all surveys plotted if key=PM.SURVEY_KEY).
        Gives 'KeyError' if no series are plotted for that key (i.e. if peilmerken are
        asked for, but the only variation between the series is survey).

        See the argument 'skeys' in the 'addPoints' method.
        '''
        return list(self._allSeriesKeys[key])

    def checkHeightType(self, df):
        '''
        Figure out height type from what occurs in 'df', on the first call.
        Subsequent calls check the height type matches.
        '''
        if (self.hkey == AUTO_ZKEY):
            if (PM.HGT_KEY in df):
                self.hkey = PM.HGT_KEY
            else:
                assert(PM.DIFF_KEY in df)
                self.hkey = PM.DIFF_KEY
        else: assert(self.hkey in df)
        
    def addPoints(self, df, skeys=""): 
        '''
        Add points to the plot. Data provided as dataframe.
        x-axis is dataframe column dkey, y-axis is 
        dataframe column hkey (see base class).
        Can be called multiple times.

        skeys contains the list of columns to be plotted 
        (defaults to skey). Each unique value in this column
        leads to a separate plot element.
        skeys could be peilmerk (so one plot element per peilmerk),
        survey name, or both.
        '''
        # Open the plot (if needed), ...
        if (self._ax is None):     
            self.openFigure()
        
        # Cannot do anything with empty df
        if (len(df)==0):
            ML.LogMessage("No points to plot")
            return

        # Figure out depth type (if we're the first plot element;
        # all plot elements need to have the same one)
        self.checkHeightType(df)
        
        # Get list of surveys
        if(skeys==""):
            skeys = self.skey

        # Convert to list
        if isinstance(skeys, str):
            skeys=[skeys]
            
        # We also need a copy of the list in reverse
        skeys_r = skeys.copy()
        skeys_r.reverse()

        # Init admin
        indxs = {}
        srvys = {}
        for skey in skeys:
            indxs[skey] = 0
            srvys[skey] = []
            
            # Keep overall list globally
            self._allSeriesKeys[skey] = set()
        
        # Plot 1-by-1, loop over variable # of dimensions
        keepGoing = True
        while (keepGoing):
            # Init admin for current cycle. We filter df2 as we move through the levels,
            # and build up sname along the way
            df2 = df
            sname = ""
            
            # Select on all dimensions 1-by-1, start with the highest, then update the list
            # on the lower, etc.
            for skey in skeys:
                # Don't unnecessarily refresh the list
                if (len(srvys[skey])==0):
                    srvys[skey] = list(df2[skey].unique())
            
                    # Keep overall list globally
                    self._allSeriesKeys[skey] = self._allSeriesKeys[skey].union(srvys[skey])
                #print(skey, indxs, srvys)
                sval = srvys[skey][indxs[skey]]
                df2 = df2[df2[skey]==sval]
                sname += sval+", "
            sname = sname[:-2]
            
            # Skip if no data
            if (len(df2)>0):
                # Special types
                marker="o"
                linestyle="solid"
                if (PM.MEDIAN in sname):
                    linestyle="dashed"
                    marker=""
                elif (PM.MERGE in sname):
                    linestyle=""
                    marker="s"
            
                # Add to plot
                df2.plot(ax=self._ax, marker=marker, ylabel="NAP [m]",
                        x=self.dkey, y=self.hkey, label=sname,
                        linewidth=1.0,  linestyle=linestyle)#, color=df.columns)
                        
                # Record the line (so we can later scale the legend)
                self.addEntry()
                        
            # Move to next index, until we've covered everything.
            # The lowest level moves first (hence use the reversed list).
            keepGoing = False
            for skey in skeys_r:
                indxs[skey] += 1
                if (indxs[skey] < len(srvys[skey])):
                    keepGoing = True
                    break
            
                # We're done at this level.
                # Higher index will move, so list at current level needs to be refreshed
                indxs[skey] = 0            
                srvys[skey] = []

        #print("allSeriesKeys", self._allSeriesKeys)
        
    def setTimePeriod(self, tmin, tmax):
        '''
        Fix time period on x axis. Equivalent to MPW.MatPlotWrapper.setXRange
        '''
        MPW.MatPlotWrapper.setXRange(self, tmin, tmax)
