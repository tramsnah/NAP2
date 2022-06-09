'''
Classes and functions to manage a database of peilmerken and
(leveling) measurements
'''
import pickle
import copy
import datetime
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
import progressbar as pb

from . import pmexception as BE
from . import messagelogger as ML
from . import calcalignment as CA
from . import coordsys as CS

# Keys for dataframes
PEILMERK_KEY="Peilmerk"
SRCFILE_KEY="Source"
X_KEY="X"
Y_KEY="Y"
SSOURCE_KEY="SrcSurvey"
HGT_KEY="Hgt"
DATE_KEY="Date"
SURVEY_KEY="Survey"
SUBSURVEY_KEY="SubSurveys"
MASTERSURVEY_KEY="MasterSurvey"
REFPEILMERK_KEY="RefPeilmerk"
UNSTABLE_KEY="Unstable"
COMMENT_KEY="Comment"
DISTANCE_KEY="Distance"
PRJID_KEY="ProjectID"

# For output
DIFF_KEY="Diff"
NEIGHBOUR_KEY="Neighbour"
COORD_KEY="geometry"

# Allowed threshold in location inaccuracy [m]
DIST_THRESH=50

# Preferred CRS
CRS_RD=CS.CRS_RD

# Lat/lon
CRS_LATLON=CS.CRS_WGS84

# Alignment-related
MEDIAN=CA.MEDIAN
MERGE=CA.MERGE
ALIGN="align"

# Data extraction types
NO_ALIGNMENT=""
ADD_MEDIAN="add_median"
ADD_MERGE="add_merge"
ALIGN_MEDIAN=ALIGN+"_median"
ALIGN_ALL=ALIGN+"_all"
ALIGN_ALL_SEGMENT=ALIGN+"_all_segment"

T0 = CA.T0
DEFAULT_ALIGN_DATE = T0

# Internal key to store (# of) years for which a peilmerk has data
# so we can efficiently filter on it
YEARS_KEY = "Years"
        
#############################################################################
        
def WrapTZListToHeightFrame1(tzData, skey1=SURVEY_KEY, zKey=HGT_KEY):
    '''
    Convert dict of tzpair lists to dataframe
    '''
    tzDict1 = dict()
    for lsrvy in tzData:
        tzPairs = tzData[lsrvy]
        ll = len(tzPairs)
        tzDict2 = dict()
        tzDict2[zKey]=list()
        tzDict2[DATE_KEY]=list()
        for i in range(ll):
            tz = tzPairs[i]
            date = T0+datetime.timedelta(float(tz[0]))
            tzDict2[DATE_KEY].append(date)
            tzDict2[zKey].append(tz[1])
        tzDict2[skey1] = [lsrvy]*len(tzDict2[zKey])
        if (len(tzDict1)==0):
            tzDict1 = tzDict2
        else:
            for lst, tzP in tzDict2.items():
                tzDict1[lst].extend(tzP)
    
    df = pd.DataFrame(tzDict1)
    
    return df
    
def WrapTZListToHeightFrame2(tzData, skey1=SURVEY_KEY, skey2=PEILMERK_KEY, zKey=HGT_KEY):
    '''
    Convert 2-level dict of tzpair lists to dataframe
    '''
    tzDict0 = dict()
    for lspm in tzData:
        tzDict1 = dict()
        for lsrvy in tzData[lspm]:
            tzPairs = tzData[lspm][lsrvy]
            ll = len(tzPairs)
            tzDict2 = dict()
            tzDict2[zKey]=list()
            tzDict2[DATE_KEY]=list()
            for i in range(ll):
                tz = tzPairs[i]
                date = T0+datetime.timedelta(float(tz[0]))
                tzDict2[DATE_KEY].append(date)
                tzDict2[zKey].append(tz[1])
            tzDict2[skey1] = [lsrvy]*len(tzDict2[zKey])
            if (len(tzDict1)==0):
                tzDict1 = tzDict2
            else:
                for lst, tzP in tzDict2.items():
                    tzDict1[lst].extend(tzP)
        tzDict1[skey2]=[lspm]*len(tzDict1[zKey])
        if (len(tzDict0)==0):
            tzDict0 = tzDict1
        else:
            for lst, tzP in tzDict1.items():
                tzDict0[lst].extend(tzP)
    
    df = pd.DataFrame(tzDict0)

    return df
        
#############################################################################

class SurveyNotFound(BE.PMException):
    '''
    Failure in processing RWS NAP metafile
    '''
    def __init__(self, cause):
        BE.PMException.__init__(self, "Cannot find survey: " + cause)

class NoCoord(BE.PMException):
    '''
    Peilmerk with no coordinate
    '''
    def __init__(self, cause):
        BE.PMException.__init__(self, "Cannot find coordinate: " + cause)

class NoHist(BE.PMException):
    '''
    Peilmerk with no history
    '''
    def __init__(self, cause):
        BE.PMException.__init__(self, "Cannot find any measurements: " + cause)

class _PeilmerkCache:
    '''
    Auxiliary (dummy)class to facilitate cache admin
    '''
    def __init__(self):
        pass

class PeilDataBase:
    '''
    Main peilmerk database class
    '''
    def __init__(self, name=""):
        self._mergeIssueHistory = None
        self._history = None
        self._dfSurveys = None
        self._dfHeights = None
        self._dfCoords = None
        self._cache = None
        self.clear()

        self._name = name
        self._history = ["Created database as '{:s}'".format(name)]

    def clear(self):
        '''
        Reinitialize peilmerk database
        '''
        self._dfHeights = pd.DataFrame()
        self._dfCoords = pd.DataFrame()
        self._dfSurveys = pd.DataFrame()
        self._mergeIssueHistory = []
        self._history = ["Cleared"]
        self._clearCache()

    def save(self, fileName):
        '''
        Save peilmerk database to file
        '''
        msg = "Saving file: '{:s}'".format(fileName)
        self._history.append(msg)
        ML.LogMessage(msg)

        version="1.0"
        with open(fileName,"wb") as F:
            pickle.dump(version, F)
            pickle.dump(self._dfSurveys, F)
            pickle.dump(self._dfHeights, F)
            pickle.dump(self._dfCoords, F)
            pickle.dump(self._mergeIssueHistory, F)
            pickle.dump(self._history, F)


    def load(self, fileName):
        '''
        Load peilmerk database from file
        '''
        msg = "Loading file: '{:s}'".format(fileName)
        self._history.append(msg)
        ML.LogMessage(msg)

        self.clear()
        with open(fileName, "rb") as F:
            version = pickle.load(F)
            assert(version=="1.0")
            self._dfSurveys = pickle.load(F)
            self._dfHeights = pickle.load(F)
            self._dfCoords = pickle.load(F)
            self._mergeIssueHistory = pickle.load(F)
            self._history = pickle.load(F)

    def to_csv(self, baseFileName):
        '''
        Export peilmerk database to a group of three CSV files, all 
        with names starting with 'baseFileName'.
        
        For convenience lat,lon coordinates are added to the RD coordinates.
        '''
        msg = "Saving CSV files: '{:s}'".format(baseFileName)
        self._history.append(msg)
        ML.LogMessage(msg)

        self._dfSurveys.to_csv(baseFileName+"_surveys.csv", index=True)
        self._dfHeights.to_csv(baseFileName+"_heights.csv", index=True)
        
        # Add lat/lon to export
        dfCoords = self._dfCoords.to_crs(epsg=CRS_LATLON)
        dfCoords['lon'] = dfCoords['geometry'].x
        dfCoords['lat'] = dfCoords['geometry'].y
        dfCoords = pd.DataFrame(dfCoords)
        dfCoords.drop('geometry', axis=1, inplace=True)

        dfCoords.to_csv(baseFileName+"_coords.csv", index=True)

    def __str__(self):
        '''
        String representation of peilmerk database
        '''
        return "{:s}\n{:s}\n{:s}\n{:s}\n".format("PeilmerkDatabase", str(self._dfSurveys),
                str(self._dfCoords), str(self._dfHeights))
            
    def _clearCache(self):
        '''
        Clear location cache
        (internal method)
        '''
        self._cache = _PeilmerkCache()
        
    def _fillCache(self, force = False):
        '''
        Fill location cache. If force is False, it is only filled if needed.
        (internal method)
        '''
        try:
            if (not force) and (self._cache.nc == len(self._dfCoords)): return
        except AttributeError:
            pass
        self._cache = _PeilmerkCache()
        
        print("    Filling cache...")
        
        # Coords related cache
        self._cache.coords =  dict()
        self._cache.dist = 5000
        self._cache.xycache = dict()
        self._cache.nc = len(self._dfCoords)

        # Loop over coords dataframe
        pms = self._dfCoords.index.values # PEILMERK_KEY
        xs = self._dfCoords[X_KEY].values
        ys = self._dfCoords[Y_KEY].values
        us = self._dfCoords[UNSTABLE_KEY].values
        for i in range(self._cache.nc):
            # Cache coords-->xy
            spm = pms[i]
            x = float(xs[i])
            y = float(ys[i])
            dd = dict()
            dd[X_KEY] = x
            dd[Y_KEY] = y
            dd[UNSTABLE_KEY] = us[i]
            dd[YEARS_KEY] = set() # To be filled later
            self._cache.coords[spm]=dd
            
            # Cache xy-->coords
            ix=int(x/self._cache.dist)
            iy=int(y/self._cache.dist)
            if ((ix,iy) not in self._cache.xycache):
                self._cache.xycache[(ix,iy)]=[]
            self._cache.xycache[(ix,iy)].append(spm)
    
        # Hist related cache
        self._cache.hist = dict()
        self._cache.srvys = dict()
        self._cache.nh = len(self._dfHeights)

        # Loop over hist.
        # Convert data to float (copy) for faster lookup later.  
        pms = self._dfHeights[PEILMERK_KEY].values
        ss = self._dfHeights[SURVEY_KEY].values
        hs = self._dfHeights[HGT_KEY].values
        ts = self._dfHeights[DATE_KEY].values
        t0 = T0
        yrs = dict()
        for i in range(self._cache.nh):
            spm = pms [i]
            survey = ss[i]
            t = float((ts[i] - t0).days)
            h = float(hs[i])
            y = int(ts[i].year)
            if not (spm in yrs):
                yrs[spm] = list()
            if not (spm in self._cache.hist):
                self._cache.hist[spm] = dict()
            if not (survey in self._cache.hist[spm]):
                self._cache.hist[spm][survey] = []
            if not (survey in self._cache.srvys):
                self._cache.srvys[survey] = set()
            yrs[spm].append(y)
            self._cache.hist[spm][survey].append((t, h))
            self._cache.srvys[survey].add(spm)
        
        ## Now we know sizes, convert to numpy arrays
        #for spm in self._cache.hist:
        #    for survey in self._cache.hist[spm]:
        #        tzPairs = np.array(self._cache.hist[spm][survey])
        #        self._cache.hist[spm][survey] = tzPairs
                
        # For each peilmerk, cache years with
        # measurement
        for spm, aCoord in self._cache.coords.items():
            try:
                ys = yrs[spm]
                aCoord[YEARS_KEY] = set(ys)
            except KeyError:
                pass

        print("        Done filling cache...")

    def _mergeSurveys(self, dfSurveys):
        '''
        Add surveys metadata 'dfSurveys' to survey meta-dataframe if needed
        '''
        self._clearCache()
        
        # No content yet? Just assign
        if (self._dfSurveys.empty):
            self._dfSurveys = dfSurveys
        else:
            # Check presence 1-by-1
            for idx, row in dfSurveys.iterrows():
                newSrvy = idx
                if (newSrvy in self._dfSurveys.index):
                    # Survey exists
                    ML.LogMessage("Survey '{:s}' already present".format(newSrvy))

                    # TODO: CHECK/MERGE DETAILS BETTER
                    # For now only append files.
                    # Get a reference to the list, take care to make the modifications
                    # in place
                    newFiles = row[SRCFILE_KEY]
                    df2 = self._dfSurveys.loc[newSrvy]
                    assert(isinstance(df2, pd.Series))
                    oldFiles = df2.loc[SRCFILE_KEY]
                    newFiles = set(newFiles)-set(oldFiles)
                    for f in newFiles:
                        oldFiles.append(f)
                else:
                    # Survey does not
                    ML.LogMessage("Survey '{:s}' added".format(newSrvy))
                    self._dfSurveys.loc[newSrvy] = row

    def _mergeData(self, dfCoords, dfHeights, limitDist=1e+38):
        '''
        Add survey data (contained in three dataframes( to existing database
        If 'limitDist' is specified, only data with a certain distance
        will be included.
        '''
        self._clearCache()

        if not (dfCoords is None):
            assert(isinstance(dfCoords, gpd.GeoDataFrame)) 
            #df_err = dfCoords[~(dfCoords[X_KEY]>0) | dfCoords[X_KEY].isnull()]
            #assert(len(df_err) == 0)
            #df_err = dfCoords[~dfCoords[X_KEY].apply(lambda x: isinstance(x,float))]
            #assert(len(df_err)==0)
            #df_err = dfCoords[~dfCoords[Y_KEY].apply(lambda x: isinstance(x,float))]
            #assert(len(df_err)==0)
            
            # Check for duplicates. If so, check the coordinates match
            dfDup = dfCoords[dfCoords.index.duplicated(keep='last')]
            if (len(dfDup) > 0):
                ML.LogMessage("{:d} peilmerken with duplicates found".format(len(dfDup)))
                for spm in dfDup.index:
                    dfSel = dfCoords.loc[spm]
                    dfSel = gpd.GeoDataFrame(dfSel, geometry=dfSel.geometry)
                    df1 = dfSel.iloc[-1]
                    dist = dfSel.distance(df1.geometry)
                    dist = max(dist)
                    if (dist > DIST_THRESH):
                        msg = ("Warning: duplicate(s) for {:s} found, up to "
                                "{:.2f} m apart.").format(spm, dist)
                        self._mergeIssueHistory.append(msg)
                        ML.LogMessage(msg, severity = 1)
            dfCoords = dfCoords[~dfCoords.index.duplicated(keep='last')]

            # Nothing there? Easy!
            # If something there merge. Check coordinates match
            if (self._dfCoords.empty):
                self._dfCoords = dfCoords
            else:
                # First make a list of common elements, then subtract
                commonItems =  set(self._dfCoords.index).intersection(dfCoords.index)
                if (len(commonItems)>0):
                    # Extract common elements to two dataframes
                    # They should be equally long, and have the same index
                    df1 = self._dfCoords.loc[commonItems]
                    df2 = dfCoords.loc[commonItems]
                    dist =  df1.distance(df2)
                    dist = dist[dist > DIST_THRESH]

                    # If any, warn
                    for spm in dist.index:
                        msg = (("'{:s}' in survey '{:s}' is located {:.1f} m "
                                "away from previous location in '{:s}'").format(spm, 
                                df2[SSOURCE_KEY][spm], dist[spm], df1[SSOURCE_KEY][spm]))
                        self._mergeIssueHistory.append(msg)
                        ML.LogMessage("Warning: " + msg, severity = 1)
                        dfCoords.loc[spm, COMMENT_KEY] += msg

                    # Merge properties, such as (un)stable
                    for spm in commonItems:
                        dfCoords.loc[spm, COMMENT_KEY] = (dfCoords.loc[spm, COMMENT_KEY] +
                                                            self._dfCoords.loc[spm, COMMENT_KEY])
                        dfCoords.loc[spm, UNSTABLE_KEY] = (dfCoords.loc[spm, UNSTABLE_KEY] or
                                                            self._dfCoords.loc[spm, UNSTABLE_KEY])
                    
                # Skip new points outside distance limitDist
                if (limitDist < 1e30):
                    # Geoseries-->GeoDataframe to contain limit of existing data
                    buf = self._dfCoords.buffer(limitDist)
                    
                    # Join all circles into one
                    buf = buf.unary_union
                    buf = buf.simplify(limitDist/10)
                    
                    # Turn into gdf for easier manipulation
                    buf = gpd.GeoSeries(buf)
                    buf = gpd.GeoDataFrame(geometry = buf)
                    buf.set_crs(self._dfCoords.crs, inplace=True)
                    assert(len(buf)==1)

                    # Use sjoin to select new points in buffer
                    lBefore = len(dfCoords)
                    geo_sel = dfCoords.sjoin(buf, how='left', rsuffix="right")
                    geo_sel.dropna(subset=['index_right'], inplace=True)
                    geo_sel.drop('index_right', axis=1, inplace=True)
                    ML.LogMessage(("Dropping {:d} points because further than {:.2f} "
                                    "from existing points").format(lBefore-len(geo_sel), limitDist))
                    dfCoords = geo_sel
                    
                    # Also apply to heights
                    if not (dfHeights is None):
                        remainingPMs = set(geo_sel.index.values)
                        lHgts = len(dfHeights)
                        dfHeights = dfHeights[dfHeights[PEILMERK_KEY].isin(remainingPMs)]
                        ML.LogMessage("        Also dropping {:d} height points".
                                                        format(lHgts-len(dfHeights)))

                # Merge, and keep the newer data
                self._dfCoords = self._dfCoords.append(dfCoords)
                self._dfCoords = self._dfCoords[~self._dfCoords.index.duplicated(keep='last')]
        
        # Finally, also merge heighers        
        if not (dfHeights is None):
            #df_err =  dfHeights[~dfHeights[DATE_KEY].apply(lambda x: 
            #           isinstance(x,(datetime.date, datetime.datetime)))]
            #assert(len(df_err)==0)
            #df_err = dfHeights[~dfHeights[HGT_KEY].apply(lambda x: isinstance(x,float))]
            #assert(len(df_err)==0)
        
            if (self._dfHeights.empty):
                self._dfHeights = dfHeights
            else:
                self._dfHeights = self._dfHeights.append(dfHeights)
                self._dfHeights.drop_duplicates(keep="last", 
                            subset=[SURVEY_KEY, PEILMERK_KEY, DATE_KEY], inplace=True)
            self._dfHeights.sort_values(by=[SURVEY_KEY, PEILMERK_KEY, DATE_KEY], inplace=True)

    def registerSurvey(self, surveyKey, subSurveys=None, srvFile="", 
                srvComment="", refPeilmerk=None):
        '''
        Register survey metadata. The survey can have subsurveys, which 
        will also be registered.
        '''
        if (subSurveys is None): subSurveys = list()

        self._history.append("Registered survey: '{:s}'".format(surveyKey))
        dfSurveys=pd.DataFrame({SURVEY_KEY: [surveyKey], 
                            SUBSURVEY_KEY: [subSurveys],
                            MASTERSURVEY_KEY: [""], 
                            SRCFILE_KEY: [[srvFile]],
                            COMMENT_KEY: [srvComment],
                            REFPEILMERK_KEY: [refPeilmerk]})

        for s in subSurveys:
            dfSurveys = dfSurveys.append({SURVEY_KEY: s, 
                            SUBSURVEY_KEY: [],
                            MASTERSURVEY_KEY: surveyKey, 
                            SRCFILE_KEY: [srvFile],
                            COMMENT_KEY: srvComment,
                            REFPEILMERK_KEY: refPeilmerk}, 
                            ignore_index=True)

        dfSurveys.set_index(SURVEY_KEY, inplace=True)

        self._mergeSurveys(dfSurveys)

    def addSurveyData(self, surveyKey, heights = None, coords = None, **kwargs):
        '''
        Add survey hist and coords (contained in two dataframes( to existing database
        If 'limitDist' is specified, only data with a certain distance
        will be included.
        Survey metadata needs to be tegistered separately.
        '''
        dfHeights = None
        if not (heights is None):
            # Make deep copy
            dfHeights = heights.copy(deep=True)
            
            # Default columns
            dfHeights[SURVEY_KEY]=surveyKey
            cols=dfHeights.columns.to_list()
            if not(PRJID_KEY in cols):
                dfHeights[PRJID_KEY]=""
            if not(SRCFILE_KEY in cols):
                dfHeights[SRCFILE_KEY]=""
            if not(COMMENT_KEY in cols):
                dfHeights[COMMENT_KEY]=""

            # Keep only the ones we understand
            dfHeights = dfHeights[[PEILMERK_KEY, DATE_KEY, HGT_KEY, PRJID_KEY, 
                        SURVEY_KEY, SRCFILE_KEY, COMMENT_KEY]]

        dfCoords = None
        if not (coords is None):
            # Make deep copy
            dfCoords = coords.copy(deep=True)

            # Default columns
            dfCoords[SSOURCE_KEY]=surveyKey
            cols=dfCoords.columns.to_list()
            if not (UNSTABLE_KEY in cols):
                dfCoords[UNSTABLE_KEY] = False
            if not (COMMENT_KEY in cols):
                dfCoords[COMMENT_KEY] = ""
            if not(SRCFILE_KEY in dfCoords):
                dfCoords[SRCFILE_KEY]=""

            # Keep only the ones we understand
            dfCoords = dfCoords[[PEILMERK_KEY, X_KEY, Y_KEY, SSOURCE_KEY, 
                        UNSTABLE_KEY, SRCFILE_KEY, COMMENT_KEY]]

            # Convert to geodataframe, if needed
            if (not isinstance(dfCoords, gpd.GeoDataFrame)):
                # Convert X,Y to shapely Points
                dfCoords['coords'] = list(zip(dfCoords[X_KEY], dfCoords[Y_KEY]))
                dfCoords = gpd.GeoDataFrame(dfCoords,
                                            crs  ='epsg:'+str(CRS_RD),
                                            geometry=dfCoords['coords'].apply(Point))
                dfCoords = dfCoords.drop('coords', axis=1)
            dfCoords.set_index(PEILMERK_KEY, inplace=True)

        self._mergeData(dfCoords, dfHeights, **kwargs)

    def addSurvey(self, surveyKey, srvFile="", srvComment="", refPeilmerk = None,
                  heights = None, coords = None, **kwargs):
        '''
        Add surveys metadata to database's survey meta-dataframe if needed, then 
        add data as well.
        '''
        self.registerSurvey(surveyKey, srvFile=srvFile, srvComment=srvComment, 
                    refPeilmerk=refPeilmerk)
        
        self.addSurveyData(surveyKey, heights = heights, coords = coords, **kwargs)

    def mergeDataBase(self, lpmdb, **kwargs):
        '''
        Merge database lpdmb into this one.
        If 'limitDist' is specified, only data with a certain distance
        will be included.
        '''
        self._history.append("Merged: "+lpmdb._name)
        for msg in lpmdb._history:
            self._history.append("        "+msg)

        if (len(lpmdb._mergeIssueHistory)>0):
            self._mergeIssueHistory.append("Merged '"+lpmdb._name+"':")
            for s in lpmdb._mergeIssueHistory:
                self._mergeIssueHistory.append("        "+s)
        else:
            self._mergeIssueHistory.append("Merged '"+lpmdb._name+"'")

        self._mergeSurveys(lpmdb._dfSurveys)
        
        self._mergeData(lpmdb._dfCoords, lpmdb._dfHeights, **kwargs)

        return 1

    def getDatabaseHistory(self):
        '''
        Database collates history for key modificiations, as a list of strings.
        his is returned.
        '''
        return self._history

    def checkComplete(self):
        '''
        Check database is complete.
        Returns
        - frame with peilmerken that have measurement history, but no coordinates.
        - frame with peilmerken that have coordinates but no measurement history.
        - list of issues that came up when merging in the data that make up the 
          database (list of strings)
        '''
        # Check how many peilmerken without coordinates
        # First do a join
        # Then strip the ones that have coordinates
        dfTotal = self._dfHeights.join(self._dfCoords, on=PEILMERK_KEY, rsuffix="_crd")
        dfNoCoord = dfTotal[dfTotal[X_KEY].isnull()]
        noCoord = list(dfNoCoord[PEILMERK_KEY].unique())

        # Same to find ones with no measurement history
        dfTotal = self._dfCoords.join(self._dfHeights.set_index(PEILMERK_KEY), 
                    on=PEILMERK_KEY, rsuffix="_dff")
        dfNoHist = dfTotal[dfTotal[HGT_KEY].isnull()]
        noHist = list(dfNoHist.index)

        return noCoord, noHist, self._mergeIssueHistory
        
    def getNumPeilmerken(self):
        ''' 
        Get number of peilmerken in database
        '''
        return len(self._dfCoords)
        
    def getPeilmerkenWithinBounds(self, bounds):
        ''' 
        Get peilmerken in database withun bounds
        supplied as (xmin, ymin, xmax, ymax), in RD.
        Returned as GeoDataFrame.
        '''
        # Bounds are in RD coordinates
        # Create geodataframe with only a geometry
        xys=Polygon([(bounds[0], bounds[1]), 
                    (bounds[0], bounds[3]), 
                    (bounds[2], bounds[3]),
                    (bounds[2], bounds[1])])
        gdfBound = gpd.GeoDataFrame([1], geometry=[xys], crs=CRS_RD)
        
        gdfOut = self._dfCoords.clip(gdfBound)

        return gdfOut.copy()
        
    def hasPeilmerk(self, spm, both=False):
        '''
        Return True if peilmerk spm has coords or history data in the database.
        if 'both' is True, both need to be there.
        '''
        if (both):
            isPresent = ((spm in self._dfCoords.index.values) and
                (spm in self._dfHeights[PEILMERK_KEY].values))
        else:
            isPresent = ((spm in self._dfCoords.index.values) or
                (spm in self._dfHeights[PEILMERK_KEY].values))
        return isPresent

    def renamePeilmerk(self, spm, new, comment):
        '''
        Rename peilmerk 'spm' to 'new'.
        
        A comment/reason needs to be given.
        
        Raises 'KeyError' if peilmerk is not present.
        '''
        if (not self.hasPeilmerk(spm)):
            raise KeyError
            
        # Cache is no longer valid
        self._clearCache()

        # Be careful: rename can overwrite
        # First check coordinates
        cSpms = self._dfCoords.index
        if (spm in cSpms):
            if (new in cSpms):
                # Overwrite. Check if the distance is significantly different
                # Cannot use loc, since we want to retain the geopandas features
                df_old = self._dfCoords.loc[new]
                df_new = self._dfCoords.loc[spm]

                # Convert to geoseries, calculate distance
                gs_new = gpd.GeoSeries(df_new.geometry)
                gs_old = gpd.GeoSeries(df_old.geometry)
                dist = gs_old.distance(gs_new, align=False)
                dist = dist.iat[0]

                # Report, then drop the old version of 'new'
                msg = ("Alias '{:s}'-->'{:s}' overwrites existing "
                        "peilmerk coords, at distance {:.2f}".format(spm, new, dist))
                self._dfCoords.drop(new, inplace=True)
                self._mergeIssueHistory.append(msg)
                ML.LogMessage(msg, severity=1 if (dist > DIST_THRESH) else 0)
            self._dfCoords.loc[spm, COMMENT_KEY] += "; Renamed from: " + spm + " (" + comment + ")"
            self._dfCoords.rename(index={spm:new}, inplace=True)

        # Then heights
        dSpms = self._dfHeights[PEILMERK_KEY].values
        if (spm in dSpms):
            if (new in dSpms):
                self._dfHeights = self._dfHeights[self._dfHeights[PEILMERK_KEY] != spm]
                msg = "Alias '{:s}'-->'{:s}' overwrites existing peilmerk heights".format(spm, new)
                self._mergeIssueHistory.append(msg)
                ML.LogMessage(msg, severity=1)
            self._dfHeights.loc[self._dfHeights[PEILMERK_KEY] == spm, PEILMERK_KEY] = new

        return 1

    def deletePeilmerk(self, spm, comment):
        '''
        Delete peilmerk 'spm'
        
        A comment/reason needs to be given.
        
        Raises 'KeyError' if peilmerk is not present.
        '''
        if (not self.hasPeilmerk(spm)):
            raise KeyError
            
        self._history.append("Deleted peilmerk: "+spm+" ("+comment+")")

        self._dfCoords.drop(spm, inplace=True)
        self._dfHeights = self._dfHeights[self._dfHeights[PEILMERK_KEY] != spm]
    
        self._clearCache()
    
        return 1

    def markPeilmerkUnstable(self, spm, comment, unstable=True):
        '''
        Mark peilmerk 'spm' as unstable (unless 'unstable' is passed as False)
        
        A comment/reason needs to be given.
        
        Raises 'KeyError' if peilmerk is not present.
        '''
        #if (not self.hasPeilmerk(spm)):
        #    raise KeyError

        # Loc method adds empty peilmerk if not defined. Force a check
        old = self._dfCoords.loc[spm]
        self._dfCoords.loc[spm, UNSTABLE_KEY] = unstable
        self._dfCoords.loc[spm, COMMENT_KEY] += "; Unstable=" + str(unstable) + " (" + comment + ")"
    
        self._clearCache()

        return 1
        
    def isUnstable(self, spm):
        '''
        Check whether peilmerk 'spm' has been marked as unstable.
        '''
        df1=self._dfCoords.loc[spm]
        return df1[UNSTABLE_KEY]
            
    def getNumSurveys(self):
        ''' 
        Get number of surveys in database
        '''
        return len(self._dfSurveys)
        
    def getSurveyYears(self, srvy):
        '''
        Get list of (calendar) years in which a survey has measurements
        '''
        df = self._dfHeights[self._dfHeights[SURVEY_KEY]==srvy].copy()
        
        _YEAR_KEY="year"
        df[_YEAR_KEY] = df[DATE_KEY].apply(lambda x: x.year)
        
        yrs = list(df[_YEAR_KEY].unique())
        yrs.sort()
        
        return yrs

    def getSurveyDiffs(self, survey, year1, year2, refShifts=None):
        '''
        Return dataframe with points (peilmerk, x, y) from a given survey,
        and differences between two years (in column DIFF_KEY).
        
        (peilmerk, x, y) in columns (PEILMERK_EKY, X_KEY, Y_KEY)
        
        The unstability is marked in column UNSTABLE_KEY
        '''
        # Check survey is there
        if not (survey in self._dfSurveys.index.values):
            raise SurveyNotFound(survey)
        
        # Subsurveys not yet implemented
        subSurveys = self._dfSurveys.loc[survey]
        subSurveys = subSurveys[SUBSURVEY_KEY]
        if (len(subSurveys)>0):
            ML.LogMessage(
                "Warning: {:s} has subsurveys. Not implemented in getSurveyHeights".
                        format(survey))
        
        # Get points for survey
        df = self._dfHeights[self._dfHeights[SURVEY_KEY] == survey].copy()

        # Calc year as new column
        _YEAR_KEY="year"
        df[_YEAR_KEY] = df[DATE_KEY].apply(lambda x: x.year)
        
        # Reference shifts can be provided as dict[srvy][year] or dataframe, with index year, 
        # and columns DIFF_KEY and SURVEY_KEY.
        # If dict, convert to dataframe.
        if (refShifts is not None):
            if isinstance(refShifts, dict):
                # Convert dict
                dfRefShifts = pd.DataFrame(refShifts)
                dfRefShifts = dfRefShifts.melt(ignore_index=False).reset_index()
                dfRefShifts.rename(columns={'index':_YEAR_KEY, 'variable':SURVEY_KEY, 'value':DIFF_KEY}, inplace=True)
                dfRefShifts.set_index(_YEAR_KEY, inplace=True)
            else:
                assert(isinstance(refShifts, pd.DataFrame))
                dfRefShifts = refShifts.set_index(_YEAR_KEY)
            
            # Extract data for current survey
            dfRefShifts = dfRefShifts[dfRefShifts[SURVEY_KEY]==survey]

            # Apply shifts to extracted data
            df = df.join(dfRefShifts, on=_YEAR_KEY, rsuffix="_d", lsuffix="")
            df[DIFF_KEY].fillna(0, inplace=True)
            df[HGT_KEY]=df[HGT_KEY] + df[DIFF_KEY]
            df.drop([DIFF_KEY, SURVEY_KEY+"_d"], axis=1, inplace=True)

        # Get dataframes for the two years
        df1 = df[df[_YEAR_KEY] == year1]
        df2 = df[df[_YEAR_KEY] == year2]
        
        # Calculate difference
        df3 = df1.join(df2.set_index(PEILMERK_KEY), on=PEILMERK_KEY, rsuffix="_2")
        df3[DIFF_KEY] = df3[HGT_KEY+"_2"] - df3[HGT_KEY]
        df3 = df3[~df3[DIFF_KEY].isnull()]
                
        # Wrap up output
        df.drop(_YEAR_KEY, axis=1, inplace=True)
        df = pd.merge(df, df3, on = PEILMERK_KEY, how = "inner")        
        df = pd.merge(df, self._dfCoords, on = PEILMERK_KEY, how = "inner")
        df = df[[PEILMERK_KEY, X_KEY, Y_KEY, UNSTABLE_KEY, DIFF_KEY]]

        return df
        
    def getSurveyPointsFrame(self, survey, year = None):
        '''
        Return dataframe with points (peilmerk, x, y) from a given survey,
        measured in a geven year
        '''
        df = self._dfHeights[self._dfHeights[SURVEY_KEY] == survey].copy()

        # Calc year as new column
        if not (year is None):
            _YEAR_KEY="year"
            df[_YEAR_KEY] = df[DATE_KEY].apply(lambda x: x.year)
            df = df[df[_YEAR_KEY] == year]
            df.drop(_YEAR_KEY, axis=1, inplace=True)

        df = pd.merge(df, self._dfCoords, on = PEILMERK_KEY, how = "inner")

        df = df[[PEILMERK_KEY, X_KEY, Y_KEY, UNSTABLE_KEY]]

        return df

    def getHeightsForPMAsList(self, spm, alignment=NO_ALIGNMENT, refDate=None, 
                                afterDate=None, refShifts = None):
        '''
        Get heights for peilmerk 'spm' as a dict-of-lists. Dict is keyed on
        survey.
        Alignment behavior is controlled via 'alignment' switch:
        NO_ALIGNMENT - Raw NAP data is returned
        ADD_MEDIAN - A median NAP height curve is added
        ADD_MERGE - A curve is added that is the merge of all surveys
        ALIGN_MEDIAN - Heights are shifted so median is zero at refDate (same shift
                    is appied to all surveys)
        ALIGN_ALL - Heights are shifted height is zero at refDate (all surveys
                    and median shifted separately, so they line up with the median)
        ALIGN_ALL_SEGMENT - Heights are shifted so median is zero at refDate if 
                    there is contiguous (overlapping) data to refdate
                    
        Times are returned as days from T0 (1-1-1970)
        
        refData is to be provided as days from T0 (1-1-1970)
        ''' 
        assert(isinstance(spm, str))
        if (refDate is None): refDate = (DEFAULT_ALIGN_DATE-T0).days

        self._fillCache(False)

        try:    
            tzData = self._cache.hist[spm]
        except KeyError:
            raise NoHist(spm) from None

        if (alignment == ADD_MEDIAN):
            tzOut, _ = CA.AnalyzeTZSeries(tzData, 
                            afterDate=afterDate)
            tzOut.update(tzData)
        elif (alignment == ADD_MERGE):
            tzOut= CA.MergeTZSeries(tzData)
            tzOut.update(tzData)
        elif (alignment == ALIGN_MEDIAN):
            tzOut = CA.AlignMedian(tzData, refDate, 
                            afterDate=afterDate)
        elif (alignment == ALIGN_ALL):
            tzOut = CA.AlignAllMedian(tzData, refDate, 
                            afterDate=afterDate)
        elif (alignment == ALIGN_ALL_SEGMENT):
            tzOut = CA.AlignAllSegmentMedian(tzData, refDate, 
                            afterDate=afterDate)
        else:
            tzOut = tzData

        # Return a copy, so others can manipulate it without damaging the database
        tzOut = copy.deepcopy(tzOut)
        
        # Reference shifts can be provided as dict[srvy][year] or dataframe, with index year, 
        # and columns DIFF_KEY and SURVEY_KEY.
        # If dict, convert to dataframe.
        if (refShifts is not None):
            if isinstance(refShifts, dict):
                pass
            else:
                # Convert to dict
                assert(isinstance(refShifts, pd.DataFrame))
                dfRefShifts = refShifts.set_index(_YEAR_KEY)
                assert(0) # TODO
            
            for srvy, tzPairs in tzOut.items():
                try:
                    refShiftsL = refShifts[srvy]
                except KeyError:
                    continue
                
                for i, tz in enumerate(tzPairs):
                    y =  (T0+datetime.timedelta(float(tz[0]))).year
                    try:
                        dz = refShiftsL[y]
                    except KeyError:
                        continue
                    tzPairs[i] = (tz[0], tz[1]+dz)
            
        return tzOut

    def getHeightsForPMAsFrame(self, spm, alignment=NO_ALIGNMENT, refDate=None, 
                                afterDate=None, **kwargs):
        '''
        Get heights for peilmerk 'spm' as a dataframe.
        Alignment behavior is controlled via 'alignment' switch:
        NO_ALIGNMENT - Raw NAP data is returned
        ADD_MEDIAN - A median NAP height curve is added
        ADD_MERGE - A curve is added that is the merge of all surveys' NAP heights
        ALIGN_MEDIAN - Heights are shifted so median is zero at refDate (same shift
                    is appied to all surveys)
        ALIGN_ALL - Heights are shifted height is zero at refDate (all surveys
                    and median shifted separately, so they line up with the median)
        ALIGN_ALL_SEGMENT - Heights are shifted so median is zero at refDate if 
                    there is contiguous (overlapping) data to refdate
                            
        Times are returned as dates (datetime)
        
        refData is to be provided as date
        
        NAP heights are HGT_KEY column, relative heights as DIFF_KEY
        '''
        assert(isinstance(spm, str))

        # In frame we have datetime, in dictlist we work in days since T0
        if not (refDate is None): refDate = (refDate-T0).days
        if not (afterDate is None): afterDate = (afterDate-T0).days
        tzOut = self.getHeightsForPMAsList(spm, alignment=alignment, refDate=refDate, 
                                    afterDate=afterDate, **kwargs)
        
        zKey = DIFF_KEY if (alignment.startswith(ALIGN)) else HGT_KEY
        
        dfOut = WrapTZListToHeightFrame1(tzOut, skey1=SURVEY_KEY, zKey=zKey) # skey2=PEILMERK_KEY, 
        
        return dfOut

    def getPeilmerkXY(self, spm):
        '''
        Get X,Y (in RD) for peilmerk 'spm'
        '''
        df1=self._dfCoords.loc[spm]
        return (df1[X_KEY], df1[Y_KEY])

    def getCoordSource(self, spm):
        '''
        Get source survey for peilmerk 'spm's X,Y
        '''
        df1 = self._dfCoords.loc[spm]
        src = df1[SSOURCE_KEY]
        assert(isinstance(src,str))
        return src
        
    def getHeightSource(self, spm):
        '''
        Get source survey for peilmerk heights data.
        A list is returned.
        '''
        df1=self._dfHeights[self._dfHeights[PEILMERK_KEY]==spm]
        srvys = list(df1[SURVEY_KEY].unique()) # TODO
        return srvys
        
    def getPeilmerkList(self, srvy = None):
        '''
        Get list of all peilmerken (in survey 'srvy', if provided)
        '''
        if not (srvy is None):
            df = self._dfHeights[self._dfHeights[SURVEY_KEY] == srvy]
            return list(df[PEILMERK_KEY].unique()) # unique should not be needed
        else:
            df =  self._dfCoords
            return list(df.index.unique()) # unique should not be needed

    def getPeilmerkCoords(self, srvy = None):
        '''
        Get dataframe of all peilmerken with coordinates (in survey 'srvy', if provided)
        
        Peilmerk name is index of the frame, X, Y are geometry (in RD) and columns X_KEY, Y_KEY.
        Unstability is column UNSTABLE_KEY.
        '''
        if not (srvy is None):
            df = self._dfCoords[self._dfCoords[SURVEY_KEY] == srvy]
        else:
            df =  self._dfCoords
        return df.copy()

    def getSurveyList(self):
        '''
        Get list of all surveys
        '''
        srvys = self._dfSurveys.index.values
        return list(srvys)

    def getHeightSurveyList(self, spm):
        '''
        Get list of surveys that have height measurements for 'spm'
        '''
        df1=self._dfHeights[self._dfHeights[PEILMERK_KEY]==spm]
        src = list(df1[SURVEY_KEY]) # TODO
        return src[0]

    def getClosestPeilmerkenAsList(self, xy, maxDistance=2000, minYears=2, maxNumPMs=None,
                                returnData=True, refDate=None, afterDate = None, 
                                includeUnstable = False): 
        '''
        Get list of peilmerknames and matching list of distances that are 
        within maxdist, and have measurements in at least minPoints years. 
        The list is sorted on dist, and retruned as a dict, peilmerken in 
        PEILMERK_KEY, distances in DIST_KEY.
        '''
        if (afterDate is None):
            afterDate = DEFAULT_ALIGN_DATE

        self._fillCache(False)
        
        # Look only for points in adjacent grid tiles
        dists=[]
        ix=int(xy[0]/self._cache.dist)
        iy=int(xy[1]/self._cache.dist)
        nxy=int(maxDistance/self._cache.dist)+1
        for jx in range(ix-nxy,ix+nxy+1):
            for jy in range(iy-nxy,iy+nxy+1):
                if ((jx,jy) in self._cache.xycache):
                    for spm in self._cache.xycache[(jx,jy)]:
                        dd = self._cache.coords[spm]
                        xSpm = dd[X_KEY]
                        ySpm = dd[Y_KEY]
                        dist = np.sqrt((xSpm-xy[0])**2 + (ySpm-xy[1])**2)
                        if (dist <= maxDistance) and (includeUnstable or not(dd[UNSTABLE_KEY])): 
                            yrSpm = dd[YEARS_KEY]
                            yrT = afterDate.year
                            n = sum(map(lambda tt : tt>=yrT, yrSpm))
                            if (n >= minYears): dists.append((dist, spm))
        
        # Sort on distance
        dists.sort()
        
        # Chop if requested
        if not (maxNumPMs is None):
            dists = dists[:maxNumPMs]
        
        # And return in proper shape
        res = list(zip(*dists))
        if (len(res)>0):
            return {PEILMERK_KEY: res[1], DISTANCE_KEY: res[0]}
        else:
            return {PEILMERK_KEY: [], DISTANCE_KEY: []}
        
    def getClosestPeilmerkenAsFrame(self, xy, **kwargs): 
        '''
        Get list of peilmerknames and matching list of distances that are 
        within maxdist, and have measurements in at least minPoints years. 
        The list is sorted on dist, and returned as a dataframe,
        peilmerken in column PEILMERK_KEY, distances in DISY_KEY.
        '''
        tzdict = self.getClosestPeilmerkenAsList(xy, **kwargs)
        
        df = pd.DataFrame(tzdict)
        
        return df
        
    def getHeightsForPMListAsList(self, pml, refDate=None, afterDate=None, 
                                    alignment=None, refShifts=None):
        '''
        Get list of heights for peilmerken in list 'pml'.
        
        Output is a dict, keyed on peilmerk name. Each element is again
        a dict, keyed on survey. Elements of that are a list of (t,z) tuples
        representing the heights.
        For each peilmerk a MEDIAN curve is provided (survey name set to MEDIAN).
        For the total an overall MEDIAN curve is provided (i.e. peilmerk name 
        and survey name are MEDIAN).
        
        Times are in days since T0 (1-1-1970).
        '''
        if (afterDate is None):
            afterDate = DEFAULT_ALIGN_DATE

        self._fillCache(False)
        
        tzData = {spm: self._cache.hist[spm] for spm in pml}
        
        if not (afterDate is None):
            afterDate = (afterDate - T0).days
        else:
            afterDate = 0 # T0
        if not (refDate is None):
            refDate = (refDate - T0).days
        else:
            refDate = 0 # T0
            
        #TODO: DO WE WANT ALIGNMENT VARIATIONS?
        
        # Align each peilmerk to its own median, and align those
        tzAligned = CA.AlignAllMedian2Level(tzData, refDate, afterDate=afterDate)
        
        # Reference shifts can be provided as dict[srvy][year] or dataframe, with index year, 
        # and columns DIFF_KEY and SURVEY_KEY.
        # If dict, convert to dataframe.
        if (refShifts is not None):
            if isinstance(refShifts, dict):
                pass
            else:
                # Convert to dict
                assert(isinstance(refShifts, pd.DataFrame))
                dfRefShifts = refShifts.set_index(_YEAR_KEY)
                assert(0) # TODO
            
            # Map the dz's over the data
            for spm, tzDict in tzAligned.items():
                for srvy, tzPairs in tzDict.items():
                    try:
                        refShiftsL = refShifts[srvy]
                    except KeyError:
                        continue
                    
                    for i, tz in enumerate(tzPairs):
                        y =  (T0+datetime.timedelta(float(tz[0]))).year
                        try:
                            dz = refShiftsL[y]
                        except KeyError:
                            continue
                        tzPairs[i] = (tz[0], tz[1]+dz)

        return tzAligned 
    
    def getHeightsForPMFrameAsFrame(self, pmDf, **kwargs):
        '''
        Get frame of heights for peilmerken in frame 'pmDf' (assumed keyed on PEILMERK_KEY).
        
        Output is a frame, with PEILMERK_KEY, SURVEY_KEY, DATE_KEY, DIFF_KEY.
        For each peilmerk a MEDIAN curve is provided (survey name set to MEDIAN).
        For the total an overall MEDIAN curve is provided (i.e. peilmerk name 
        and survey name are MEDIAN).
        Output is aligned at refDate
        '''
        if (isinstance(pmDf, str)):
            pml = [pmDf]
        elif (isinstance(pmDf, pd.DataFrame)):  
            pml = list(pmDf[PEILMERK_KEY].values)
        else:
            pml = pmDf
        tzAligned = self.getHeightsForPMListAsList(pml, **kwargs)
        
        return WrapTZListToHeightFrame2(tzAligned, skey1=SURVEY_KEY, skey2=PEILMERK_KEY, 
                                        zKey=DIFF_KEY)

    def collectAlignedDataAsList(self, refDated=0, pml=None, includeUnstable=False):
        '''
        Method to collect aligned data for a list (pml) of (or all,
        if pml is None) peilmerken.

        refDated: reference time, # days since T0 (1-jan-1970)

        Returned as dict (keyed on peilmerk name spm), each element:
            COORD_KEY:
                X_KEY:          x (RD)
                Y_KEY:          y (RD)
            NEIGHBOUR_KEY:
                list of neighbouring peilmerken used in the analysis
            DIFF_KEY: height differences, zero at refDated
                ALIGN_ALL:      TZ pairs of aligned data from the area
                MEDIAN:         TZ pairs of aligned amalgamated measured data
                <survey>:       TZ pairs of aligned measured data

        Can be time consuming, a progress bar is shown.
        '''
        print("    -----Collecting Aligned Data-------------")
        
        # Default peilmerklist & get coordinates
        if (pml is None): 
            pml = self.getPeilmerkList()
            dfC = self._dfCoords
        else:
            dfC = self._dfCoords[self._dfCoords.index.isin(pml)]

        # Loop over all peilmerken, with progress monitoring
        nc = len(dfC)
        pmcol = dfC.index.values
        xcol = dfC[X_KEY].values
        ycol = dfC[Y_KEY].values
        nUnst = []
        nData = []
        collectedData={}
        for i in pb.progressbar(range(nc), redirect_stdout=True):
            # Skip peilmerken that are unstable
            spm = pmcol[i]
            if ((not includeUnstable) and self.isUnstable(spm)):
                nUnst.append(spm)
                continue
            x = xcol[i]
            y = ycol[i]
                
            # Get peilmerken in the vicinity
            # Result is dict (keyed on peilmerk) with dict (keyed on survey) containing
            # tzpairs.
            ngb = self.getClosestPeilmerkenAsList((x,y), 
                            includeUnstable=includeUnstable)
            pmh = self.getHeightsForPMListAsList(ngb[PEILMERK_KEY])
            
            # Medians have dummy peilmerk/survey key.
            tzAreaMed = pmh[MEDIAN][MEDIAN]

            # Check there is enough data
            if not (spm in pmh):
                nData.append(spm)
            elif(len(tzAreaMed)>2 and len(pmh)>1):
                #print(pmh)
                d=pmh[spm]
                d[ALIGN_ALL] = tzAreaMed
                crd = {X_KEY:x, Y_KEY:y}
                collectedData[spm] = {COORD_KEY: crd, DIFF_KEY: d, NEIGHBOUR_KEY: ngb[PEILMERK_KEY]}         
            else:
                nData.append(spm)
            
        print("    Included:", len(collectedData))
        print("    Unstable:", len(nUnst))
        print("    Too little data:", len(nData))
        #df = pd.Series( nData1 )
        #df.to_csv("aap.csv")
        print("    ------------------")
        print()
        
        return collectedData

    def collectAlignedDataAsFrame(self, refDate=None, pml=None, includeUnstable=False,
                                    addLatLon=True):
        '''
        Method to collect aligned data for a list (pml) of (or all,
        if pml is None) peilmerken.

        Returned as a dict of pandas dataframes.
            COORD_KEY: coordinates (RD and latlon)
            NEIGHBOUR_KEY: for each peilmer, the neighbours involved in the analysis
            DIFF_KEY:   the differences, zero @ refDate

        Can be time consuming, a progress bar is shown
        '''
        if (refDate is None): refDated = 0
        else: refDated = (refDate-T0).days
        collectedData = self.collectAlignedDataAsList(refDated=refDated, pml=pml,
                    includeUnstable=includeUnstable)
            
        print("    Converting to dataframe")

        # First the diffs
        tzDict1 = dict()
        for lspm, cData in collectedData.items():
            d = cData[DIFF_KEY]
            for srvy, tzPairs in d.items():
                ll = len(tzPairs)
                tzDict2 = dict()
                tzDict2[DIFF_KEY]=list()
                tzDict2[DATE_KEY]=list()
                for i in range(ll):
                    tz = tzPairs[i]
                    date = T0+datetime.timedelta(float(tz[0]))
                    tzDict2[DATE_KEY].append(date)
                    tzDict2[DIFF_KEY].append(tz[1])
                tzDict2[SURVEY_KEY] = [srvy]*len(tzDict2[DIFF_KEY])
                tzDict2[PEILMERK_KEY] = [lspm]*len(tzDict2[DIFF_KEY])
                if (len(tzDict1)==0):
                    tzDict1 = tzDict2
                else:
                    for lst, tzP in tzDict2.items():
                        tzDict1[lst].extend(tzP)
        df = pd.DataFrame(tzDict1)
        df = df[[PEILMERK_KEY, SURVEY_KEY, DATE_KEY, DIFF_KEY]]

        # Then the coordinates
        cDict={PEILMERK_KEY:[], X_KEY:[], Y_KEY:[]}
        for lspm, cData in collectedData.items():
            d = cData[COORD_KEY]
            cDict[PEILMERK_KEY].append(lspm)
            cDict[X_KEY].append(d[X_KEY])
            cDict[Y_KEY].append(d[Y_KEY])
        dfC = pd.DataFrame(cDict)

        # Add latlon
        if (addLatLon):
            geometry = [Point(xy) for xy in zip(cDict[X_KEY], cDict[Y_KEY])]
            gdf = gpd.GeoDataFrame(crs=CRS_RD, geometry=geometry)
            gdf = gdf.to_crs(epsg=CRS_LATLON)
            dfC['lon'] = gdf['geometry'].x
            dfC['lat'] = gdf['geometry'].y

        # Finally collect the neighbours
        nDict={PEILMERK_KEY:[], NEIGHBOUR_KEY: []}
        for lspm, cData in collectedData.items():
            d = cData[NEIGHBOUR_KEY]
            nDict[PEILMERK_KEY].extend([lspm]*len(d))
            nDict[NEIGHBOUR_KEY].extend(d)
        dfN = pd.DataFrame(nDict)     
        
        print("    Done")

        return {DIFF_KEY: df, COORD_KEY: dfC, NEIGHBOUR_KEY: dfN}
