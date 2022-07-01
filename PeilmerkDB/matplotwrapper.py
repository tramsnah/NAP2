'''
Generic (abstract) base classes to facilitate managing various
kinds of plots using MatPlotLib
'''
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

from . import genplotwrapper as GW
from . import embedplotindialog as ED
from . import messagelogger as ML
from . import mptimer as MPT

# Default _colors etc.
_colors=[]
_colors.append("black")
_colors.append("blue")
_colors.append("red")
_colors.append("green")
_colors.append("orange")
_colors.append("yellow")
_colors.append("grey")
_colors.append("brown")
_colors.append("purple")
_colors.append("hotpink")
_colors.append("lime")

_lstyles=[]
_lstyles.append("solid")
_lstyles.append("dotted")
_lstyles.append("dashdot")
_lstyles.append("dashed")
_lstyles.append((0, (3, 5, 1, 5, 1, 5)))

_mstyles=[]
_mstyles.append("o")
_mstyles.append("^")
_mstyles.append("v")
_mstyles.append("<")
_mstyles.append(">")
_mstyles.append("s")
_mstyles.append("p")
_mstyles.append("*")
_mstyles.append("P")
_mstyles.append("D")

class MatPlotWrapper(GW.GenPlotWrapper):
    '''
    Base class wrapper for various types of matplotlib polts
    (crossplot, intersection, peilmerkplot, map)
    '''
    def __init__(self, name, mgr, wType, inDialog = None, **kwargs):
        GW.GenPlotWrapper.__init__(self, name, mgr, wType, **kwargs)

        self._inDialog = inDialog
        self._ax = None
        self._ax = None
        self._fig = None
        self._canvas = None
        self._cbarAx = None
        
        self._xmin = None
        self._xmax = None
        self._dxmin = None

        self._ymin = None
        self._ymax = None
        self._dymin = None
        
        self._xlabel = None
        self._ylabel = None
        
        self._hideTickLabels = False
        
        self._entries = list()
        
        self._plotted = None
        self._annotation = None
        self._timer = None
        self._hovercall = None
        
    def addEntry(self, name = None):
        '''
        Add layer to admin.
        '''
        # Generate unique name if needed
        if (name is None): name=""
        lname = name
        idx = 0
        while(lname in self._entries):
            lname = name +"_"+ str(idx)
            idx += 1
            
        self._entries.append(lname)

        return lname
        
    def getAxesObject(self, openIfNeeded=True):
        '''
        Open the plot (if needed), ...
        '''
        if openIfNeeded and (self._ax is None):     
            self.openFigure()
        return self._ax
        
    def getMarkerStyle(self, idx):
        '''
        # Get marker style # idx (to automate differeing marker styles per series)
        '''
        return _mstyles[idx % len(_mstyles)]
        
    def getFileExtension(self):
        '''
        File extension is png
        '''
        return "png"
        
    def openFigure(self):
        '''
        Initialize the matplotlib Figure
        '''
        assert(self._ax is None)
        
        # Open the plot
        if not (self._inDialog is None):
            self._fig = Figure(figsize = (7, 4), dpi = 100, alpha  = 1)
        else:
            self._fig = plt.figure()
        self._ax = self._fig.subplots() 
        #self._fig.tight_layout()
        
        self._entries = list()
        
    def resizePlotLegendRight(self, widthPlotArea=8, height=4):
        '''
        Adapt legend placement and sizing, so that also for very large numbers
        of lines, the legend does not cover the plot.
        The legend is shown right of the plot. If necessary, the plot is enlarged
        so the plot area stays roughly the same size.
        The method assumes no RHS axis.
        '''
        # First figure out what's in the legend.
        # Number of entries, and length of legend text.
        _, l = self._ax.get_legend_handles_labels()
        numEntries=len(l)
        maxlen=0
        for label in l:
            maxlen=max(len(label),maxlen)  

        # Add legend to the right
        # First compute # of columns and lines
        nc=int(numEntries/30+0.99)
        nl=int(numEntries/nc+0.99)

        # Fontsize
        fs = min(int(170/maxlen), int(210/nl))
        fs = max(3, fs)
        
        width_l=maxlen*fs/100*nc
        width = widthPlotArea + width_l    

        xfrac=1-width_l/width
        self._fig.subplots_adjust(right=xfrac)
        self._fig.set_size_inches(width, height)

        self._ax.legend(ncol=nc, loc="center left", bbox_to_anchor=(1.01,0.5), fontsize=fs)

    def resizePlotLegendBelow(self, width=8, heightPlotArea=3):
        '''
        Adapt legend placement and sizing, so that also for very large numbers
        of lines, the legend does not cover the plot.
        The legend is shown below the plot. If necessary, the plot is enlarged
        so the plot area stays roughly the same size.
        '''
        # First figure out what's in the legend.
        # Number of entries, and length of legend text.
        _, l = self._ax.get_legend_handles_labels()
        numEntries=len(l)
        maxlen=0
        for label in l:
            maxlen=max(len(label),maxlen)
        
        # Font size
        fs = min(9,max(3,int(200/np.sqrt(numEntries*maxlen))))

        #First calculate # of columns. Take care that there is some overhead apart from the label
        nc=max(1,int(1000/((maxlen+7)*fs)))
        nl=int(numEntries/nc+0.99)
        
        has_xaxis = self._ax.axes.xaxis.get_visible()
        #has_xannot = len(self._ax.axes.xaxis.get_ticklabels())>0 if has_xaxis else False
        has_xannot = (not self._hideTickLabels) if has_xaxis else False
        has_xlabel = len(self._ax.get_xlabel())>0 if has_xaxis else False
        
        height_l=(nl+1)*fs/50
        height = height_l
        height_t = 0.23
        height += height_t if has_xlabel else 0 # Axis title
        height += height_t if has_xannot else 0 # Axis annottion
        height += height_t # Plot title
        height_p = heightPlotArea
        height += height_p # plot itself
        self._fig.set_size_inches(width, height)
      
        yfrac1=(height_l+2*height_t)/height # offset to resize plot area relative to total
        yfrac2=-(height_l+1.95*height_t)/(height_p) # legend relative to figure
        self._fig.subplots_adjust(bottom=yfrac1, top=0.95)

        self._ax.legend(loc="lower center", bbox_to_anchor=(0.5, yfrac2), ncol=nc, fontsize=fs,  borderaxespad=0.)

            
    def close(self): 
        '''
        Plot is closed. Remove any admin. Subclasses may override.
        '''
        #print("    MatPlotWrapper.close")
        self._fig = None
        self._ax = None
        if not (self._timer is None):
            self._timer.stop()
            self._timer = None
        
        # Let base class wrap up
        GW.GenPlotWrapper.close(self)
        
    def isOpen(self):
        '''
        Is the plot open? Or still in construction?
        '''
        return not (self._ax is None)
        
    def _closePlot(self):
        '''
        close callback, in case we're showing the plot in a custom window
        '''
        #print("    MatPlotWrapper._closePlot()", self._fig is None, self._inDialog is None)
        if not (self._inDialog is None):
            dlg = self._inDialog
            self._inDialog = None
            dlg.closePlot()
        self.callbacksDisconnect()   
        self.close()
        
    def _on_hover(self, event):
        '''
        Callback from hover event
        '''
        if (self._plotted is None): return
        
        if not (self._annotation is None):
            self._annotation.set_visible(False)
            
        if not (self._timer is None):
            self._timer.stop()
        self._timer = MPT.MPTimer(self._fig.canvas.get_tk_widget(), 1000, 
                    lambda: MatPlotWrapper._on_hover_time(self, event))

    def _on_hover_time(self, event):
        '''
        Hover time out callback (internal)
        '''
        self.hoverTimedOut(event)
     
    def hoverTimedOut(self, event):
        '''
        Hover time out callback method that can be overloaded
        '''
        self._timer = None
        (xpt,ypt) = (event.xdata, event.ydata)
        event = self.filterEvent(event)
        if not (event.xdata is None):
            # Init admin
            distMin = 1e37
            labMin = ""
            xscale = event.plot_xscale
            yscale = event.plot_yscale
            #print(xscale, yscale)
            
            # Loop over data stored for the layers
            # In each layer, find the closest point
            # Plot the closest of all
            # TODO: take plotting order inro account
            for (df, xs, ys, indxs, labelKey, layer) in self._plotted:
                l = len(xs)
                for i in range(l):
                    dist = np.sqrt(((xpt - xs[i])/xscale)**2 + ((ypt-ys[i])/yscale)**2)
                    if (dist < distMin):
                        distMin = dist
                        if (not (labelKey is None)) and (labelKey != ""):
                            labMin = str(df.loc[indxs[i]][labelKey])
                        else:
                            labMin = str(indxs[i])
                        if (not (layer is None)) and (layer != ""):
                            labMin += " ("+layer+")"
                            
            # Figure out where in the plot we are
            (xmin, xmax) = self._ax.get_xlim()
            (ymin, ymax) = self._ax.get_ylim()
            xf = (event.xdata-xmin)/(xmax-xmin)
            yf = (event.ydata-ymin)/(ymax-ymin)
            halign = "right" if (xf > 0.5) else "left"
        
            # Are we close enough? Distance depends on zoom!
            if (distMin>10): 
                if not (self._annotation is None):
                    self._annotation.set_visible(False)
            else:
                xpt += 10*xscale 
                ypt += 10*yscale 
                if not (self._annotation is None):
                    self._annotation.set_text(labMin)
                    self._annotation.set_x(xpt)
                    self._annotation.set_y(ypt)
                    self._annotation.set_horizontalalignment(halign)
                else:
                    self._annotation = self._ax.annotate(labMin, 
                        xy=(xpt, ypt), xycoords='data',
                        #xytext=(xpt + xoff, ypt+yoff), textcoords='data',
                        horizontalalignment=halign,
                        #arrowprops=dict(arrowstyle="simple",
                        #connectionstyle="arc3,rad=-0.2"),
                        bbox=dict(boxstyle="round", facecolor="w", 
                        edgecolor="0.5", alpha=0.9)
                )
                self._annotation.set_visible(True)
        elif not (self._annotation is None):
            self._annotation.set_visible(False)
            
        # Force a redraw
        self._fig.canvas.draw()

    def filterEvent(self, event):
        '''
        Filter an event. 
        Add plot coordinates and scale.
        an be overridden for coordinate transformations.
        '''
        #print("   matplotwrapper.filterEvent")
        ia = event.inaxes
        if not (ia is None):
            # Shifted coord to determine scale
            xd1, yd1 = ia.transData.inverted().transform((event.x+1, event.y+1))
            event.plot_xscale = abs(event.xdata - xd1)
            event.plot_yscale = abs(event.ydata - yd1)
            event.plot_scale = None
        else:
            event.xdata = None
            event.ydata = None
            event.plot_xscale = None
            event.plot_yscale = None
            event.plot_scale = None
        return event
        
    def recordPlotted(self, df, xs, zs, indxs, labelKey, layer):
        '''
        Record plotted points (for hover callbacks)
        If no points recorded, no hover callbacks are generated.
        '''
        if (self._plotted is None): self._plotted = list()
        self._plotted.append((df, xs, zs, indxs, labelKey, layer))

    def callbacksConnect(self):
        '''
        After construction, install various callbacks.
        Can be overridden to add more.
        '''
        if not (self._plotted is None):
            self._hovercall = self._fig.canvas.mpl_connect(
                "motion_notify_event", self._on_hover)
        else:
            self._hovercall = None
            
    def callbacksDisconnect(self):
        '''
        Clean up callbacks on closing.
        '''
        if not (self._hovercall is None):
            self._fig.canvas.mpl_disconnect(self._hovercall)
        self._hovercall = None
        if not (self._timer is None):
            self._timer.stop()
            self._timer = None
            
    def hideTickLabels(self):
        self._hideTickLabels = True
    
    def plotColorBar(self, im, caption):
        '''
        Make space for a color bar for plot element 'im'.
        Caption is specified.
        '''
        self._cbarAx = inset_axes(self._ax,
                   width="1.5%",  # width = 5% of parent_bbox width
                   height="50%",  # height : 50%                   
                   loc='center left',
                   bbox_to_anchor=(1.01, 0., 1, 1),
                   bbox_transform=self._ax.transAxes,
                   #width="2.5%",  # width = 5% of parent_bbox width
                   #height="50%",  # height : 50%                   
                   #loc='lower left',
                   #bbox_to_anchor=(1.01, 0., 1, 1),
                   #bbox_transform=self._ax.transAxes,
                   #borderpad=0,
                   )
        #cbar = self._fig.colorbar(im, ax=self._ax, shrink=0.5)
        cbar = self._fig.colorbar(im, cax=self._cbarAx)
        cbar.ax.set_title(caption, loc="left", pad=12, fontsize=9)
        cbar.ax.tick_params(labelsize=9)
            
    def show(self, title=None, fileName=None):
        '''
        Show the plot
        In batch mode, write the output file.
        Can be overridden to extend behavior.
        '''
        # Callbacks for the three modes
        # (TODO: more elegantly?)        
        if not (self._inDialog is None):
            # Connect callbacks for embedded
            self.callbacksConnect()
        elif not (fileName is None):
            # No connection needed in file mode
            pass
        else:
            # Connect callbacks for MPL-interactive
            self.callbacksConnect()
            
        # Axis annotation?
        if (self._hideTickLabels):
            #self._ax.set_axis_off()
            self._ax.xaxis.set_ticklabels([])
            self._ax.yaxis.set_ticklabels([])
        
            
        # Axis labels
        if not (self._xlabel is None):
            self._ax.set_xlabel(self._xlabel)
        if not (self._ylabel is None):
            self._ax.set_ylabel(self._ylabel)
            
        # Title (None or empty string means no title)
        if (title != "") and (not (title is None)):
            self.setTitle(title)
        title = self.getTitle()
        if (title != "") and (not (title is None)):
            self._ax.set_title(self.getTitle(), fontsize= 10, fontweight='bold')
        else:
            title = ""
        
        # Auto-size legend, if needed
        numEntries = len(self._entries)
        if (numEntries>0):
            self.resizePlotLegendBelow()
            
            # # Try to have max. 10 per column
            # nc = 1
            # fs=10.0
            # if(numEntries>20):
                # nc = 3
                # fs = 6.0
            # elif (numEntries>1):
                # nc = 2
                # fs = 9.0
            # nl = int(numEntries/nc+0.99)
            # #print("**MPW: ne", numEntries, "nc", nc, "nl", nl, "fs", fs)
                
            # # Space the plot elements, depends on annotations
            # margin=0.01 # In window coordinates
            # titleSpace=margin # In window coordinates, plot title
            # if (title != ""):
                # titleSpace=0.05
            # xaxisSpace=0.03 # In window coordinates, for numbers+axis title
            # yaxisSpace=0.03 # In window coordinates, for numbers+axis title
            # if not (self._hideTickLabels):
                # xaxisSpace+=0.03 # In window coordinates, for numbers+axis title
                # yaxisSpace+=0.03 # In window coordinates, for numbers+axis title
            # if not (self._xlabel is None): xaxisSpace+=0.06
            # if not (self._ylabel is None): yaxisSpace+=0.06
            # cbarSpace=0
            # if not (self._cbarAx is None):
                # cbarSpace=0.05 # Color bar
            # y0 = 0.05*nl*fs/9 + margin # In window coordinates
            # plotBottom = xaxisSpace+y0 # In window coordinates
            # y0 = (y0 + 2*margin - plotBottom)/(1-titleSpace-plotBottom) # Relative to plot area
            # #print("**MPW: left", yaxisSpace, "right", 1-margin-cbarSpace, "bottom", plotBottom, "top", 1-titleSpace)

            # # Add the legend below the plot
            # self._fig.subplots_adjust(left=yaxisSpace, right=1-margin-cbarSpace)
            # self._fig.subplots_adjust(bottom=plotBottom, top=1-titleSpace)
            # self._ax.legend(loc="upper center", bbox_to_anchor=(0.5*(1-yaxisSpace),y0), ncol=nc, fontsize=fs)
            
            # self._fig.set_figwidth(4)
            # self._fig.set_figheight(1)
            
        ### Don't check final space adjustment
        #self._fig.tight_layout()

        # Display a grid
        self._ax.grid(color='grey', linestyle='dotted', linewidth=0.5)
        
        ## Limits
        #if not (self._xmin is None):
        #    self._ax.set_xlim(self._xmin, self._xmax)
        #elif not (self._dxmin is None):
        #    (xmin, xmax) = self._ax.get_xlim()
        #    dx = max(abs(xmax-xmin), self._dxmin)
        #    self._ax.set_xlim((xmin+xmax)/2-dx/2, (xmin+xmax)/2+dx/2)
        
        if not (self._ymin is None):
            self._ax.set_ylim(self._ymin, self._ymax)
        elif not (self._dymin is None):
            (ymin, ymax) = self._ax.get_ylim()
            dy = max(abs(ymax-ymin), self._dymin)
            self._ax.set_ylim((ymin+ymax)/2-dy/2, (ymin+ymax)/2+dy/2)
        
        # Go, go, go
        if not (self._inDialog is None):
            ed = ED.EmbedPlotInDialog(self._fig, self._inDialog, 
                        closeCmd=self._closePlot, filterEvent = self.filterEvent)
        elif not (fileName is None):
            plt.ioff()
            plt.savefig(fileName, dpi=600)
            ML.LogMessage("File {:s} written".format(fileName))
            #plt.show()
            #plt.clf()
            plt.close()
            self.close()
        else:
            # Let matplotlib do the rest
            #print("        plt.show")
            plt.show()
            plt.close()
            self.close()

    def setXRange(self, xmin, xmax):
        ''' Set plot x range '''
        self._xmin = xmin
        self._xmax = xmax
        
    def getXRange(self):
        ''' Get plot x range '''
        return (self._xmin, self._xmax)
    
    def setMinXRange(self, dxmin):
        ''' 
        Set minimum x range extent (to avoid excessive zoom in
        if all heights the same)
        '''
        self._dxmin = dxmin
        
    def setYRange(self, ymin, ymax):
        ''' Set plot y range '''
        self._ymin = ymin
        self._ymax = ymax
        
    def setMinYRange(self, dymin):
        ''' 
        Set minimum y range extent (to avoid excessive zoom in
        if all heights the same)
        '''
        self._dymin = dymin
    
    def setXLabel(self, xlabel):
        ''' Set plot x axis label range '''
        self._xlabel = xlabel
        
    def setYLabel(self, ylabel):
        ''' Set plot y axis label '''
        self._ylabel = ylabel
        
    def getColorScale(self, **kwargs):
        '''
        Get colorscale in format for LinearSegmentedColorscale.
        
        Overloads baseclass method to change the format.
        '''
        colors = GW.GenPlotWrapper.getColorScale(self, **kwargs)
        
        # Invert lookup axis order, and values from 0-1 (for matplotlib)
        red = list()
        green = list()
        blue = list()
        vals = list(colors.keys())
        vals.sort()
        sc = 255
        for p in vals:
            red.append((p,colors[p][0]/sc,colors[p][0]/sc))
            green.append((p,colors[p][1]/sc,colors[p][1]/sc))
            blue.append((p,colors[p][2]/sc,colors[p][2]/sc))
            
        colors={"red":red, "green": green, "blue": blue}
        
        return colors
        
    def addLine(self, pts, label=None, useForZoom = False):
        '''
        Add a line to the graph
        '''
        # Open the plot (if needed), ...
        if (self._ax is None):     
            self.openFigure()
        ax = self._ax
        
        # Values
        ptsz = list(zip(*pts))
        x = ptsz[0]
        y = ptsz[1]
        
        # Default label
        if (label is None):
            label="Line"
        
        # Create the plot
        ax.plot(x, y, label=label, color="black", scalex=useForZoom, scaley=useForZoom)

