'''
Module provides class for map plotting (in matplotlib/contextily).
There is also a folium version.
'''
import numpy as np
from shapely.geometry import Point, MultiPoint
# from shapely.geometry import Polygon
import geopandas as gpd
import pandas as pd

import traceback

from matplotlib_scalebar.scalebar import ScaleBar
from matplotlib import colors as col
import contextily as ctx

from . import matplotwrapper as MPW
from . import genmapwrapper as GMW
from . import mptimer as MPT

CRS_RD = GMW.CRS_RD
CRS_TILE = GMW.CRS_TILE

DISTANCE_KEY = "Distance"

_map_sources={
        "CartoDB": ctx.providers.CartoDB.Voyager,
        "WorldStreetMap": ctx.providers.Esri.WorldStreetMap,
        "NLStandaard": ctx.providers.nlmaps.standaard,
        "NLLuchtfoto": ctx.providers.nlmaps.luchtfoto,
        "OSMMapnik": ctx.providers.OpenStreetMap.Mapnik,
        "OpenTopo": ctx.providers.OpenTopoMap,
        "":None
        }
    
class GPWrapper(GMW.GenMapWrapper, MPW.MatPlotWrapper):
    '''
    Wrapper for map plotting (in matplotlib/contextily).
    There is also a folium version.
    '''
    def __init__(self, name, mgr, inDialog = None, warp=False):
        GMW.GenMapWrapper.__init__(self, warp = warp)
        MPW.MatPlotWrapper.__init__(self, name, mgr, "GeoMatPlotMap", inDialog = inDialog)
        
        self._cmaps = dict()

        # We keep track of data limits
        self._xmind=1e38
        self._xmaxd=-1e38
        self._ymind=1e38
        self._ymaxd=-1e38
        
        self._x_called = 0
        self._y_called = 0
        self._zoomcallx = None
        self._zoomcally = None
        self._hovercall = None
        
        self._warp = warp
        
        self._timer = None
        self._annotation = None
        self._plotted = None

        self._crs = None

        self._timerB = None
        
    def _getMapSource(self, key="WorldStreetMap"):
        try:
            source = _map_sources[key]
        except KeyError:
            source = None
        return source

    def plotBasemapInteractive(self):
        print("GPWrapper.plotBasemapInteractive")
        #for line in traceback.format_stack():
        #    print(line.strip())
        
        #if (self._timerB is None):
        #    self._timerB = MPT.MPTimer(self._inDialog.getWidget(), 1000, 
        #            lambda: GPWrapper._after_redraw_request(self))
        #else:
            #self._timerB.start(1000)

    #def _after_redraw_request(self):
        #print("GPWrapper._after_redraw_request")
        self.plotBasemap()
        
    def plotBasemap(self, xtraZoom=0):     
        '''
        Add basemap (contextily) to plot
        Called just before we're done
        '''   
        
        # Source of map
        mapSrc=self._getMapSource()
        if (mapSrc is None):
            return

        # Recalculate zoom level
        xmin, xmax = self._ax.get_xlim()
        ymin, ymax = self._ax.get_ylim()
        dx = abs(xmax-xmin)
        dy = abs(ymax-ymin)
        zoom = 26 - int(np.log((dx+dy)/2)/np.log(2)) + xtraZoom
        
        # Test if zoom: 28 is valid or not?
        retval = mapSrc.get("max_zoom", zoom)
        #print("    plotting map, zoom=", zoom, "max: ", retval)
        zoom = min(zoom, retval)
        
        # Plot the map
        ctx.add_basemap(self._ax, zoom=zoom, source=mapSrc, crs=self._crs)
    
    def getCRS(self):
        '''
        Can be RD or the format commonly used by tiling service
        '''
        return CRS_RD if (self._warp) else CRS_TILE
    
    def addPoints(self, df, zKey=None,
                    labelKey=None,
                    cname=None, color=None, edgeColor=None, # TODO
                    layer=None, size=1,
                    useForZoom=True, marker=None, zorder=None):
        '''
        Add points to map. Can be called multiple times.
        Data provided as geodataframe, zkey column contains height diffs,
        labelKey optional popups.
        The points are called 'layer' (for legend).
        If 'useForZoom' is False, the map is not zoomed out to accomodate the data.
        'cname' specifies the name of the color map to use (if non-default), 'color'
        the color to use no z-value coloring is to be used.
        '''
        # Make sure we're a geodataframe
        df = self.convertToGeoDataFrame(df)
        
        # Convert (if needed) to target CRS
        df2 = df.to_crs(epsg=CRS_RD if (self._warp) else CRS_TILE)
                
        # Get output as Point list, then convert to x,y
        # TODO: Plot straight from geodataframe!?
        xo = [p.x for p in df2.geometry.to_list()]
        yo = [p.y for p in df2.geometry.to_list()]

        # Z data (assumes df is (geo)dataframe)
        if (zKey is None): zKey = ""
        if (zKey != ""):
            assert(isinstance(df,(pd.DataFrame, gpd.GeoDataFrame)))
            zvalues = list(df[zKey].values)

        # Store the CRS
        self._crs = df2.crs
        
        # Check color map is defined
        if (zKey != ""):
            if (len(self._cmaps)==0):
                raise KeyError("No Color map defined")
            if (cname is None):
                cname=next(iter(self._cmaps))
            elif not (cname in self._cmaps):
                raise KeyError("Color map '"+str(cname)+"' not defined")
        
        # Default color (if no zvalues)
        if (color is None): color = ""
        if (color == ""): color='blue'

        # Open the plot (if needed), ...
        if (self._ax is None):     
            self.openFigure()
            
        # Marker from list?
        if (isinstance(marker, (int, float))):
            marker = self.getMarkerStyle(marker)
            
        # Other arguments
        kwargs=dict()
        if not (zorder is None):
            kwargs["zorder"] = zorder
            
        if not (labelKey is None):
            if (self._plotted is None):
                self._plotted = list()
            self._plotted.append((df, labelKey, zKey, layer))
            
        # ... then add the data
        if (zKey==""):
            im = self._ax.scatter(xo, yo, 
                        #scalex=useForZoom, scaley=useForZoom,
                        c=color, s=size*5, label=layer,
                        linewidth=1.3 if color == "none" else .3,
                        marker="o" if marker is None else marker,
                        edgecolors="black" if edgeColor is None else edgeColor, **kwargs)
        else:
            im = self._ax.scatter(xo, yo, 
                        #scalex=useForZoom, scaley=useForZoom,
                        s=size*5, c=zvalues, 
                        cmap=self._cmaps[cname]["cmap"],
                        vmin=self._cmaps[cname]["min"], 
                        vmax=self._cmaps[cname]["max"], 
                        linewidth=.3, label=layer,
                        marker="o" if marker is None else marker,
                        edgecolors="black" if edgeColor is None else edgeColor, **kwargs)
                                    
            # Show the legend for this colorbar
            if (not ("shown" in self._cmaps[cname])) or (not self._cmaps[cname]["shown"]):
                self.plotColorBar(im, self._cmaps[cname]["caption"])
                self._cmaps[cname]["shown"] = True

        # Record the line (so we can later scale the legend)
        self.addEntry(layer)
        
        if (useForZoom):
            self._updateBounds((min(xo), min(yo), max(xo), max(yo)))
    
    def _updateBounds(self, bounds):
        self._xmind=min(self._xmind, bounds[0])
        self._xmaxd=max(self._xmaxd, bounds[2])
        self._ymind=min(self._ymind, bounds[1])
        self._ymaxd=max(self._ymaxd, bounds[3])
        
    def getMapBounds(self, expand=1):
        '''
        Get current map bounds (in RD)
        '''
        # Bounds are in map coordinates
        xys=[(self._xmind, self._ymind), (self._xmaxd, self._ymaxd)]
        gs = gpd.GeoSeries(MultiPoint(xys), crs=self._crs)

        # Convert back to RD
        gs2 = gs.to_crs(epsg=CRS_RD)

        # Get output as Point list, convert to x,y list
        xy_o = [(p.x, p.y) for p in list(gs2.to_list()[0].geoms)]
        print(xy_o)
        
        # Return
        x_avg = (xy_o[0][0] + xy_o[1][0])/2
        y_avg = (xy_o[0][1] + xy_o[1][1])/2
        dx = (xy_o[1][0] - xy_o[0][0])
        dy = (xy_o[1][1] - xy_o[0][1])
        dx *= expand
        dy *= expand 
        bounds = (x_avg-dx/2, y_avg-dy/2, x_avg+dx/2, y_avg+dy/2)
        print(bounds)

        # TODO: Need to prelude on extension for aspect ratio
        return bounds
      
    #def _on_limx_change(self, _):
    #    ''' zoom callback'''
    #    self._x_called += 1
    #    if self._y_called == 1:
    #        self._on_lim_change()
    #
    #def _on_limy_change(self, _):
    #    ''' zoom callback '''
    #    self._y_called += 1
    #    if self._x_called == 1:
    #        self._on_lim_change()
    #
    #def _on_lim_change(self):
    #    ''' called from either zoom callback '''
    #    self._x_called += 1
    #    self._y_called += 1
    #    
    #    if not (self._inDialog is None):
    #        # Wrap up background
    #        self.plotBasemapInteractive()
    #    else:
    #        self.plotBasemap()
    #    
    #    self._x_called = 0
    #    self._y_called = 0

    def hoverTimedOut(self, event):
        '''
        If we've hovered somewhere longer than a certain
        period, this method is called.
        Pop up info from closest point.
        Overridden from base class because of coord transforms.
        '''
        self._timer = None
        
        (xpt,ypt) = (event.xdata, event.ydata)
        event = self.filterEvent(event)
        if not (event.xdata is None):
            # Init admin
            distMin = 1e37
            labMin = ""
            scale = event.plot_scale
            
            # Loop over data stored for the layers
            # In each layer, find the closest point
            # Plot the closest of all
            # Todo: take plotting order inro account
            for (df, labelKey, zKey, layer) in self._plotted:
                pxy = Point(event.xdata, event.ydata)
                df[DISTANCE_KEY]=df.distance(pxy)
                idx = df[DISTANCE_KEY].idxmin()
                lDistMin = df[DISTANCE_KEY].loc[idx]
                lLabMin = df[labelKey].loc[idx]
                if (not (layer is None)) and (layer != ""):
                    lLabMin += " ("+layer+")"
                if (lDistMin<=distMin):
                    distMin = lDistMin
                    labMin = lLabMin
            
            # Are we close enough? Distance depends on zoom!
            if (distMin>10*scale):
                if not (self._annotation is None):
                    self._annotation.set_visible(False)
            else:
                xpt += 10*scale 
                ypt += 10*scale 
                if not (self._annotation is None):
                    self._annotation.set_text(labMin)
                    self._annotation.set_x(xpt)
                    self._annotation.set_y(ypt)
                else:
                    self._annotation = self._ax.annotate(labMin, 
                        xy=(xpt, ypt), xycoords='data',
                        #xytext=(xpt + xoff, ypt+yoff), textcoords='data',
                        horizontalalignment="left",
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
        Add plot x,y,scale to event.
        Overridden base class methods to apply coord transform.
        '''
        #print("    geopandamapwrapper.filterEvent")
        ia = event.inaxes
        if not (ia is None):
            # Convert from espg used to RD, whose epsg is 28992 (RD)
            xy = (event.xdata, event.ydata)
            gs = gpd.GeoSeries(Point(xy), crs=self._crs)
            gs2 = gs.to_crs(epsg=28992)
            xy_o = [(p.x, p.y) for p in list(gs2.to_list())]
            
            # Store the first member back
            event.xdata = xy_o[0][0]
            event.ydata = xy_o[0][1]

            # Shifted coord to determine scale
            xd1, yd1 = ia.transData.inverted().transform((event.x+1, event.y+1))
            xy1 = (xd1, yd1)
            gs = gpd.GeoSeries(Point(xy1), crs=self._crs)
            gs2 = gs.to_crs(epsg=28992)
            xy_o1 = [(p.x, p.y) for p in list(gs2.to_list())]
            scale = np.sqrt((xy_o[0][0]-xy_o1[0][0])**2 + (xy_o[0][1]-xy_o1[0][1])**2)
            event.plot_scale = scale
        else:
            event.xdata = None
            event.ydata = None
            event.plot_xscale = None
            event.plot_yscale = None
            event.plot_scale = None
            
        return event
    
    def callbacksConnect(self):
        '''
        Connect callbacks.
        Overridden from base class to add zoom callback.
        '''
        MPW.MatPlotWrapper.callbacksConnect(self)
        self._x_called = 0
        self._y_called = 0
        #self._zoomcallx = self._ax.callbacks.connect(
        #    'xlim_changed', self._on_limx_change)
        #self._zoomcally = self._ax.callbacks.connect(
        #    'ylim_changed', self._on_limy_change)
        #self._hovercall = self._fig.canvas.mpl_connect(
        #    "motion_notify_event", self._on_hover)
            
    def callbacksDisconnect(self):
        '''
        Disconnect callbacks.
        Overridden from base class to add zoom callback.
        '''
        MPW.MatPlotWrapper.callbacksDisconnect(self)
        self._ax.callbacks.disconnect(self._zoomcallx)
        self._ax.callbacks.disconnect(self._zoomcally)
        self._zoomcallx = None
        self._zoomcally = None
        #self._fig.canvas.mpl_disconnect(self._hovercall)
        #self._hovercall = None
    
    def show(self, fileName=None, **kwargs):
        '''
        Show the plot, after updating the base map (contextily)
        In batch mode, write the file.
        '''
        if (self._inDialog):
            widg = self._inDialog.getWidget().master
            w = widg.winfo_width()
            h = widg.winfo_height()
            h -= 100
        else:
            cSize = self._fig.get_size_inches()
            w = cSize[0]
            h = cSize[1]
        aspect = 1.5
        if (w>1 and h>1):
            aspect = w/h
        print("****GPWrapper: size", w, h, aspect)
        
        # Set limits a bit wider than the data
        if (self._xmind<self._xmaxd):
            dx = (self._xmaxd-self._xmind)
            dy = (self._ymaxd-self._ymind)
            print("GPW before", dx, dy)
            dx *= 1.1
            dy *= 1.1
            if (dx < aspect*dy):
                dx = dy*aspect
            else:
                dy = dx/aspect
            avx = (self._xmaxd+self._xmind)/2
            avy = (self._ymaxd+self._ymind)/2
            self._xmin = avx - dx/2
            self._xmax = avx + dx/2
            self._ymin = avy - dy/2
            self._ymax = avy + dy/2
            print("GPW after", dx, dy)
            
            self._ax.set_xlim(self._xmin, self._xmax)
            self._ax.set_ylim(self._ymin, self._ymax)
            
            self._ax.set_aspect('equal')
        
        # Unless we display in RD, axes not meaningful
        if not self._warp:
            self.hideTickLabels()
            
            # We do want a scalebar
            self._ax.add_artist(ScaleBar(1))
        
        # Background and callbacks for the three modes
        # (TODO: more elegantly?)        
        if not (self._inDialog is None):
            # Wrap up background
            self.plotBasemapInteractive()
            
            # Connect callbacks
            self.callbacksConnect()
        elif not (fileName is None):
            # Wrap up background
            self.plotBasemap(xtraZoom=2)
        else:
            # Wrap up background
            self.plotBasemap()

            # Connect callbacks
            self.callbacksConnect()

        # Rest is done by base class
        MPW.MatPlotWrapper.show(self, fileName=fileName, **kwargs)
                    
    def addColormap(self,cname,cmin,cmax,inverse=False,caption=None):
        '''
        Add a color map by name 'cmap' with specified range.
        '''
        cmap = col.LinearSegmentedColormap("gui_cmap", self.getColorScale(inverted=inverse))
        
        if (caption is None):
            caption=cname

        self._cmaps[cname] = {"cmap": cmap, "min": cmin, "max": cmax, "caption": caption}
        
    def addPolygon(self, df, useForZoom=True, color=None):
        '''
        Add polygon to map
        '''
        # Let's define our raw data, whose epsg is 28992 (RD)
        gs = self.convertToGeoSeries(df)            
        
        # Convert (if needed) to target CRS
        gs2 = gs.to_crs(epsg=CRS_RD if (self._warp) else CRS_TILE)
                
        # Get output as Point list, then convert to x,y
        # TODO: Plot straight from geodataframe!?
        xo = [p.x for p in gs2.to_list()]
        yo = [p.y for p in gs2.to_list()]
 
        # Store the CRS
        self._crs = gs2.crs
        
        # Open the plot (if needed), ...
        if (self._ax is None):     
            self.openFigure()
            
        # Default color
        if (color is None):
            color = "black"
            
        # ... then add the data
        self._ax.plot(xo, yo, scalex=useForZoom, scaley=useForZoom, c=color)
        
        if (useForZoom):
            self._updateBounds((min(xo), min(yo), max(xo), max(yo)))

    def addAnnotations(self, coords, annotations):
        # Make sure we're a geodataframe
        df = self.convertToGeoDataFrame(coords)
        
        # Convert (if needed) to target CRS
        df2 = df.to_crs(epsg=CRS_RD if (self._warp) else CRS_TILE)

        # Annotate
        for indx, p in enumerate(df2.geometry.to_list()):
            self._ax.annotate(annotations[indx], (p.x, p.y), xytext=(p.x+1500, p.y+1500),
                                arrowprops=dict(arrowstyle="->", facecolor='black'))
        
    def addShapes(self, shapes, useForZoom=True):
        '''
        Add shapes to map
        '''
        assert(0) # not implemented
        pass
        
    def addGridToContour(self, X2,Y2,S2, cname=None):
        '''
        Add grid contours to map
        '''
        assert(0) # not implemented
        pass
    