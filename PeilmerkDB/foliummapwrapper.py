'''
Module provides wrapper object to generate folium maps
(there is an outwardly identical wrapper for
matplotlib maps)
Can only be run in batch.
'''
import geopandas as gpd

import folium
import branca.colormap as cm

#import shapefile
from shapely.geometry import Polygon, MultiPoint
#from shapely.geometry import MultiPolygon, Point
from skimage import measure

from . import genplotwrapper as GW
from . import genmapwrapper as GMW
from . import messagelogger as ML

CRS_RD = GMW.CRS_RD
CRS_WGS84 = GMW.CRS_WGS84

################################################################################

class FoliumWrapper(GMW.GenMapWrapper, GW.GenPlotWrapper):
    '''
    Wrapper object to generate folium maps
    (there is an outwardly identical wrapper for
    matplotlib maps)
    Can only be run in batch.
    '''
    def __init__(self, name, mgr, warp=False):
        GMW.GenMapWrapper.__init__(self, warp = warp)
        GW.GenPlotWrapper.__init__(self, name, mgr, "folium")
        
        assert(not warp)
        
        self._kol = folium.Map(tiles=None, control_scale=True)
        folium.TileLayer(         
            tiles = 'http://services.arcgisonline.com/arcgis/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
            attr = 'Esri',
            name = 'World Street Map',
            overlay = False,
            control = True).add_to(self._kol)            
        folium.TileLayer('openstreetmap', name = 'Open Street Map').add_to(self._kol)
        folium.TileLayer('stamentoner', name = 'Black & White').add_to(self._kol)
        folium.TileLayer('cartodbpositron', name = 'Light').add_to(self._kol)
        folium.TileLayer('cartodbdark_matter', name = 'Dark').add_to(self._kol)
        folium.TileLayer(
            tiles = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr = 'Esri',
            name = 'Satellite',
            overlay = False,
            control = True).add_to(self._kol)
        #folium.TileLayer('Stamen Terrain').add_to(self._kol)
        #folium.TileLayer('HERE.normalday').add_to(self._kol)
        self._ll_min=(1e38,1e38)
        self._ll_max=(-1e38,-1e38)
        self._layers={}
        self._cmaps={}
        
        self._inProgress = True

    def _updateBounds(self,lat, lon):
        self._ll_min=(min(self._ll_min[0],lat),
                            min(self._ll_min[1],lon))
        self._ll_max=(max(self._ll_max[0],lat),
                            max(self._ll_max[1],lon))
                            
    def getMapBounds(self, expand=1):
        '''
        Get map bounds (in RD)
        '''
        assert(0)# Convert to RD
        return (*self._ll_min, *self._ll_max)
        
    def _getLayer(self, lname):
        '''
        Access plot layer 'lname'
        '''
        if (not lname in self._layers):
            self._layers[lname]=folium.FeatureGroup(name=lname).add_to(self._kol)
        return self._layers[lname]
    
    def getFileExtension(self):
        '''
        File extension is html
        '''
        return "html"
    
    def getCRS(self):
        '''
        Coordinate system from tiling
        '''        
        return CRS_WGS84
        
    def show(self, fileName=None, title=""):
        '''
        Write the output file
        '''
        if (fileName is None):
            fileName="FoliumMap.html"
        self._kol.fit_bounds([self._ll_min,self._ll_max])
        folium.LayerControl().add_to(self._kol)
        self._kol.save(outfile=fileName)
        
        ML.LogMessage("File {:s} written".format(fileName))
        
        # We're done
        self.close()
        
    def close(self):
        '''
        "close" the plot. For this class a dummy, since only batch plotting
        is supported
        '''
        self._inProgress = False

        # Let base class wrap up
        #print("FoliumWrapper.close")
        GW.GenPlotWrapper.close(self)
    
    def isOpen(self):
        '''
        Returns True until output file is written
        '''
        return self._inProgress
    
    def addColormap(self,cname,cmin,cmax,inverse=False,caption=None):
        '''
        Add a colormap 'cname', with specified range
        '''
        cdict = self.getColorScale(inverted=inverse)

        index = list(cdict.keys())
        index.sort()
        colors = [cdict[v] for v in index]
        index = [cmin + (cmax-cmin)*v for v in index]

        if (caption is None):
            caption=cname
        self._cmaps[cname] = cm.LinearColormap(colors=colors, 
            index=index, vmin=cmin,vmax=cmax,
            caption=caption)
        self._cmaps[cname].add_to(self._kol)
         
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
        if (layer is None):
            layer="Points"
        flyr=self._getLayer(layer)

        zValues = None
        if not (zKey is None):
            zValues = list(df[zKey].values)
            if (len(self._cmaps)==0):
                raise KeyError("No Color map defined")
            if (cname is None):
                cname=next(iter(self._cmaps))
            elif not (cname in self._cmaps):
                raise KeyError("Color map '"+str(cname)+"' not defined")
 
        labels = None
        if not (labelKey is None):
            labels = list(df[labelKey].values)
  
        if (color is None):
            color='blue'
        
        # Make sure we're a geodataframe
        df = self.convertToGeoDataFrame(df)
        
        # Convert (if needed) to target CRS 
        df2 = df.to_crs(epsg=CRS_WGS84)
                
        # Get output as Point list, then convert to x,y
        # TODO: Plot straight from geodataframe!?
        lons = [p.x for p in df2.geometry.to_list()]
        lats = [p.y for p in df2.geometry.to_list()]

        npts=len(df)
        for i in range(npts):
            (lon, lat) = (lons[i], lats[i])
            if (useForZoom):
                self._updateBounds(lat, lon)
            if not (zValues is None):
                fcolor=self._cmaps[cname](zValues[i])
            else:
                fcolor=color
            if not (labels is None):
                ftxt=str(labels[i])
            else:
                ftxt=None
            folium.CircleMarker((lat,lon), radius=1*size, 
                        color=fcolor, popup=ftxt, fill=True).add_to(flyr)
        
    def addPolygon(self, polygon_points, useForZoom=True):
        '''
        Add oolygon to plot
        '''
        assert(0) # not implemented
        pass
        
    def addShapes(self, shapes, useForZoom=True):
        '''
        Add shapes to plot
        '''
        assert(0) # untested
        flyr=self._getLayer("Shapes")
            
        # Check the parts in the shape
        for shp in shapes:
            pts=shp.parts
            pts.append(len(shp.points)+1)

        # Loop over the parts (this is ugly)
        # AND WRONG
        for i in range(len(pts)-1):
            p = Polygon(shp.points[pts[i]:pts[i+1]])
            # Convert to lat/lon
            locs=[]
            xs, ys = p.exterior.xy
            for x,y in zip(xs,ys):
                lat,lon = self._convertFromRD((x,y))
                if (useForZoom):
                    self._updateBounds(lat, lon)
                locs.append((lat,lon))
            folium.PolyLine(locs,
                    color='black',
                    weight=1,
                    opacity=0.8).add_to(flyr)
    
    def addGridToContour(self, X2,Y2,S2, cname=None):
        '''
        Add grid for contouring to plot
        '''
        assert(0) # untested
        flyr=self._getLayer("Contours")
        
        # Loop over contour levels
        for cc in range(10,100,5):
            # Determine contout
            SC=measure.find_contours(S2, cc)
            # A contour can consist of multiple parts!
            ncont=len(SC)
            for icont in range(ncont):
                lcont=len(SC[icont])
                xyds=[]
                for jcont in range(lcont):
                    (x,y)=SC[icont][jcont]
                    ix=int(x)
                    iy=int(y)
                    fx=x-ix
                    fy=y-iy
                    xd=(X2[ix,iy]*(1-fx)*(1-fy) + X2[ix+1,iy]*fx*(1-fy) + 
                        X2[ix,iy+1]*(1-fx)*fy   + X2[ix+1,iy+1]*fx*fy)
                    yd=(Y2[ix,iy]*(1-fx)*(1-fy) + Y2[ix+1,iy]*fx*(1-fy) + 
                        Y2[ix,iy+1]*(1-fx)*fy   + Y2[ix+1,iy+1]*fx*fy)
                    xyds.append((xd,yd))

                ll_contour=[]
                for x,y in xyds:
                    lat,lon = self._convertFromRD((x,y))
                    self._updateBounds(lat, lon)                    
                    ll_contour.append((lat,lon))
                
                if (cname is None):
                    ccolor='red'
                else:
                    ccolor=self._cmaps[cname](cc)
                folium.Polygon(ll_contour,
                                fill_color=ccolor,#'blue',
                                fill_opacity=0.1,
                                color=ccolor,
                                weight=1,
                                opacity=0.8).add_to(flyr)

    def _convertFromRD(self, xy):  
        '''
        Convert xy's from RD to lon,lat
        '''
        # Convert from espg used to RD, whose epsg is 28992 (RD)
        gs = gpd.GeoSeries(MultiPoint(xy), crs=CRS_RD)

        # Convert to lat/lon (WGS84)
        gs2 = gs.to_crs(epsg=CRS_WGS84)

        # Get output as Point list, convert to x,y list
        xy_o = [(p.x, p.y) for p in list(gs2.to_list()[0].geoms)]
        return xy_o
