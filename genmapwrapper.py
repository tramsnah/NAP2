'''
Generic (abstract) base classes to facilitate managing various
kinds of maps (folium, contextily/matplotlib)
'''        
from shapely.geometry import Point, Polygon
#from shapely.geometry import MultiPoint
import geopandas as gpd
import pandas as pd

from . import coordsys as CS

CRS_RD=CS.CRS_RD
CRS_WGS84=CS.CRS_WGS84 # (4326 = lon,lat)
CRS_TILE=CS.CRS_TILE # Used in web tile services

class GenMapWrapper:
    '''
    Generic (abstract) base class to facilitate managing various
    kinds of maps.
    Offers utilities for basic CRS transformations
    
    TODO: Fix peilmerk key defaults
    '''        
    def __init__(self,  xkey="", ykey="", pmkey="", warp=False):  
        # TODO: Solve differently, to break 'magic' link to PMDB
        if (xkey is None or xkey==""): xkey = "X"
        if (ykey is None or ykey==""): ykey = "Y"
        if (pmkey is None or pmkey==""): pmkey = "Peilmerk"
        
        self.xkey = xkey
        self.ykey = ykey
        self.pmkey = pmkey
        self.warp = warp
    
    def convertToGeoSeries(self, df):
        '''
        Utility to convert various inputs to
        GeoSeries.
        Inputs can be GeoDataFrame, DataFrame, Polygon
        or list of Point.
        '''
        if (isinstance(df, gpd.GeoDataFrame)):
            # GeoDataFrame
            # Let's define our raw data, whose epsg is 28992 (RD)
            gs = df.geometry            
        elif (isinstance(df, pd.DataFrame)):
            # DataFrame
            geometry=[Point(xy) for xy in zip(df[self.xkey],df[self.ykey])]
            gs = gpd.GeoSeries(geometry)
            gs.set_crs(epsg=CRS_RD, inplace=True)
        elif (isinstance(df, Polygon)):
            # TODO: complex polygons?
            x, y = df.exterior.coords.xy
            geometry=[Point(xy) for xy in zip(x,y)]
            gs = gpd.GeoSeries(geometry)
            gs.set_crs(epsg=CRS_RD, inplace=True)
        else:
            # list of points or xy tuples
            assert(isinstance(df, list))
            if (isinstance(df[0],Point)):
                gs = gpd.GeoSeries(df)
                gs.set_crs(epsg=CRS_RD, inplace=True)
            else:
                assert(isinstance(df[0],tuple))
                geometry=[Point(xy) for xy in df]
                gs = gpd.GeoSeries(geometry)
                gs.set_crs(epsg=CRS_RD, inplace=True)
        return gs
        
    def convertToGeoDataFrame(self, df):
        '''
        Utility to convert various inputs to
        GeoDataFrame.
        Inputs can be GeoDataFrame, DataFrame, Polygon
        or list of Point.
        '''
        if (isinstance(df, gpd.GeoDataFrame)):
            # GeoDataFrame
            # Let's define our raw data, whose epsg is 28992 (RD)
            gdf = df           
        elif (isinstance(df, pd.DataFrame)):
            # Let's define our raw data, whose epsg is 28992 (RD)
            geometry=[Point(xy) for xy in zip(df[self.xkey],df[self.ykey])]
            gdf = gpd.GeoDataFrame(df, geometry=geometry)
            gdf.set_crs(epsg=CRS_RD, inplace=True)
        else:
            # list of points
            assert(isinstance(df, list))
            if (isinstance(df[0], tuple)):
                df = [Point(x,y) for (x,y) in df]
            assert(isinstance(df[0],Point))
            gdf = gpd.GeoDataFrame([1]*len(df), geometry=df)
            gdf.set_crs(epsg=CRS_RD, inplace=True)
        return gdf
        
    def getMapBounds(self, expand=1):
        '''
        To be overloaded to return the bounds of the currently shown map
        '''
        assert(0)
        
    def getCRS(self):
        '''
        To be overloaded to return the CRS in which the map is plotted
        '''
        assert(0)
