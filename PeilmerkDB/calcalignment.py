'''
Auxiliary functions to align peilmerk (leveling) measurements
'''
import statistics
import time
import copy
import datetime
import pandas as pd
import numpy as np

from . import pmexception as BE
from . import interpolatefunctions as IF
from . import messagelogger as ML

class NoOverlapException(BE.PMException):
    '''
    Exception to mark lack of overlap that makes alignment impossible
    '''
    pass

# Performance timing
times=dict()

def RESETTIME():
    global times
    for indx in range(20):
        times[indx]=0

RESETTIME()

def GETTIME():
    global times
    return times

# Common keys used in this module
MERGE="merge"
MEDIAN="median"
SEGMENT="segment"
MEDIAN_SEGMENT=MEDIAN+"_"+SEGMENT+"_"
DZ="dz"

# Default starting point (also for conversion of datetime<-->float)
T0 = datetime.date(1970,1,1)

###############################################
#
# TODO: REWRITE FOR DATAFRAMES
#
###############################################

def AnalyzeTZSeries(tzData, afterDate=0, timeTol=30):
    '''
    Calculates median data for dict with tzPair lists, and shifts needed
    to align the data to the median.
    A tzPair list is a list containing (t,z) tuples, both doubles.
    t is days since T0 (1-jan-1970).

    Returns  
    tzData2 = {MEDIAN: mtzlist, ...} (one extra for each segment)
    tzData3 = {SEGMENT: segments, DZ: dz}
    '''
    # Anything to do?
    if (len(tzData) == 0):
        tzData2 = {MEDIAN: []}
        idx=0
        tzData2[MEDIAN_SEGMENT+str(idx)] = []
        tzData3 = {SEGMENT: [], DZ: []}
        return tzData2, tzData3

    # Was a focusdate supplied? Set a dummy date to facilitate comparison
    if (afterDate is None): afterDate=1e-10

    # Performance timing
    start=time.time() # TIME

    # Get a list of all time points
    ts=set()
    for srvy in tzData:
        for tz in tzData[srvy]:
            ts.add(tz[0])
    ts=list(ts)
    ts.sort()

    # Performance timing
    global times
    times[1]+=time.time()-start
    start=time.time() # TIME

    # Deal with time-duplicates
    tzlistdict=dict()
    for srvy, tzPairs in tzData.items():
        subdict=list()
        tzlistdict[srvy]=subdict
        foundDupl=False
        tprev=None
        zprev=list()
        for tz in tzPairs:
            if(tz[0]==tprev):
                foundDupl=True
                zprev.append(tz[1])
                #print("****duplicate time!!", tz[0])
            else:
                if (foundDupl):
                    # Different time. Deal with preceding duplicate if any
                    z=statistics.median(zprev)
                    subdict[-1]=(tprev,z)
                subdict.append(tz)
                tprev=tz[0]
                zprev=[tz[1]]
                foundDupl=False

        # If the duplicates were the last few points, deal with that
        if (foundDupl):
            z=statistics.median(zprev)
            subdict[-1]=(tprev,z)

    # Performance timing
    times[2]+=time.time()-start
    start=time.time() # TIME

    # Start off the counters & admin
    idx=dict()
    for srvy in tzlistdict:
        idx[srvy]=0
    jdx=0
    t1=ts[jdx]
    z1=0
    otzlistlist=list()
    otzlistlist.append(list())
    otzlistlist[-1].append((t1,z1))

    # Loop as long as points left, calculate & integrate median
    # subsidence speed along the way
    # Split data into segments if they is no contiguous coverage
    while (True):
        jdx+=1
        if (jdx>=len(ts)): break
        t0=t1
        z0=z1
        t1=ts[jdx]
        #print("Processing interval", t0, "to", t1)

        # Move all indexes that point to a t less than the current time
        for srvy, subdict in tzlistdict.items():
            while(idx[srvy]<len(subdict)) and (subdict[idx[srvy]][0]<t1):
                idx[srvy]+=1
            # IF WE ARE AT THE END, HAVE SOME TOLERANCE!!
            # HACK
            if(idx[srvy]==len(subdict)) and (subdict[idx[srvy]-1][0]>t1-timeTol):
                idx[srvy]-=1

        # Calculate derivatives
        dzdt=[]
        for srvy, subdict in tzlistdict.items():
            if(idx[srvy]>0 and idx[srvy]<len(subdict)):
                ifrom=idx[srvy]-1
                ito=idx[srvy]
                lt0=subdict[ifrom][0]
                lt1=subdict[ito][0]
                tmid=(t0+t1)/2

                if(lt0-timeTol<tmid<=lt1+timeTol):
                    lz0=subdict[ifrom][1]
                    lz1=subdict[ito][1]
                    dzdt.append((lz1-lz0)/(lt1-lt0))

        # integrate median subsidence speed, if any found
        # otherwise start afresh. The relative position of the
        # new segment remains to be determined
        if(len(dzdt)>0):
            dzdtm=statistics.median(dzdt)
            z1=z0+dzdtm*(t1-t0)
        else:
            #print("*** no derivative between",t0,t1)
            dzdtm=None
            z1=0
            otzlistlist.append(list())

        otzlistlist[-1].append((t1,z1))

    # Performance timing
    times[3]+=time.time()-start
    start=time.time() # TIME

    # Every input series must be contained in a single segment.
    # Todo: this is slow
    segments=dict()
    for srvy, subdict in tzlistdict.items():
        t0=subdict[0][0]
        for j, sublist in enumerate(otzlistlist):
            tstart=sublist[0][0]
            tend=sublist[-1][0]
            if (tstart <= t0 <= tend):
                segments[srvy]=j
                break

    # Performance timing
    times[4]+=time.time()-start
    start=time.time() # TIME

    # Finally, align the segments vertically.
    # Every input series must be contained in a single segment.
    dz=dict()
    dt=dict()
    for srvy, subdict in tzlistdict.items():
        iseg=segments[srvy]

        # Series of length 1 need to be dealt with differently
        if(len(subdict)==1):
            lt0=subdict[0][0]
            for tz in otzlistlist[iseg]:
                if (tz[0]==lt0):
                    dz[srvy]=tz[1]-subdict[0][1]
                    dt[srvy]=0
        else:
            # Start off the counters & admin
            idx=0
            dz[srvy]=0
            dt[srvy]=0
            jdx=0
            t1=otzlistlist[iseg][jdx][0]
            z1=otzlistlist[iseg][jdx][1]

            # Loop as long as points left, calculate dz along the way
            while (True):
                jdx+=1
                if (jdx>=len(otzlistlist[iseg])): break
                t0=t1
                z0=z1
                t1=otzlistlist[iseg][jdx][0]
                z1=otzlistlist[iseg][jdx][1]

                # Move index to the first t greater than the current time
                # Since all times in the series must occur in the median, we
                # are sure to step one step at a time
                while(idx<len(subdict)) and (subdict[idx][0]<t1):
                    idx+=1
                ifrom=idx-1

                # Integrate by interval. Note we know that all time values occur
                # in the median series.
                if(0 < idx < len(subdict)):
                    ito=idx
                    lt0=subdict[ifrom][0]
                    lt1=subdict[ito][0]

                    if(t0>=lt0 and t1<=lt1):
                        lz0=subdict[ifrom][1]
                        lz1=subdict[ito][1]

                        z0_int=(t0-lt0)/(lt1-lt0)*(lz1-lz0)+lz0
                        z1_int=(t1-lt0)/(lt1-lt0)*(lz1-lz0)+lz0
                        w=1
                        if (t0<afterDate):
                            w=0.01
                        dz[srvy]+=((z0-z0_int)+(z1-z1_int))/2*(t1-t0)*w
                        dt[srvy]+=(t1-t0)*w

            if (dt[srvy]>0):
                dz[srvy]/=dt[srvy]

    # Performance timing
    times[5]+=time.time()-start
    start=time.time() # TIME

    # Calculate average shift per segment
    cnt=dict()
    dz_avg=dict()
    dz_wgt=dict()
    for iseg in range(len(otzlistlist)):
        dz_avg[iseg]=0
        dz_wgt[iseg]=0
        cnt[iseg]=0
    for srvy, ldz in dz.items():
        iseg=segments[srvy]
        w=max(0.001,dt[srvy]) # TODO (default tiny weight)
        dz_avg[iseg]+=ldz*w
        dz_wgt[iseg]+=w
        cnt[iseg]+=1

    # Shift segments
    for iseg, sublist in enumerate(otzlistlist):
        if (cnt[iseg]>0):
            dz_avg[iseg]/=dz_wgt[iseg]

            # Shift tuple in sublist
            ll = len(sublist)
            for indx in range(ll):
                tz=sublist[indx]
                sublist[indx]=(tz[0],tz[1]-dz_avg[iseg])
        else:
            print("****Empty segment? Should this happen?")
            print("****Check data is sorted...")
            assert(0)

    # Map shifts to survey (each survey is in one segment)
    for srvy in dz:
        iseg=segments[srvy]
        dz[srvy]-=dz_avg[iseg]

    times[6]+=time.time()-start
    start=time.time() # TIME

    # Prepare merged list as well as the per-segment list
    mtzlist=[]
    for seg_median in otzlistlist:
        mtzlist += seg_median

    # Performance timing
    times[7]+=time.time()-start
    start=time.time() # TIME

    # Collate output. Label segments uniquely (TODO: can't we use indexes?)
    tzData2 = {MEDIAN: mtzlist}
    idx=0
    for seg_median in otzlistlist:
        tzData2[MEDIAN_SEGMENT+str(idx)] = seg_median
        idx += 1
    segments = {s: MEDIAN_SEGMENT+str(seg) for s, seg in segments.items()}
    tzData3 = {SEGMENT: segments, DZ: dz}

    return tzData2, tzData3

def MergeTZSeries(tzData, timeTol=30):  # TODO: Odd results for large timeTol
    '''
    Merge data for dict with tzPair lists, in one tzPair list.
    No alignment takes place.

    A tzPair list is a list containing (t,z) tuples, both doubles.
    t is days since T0 (1-jan-1970).

    Returns merged tzData (dict with a single element, key MERGE)
    '''
    # Merge all
    tzPairs1 = list()
    for s in tzData:
        tzPairs1.extend(tzData[s])
    tzPairs1.sort()

    # Check duplicates
    tzPairs2 = list()
    tDup = []
    zDup = []
    for (t,z) in tzPairs1:
        if (len(tDup)>0 and abs(t-tDup[0])<timeTol):
            tDup.append(t)
            zDup.append(z)
        else:
            if (len(zDup)>0):
                tzPairs2[-1]=(statistics.median(tDup),
                              statistics.median(zDup))
            tzPairs2.append((t,z))
            tDup = [t]
            zDup = [z]
    if (len(zDup)>1):
        tzPairs2[-1]=(statistics.median(tDup),
                      statistics.median(zDup))

    tzData3 = dict()
    tzData3[MERGE] = tzPairs2

    return tzData3

def AlignMedian(tzData, refDate, **kwargs):
    '''
    Aligns data for dict with tzPair lists, so that median is zero at refDate.

    A tzPair list is a list containing (t,z) tuples, both doubles.
    t is days since T0 (1-jan-1970).

    Returns shifted tzData
    '''
    tzMeds, _ = AnalyzeTZSeries(tzData, **kwargs)

    dz = IF.Interpolate(tzMeds[MEDIAN], refDate, extrapol=False)

    tzData[MEDIAN] = tzMeds[MEDIAN]

    for s in tzData:
        tzData[s] = [(t, z-dz) for (t,z) in tzData[s]]

    return tzData

# Performance timing
times3=dict()
for i in range(20):
    times3[i]=0

def GETTIME3():
    return times3

def AlignAllMedian(tzData, refDate, **kwargs):
    '''
    Heights are shifted height is zero at refDate (all surveys
    and median shifted separately, so they line up with the median)
    
    A tzPair list is a list containing (t,z) tuples, both doubles.
    t is days since T0 (1-jan-1970).

    Returns shifted tzData
    '''
    # Performance timing
    start=time.time() # TIME

    # So we can modify
    tzData = copy.deepcopy(tzData)

    # Performance timing
    times3[0]+=time.time()-start
    start=time.time() # TIME

    # Anything to do?
    if (len(tzData)==0):
        return tzData

    # Calculate the median, and shifts between the curves
    tzMed, dzSrvy = AnalyzeTZSeries(tzData, **kwargs)

    # Performance timing
    times3[1]+=time.time()-start
    start=time.time() # TIME

    # Align curves to the median
    for srvy in tzData:
        dz = float(dzSrvy[DZ][srvy])
        tzPairs = tzData[srvy]
        tzData[srvy] = [(tz[0], tz[1]+dz) for tz in tzPairs]

    # Performance timing
    times3[2]+=time.time()-start
    start=time.time() # TIME

    # Calculate the shift of the median to be zero at the refDate
    dz = IF.Interpolate(tzMed[MEDIAN], refDate, extrapol=False)

    # Performance timing
    times3[3]+=time.time()-start
    start=time.time() # TIME

    # Include the median, and apply the overall shift
    tzData[MEDIAN] = tzMed[MEDIAN]
    for srvy in tzData:
        tzPairs = tzData[srvy]
        tzData[srvy] = [(tz[0], tz[1]-dz) for tz in tzPairs]

    # Performance timing
    times3[4]+=time.time()-start
    start=time.time() # TIME

    return tzData


# Performance timing
times2=dict()
for i in range(20):
    times2[i]=0

def GETTIME2():
    return times2

def AlignAllMedian2Level(tzMultiData, refDate, **kwargs):
    '''
    Output is a dict, keyed on peilmerk name. Each element is again
    a dict, keyed on survey. Elements of that are a list of (t,z) tuples
    representing the heights.
    For each peilmerk a MEDIAN curve is provided (survey name set to MEDIAN).
    For the total an overall MEDIAN curve is provided (i.e. peilmerk name 
    and survey name are MEDIAN).
    
    Times are in days since T0 (1-1-1970).
    '''
    # Performance timing
    start=time.time() # TIME

    # Anything to do?
    if (len(tzMultiData)==0):
        tzOut = dict()
        tzOut[MEDIAN] = dict()
        tzOut[MEDIAN][MEDIAN] = []
        return tzOut

    # List of keys at 2nd level
    pms = tzMultiData.keys()

    # Init admin
    tzOut = dict()
    tzMeds = dict()

    # Performance timing
    times2[0]+=time.time()-start
    start=time.time() # TIME

    # Loop over 2nd level
    for lspm in pms:
        # Performance timing
        times2[1]+=time.time()-start
        start=time.time() # TIME

        # Get subset
        tzSpm = tzMultiData[lspm]

        # Performance timing
        times2[2]+=time.time()-start
        start=time.time() # TIME

        # Do 1st level
        tzCurMed = AlignAllMedian(tzSpm, refDate, **kwargs)

        # Performance timing
        times2[3]+=time.time()-start
        start=time.time() # TIME

        # Extract and collect the medians (with proper key)
        tzMeds[lspm] = tzCurMed[MEDIAN]

        # Performance timing
        times2[5]+=time.time()-start
        start=time.time() # TIME

        # Collate the level1-aligned data
        tzOut[lspm] = tzCurMed

        # Performance timing
        times2[6]+=time.time()-start
        start=time.time() # TIME

    # Performance timing
    times2[7]+=time.time()-start
    start=time.time() # TIME

    # Calculate the median of medians, and the shifts needed to align at level 2
    tzAllMed, dzSpm = AnalyzeTZSeries(tzMeds, **kwargs)

    # Performance timing
    times2[8]+=time.time()-start
    start=time.time() # TIME

    # Align curves to the level-2 median
    for lspm in dzSpm[DZ]:
        dz = float(dzSpm[DZ][lspm])
        for lsrvy in tzOut[lspm]:
            tzPairs = tzOut[lspm][lsrvy]
            ll = len(tzPairs)
            for indx in range(ll):
                tz = tzPairs[indx]
                tzPairs[indx] = (tz[0], tz[1]+dz)

    # Performance timing
    times2[9]+=time.time()-start
    start=time.time() # TIME

    # Calculate the shift of the median of medians to be zero at the refDate
    tzMed2 = tzAllMed[MEDIAN]
    dz = IF.Interpolate(tzMed2, refDate, extrapol=False)

    # Performance timing
    times2[10]+=time.time()-start
    start=time.time() # TIME

    # Include the level 2 median in the output
    tzOut[MEDIAN] = dict()
    tzOut[MEDIAN][MEDIAN] = tzMed2

    # Performance timing
    times2[11]+=time.time()-start
    start=time.time() # TIME

    # Apply the overall level 2 shift
    for lspm, tzData in tzOut.items():
        ApplyZShift(tzData, -dz)

    # Performance timing
    times2[12]+=time.time()-start
    start=time.time() # TIME

    return tzOut

def ApplyZShift(tzData, dz):
    '''
    Apply z shift to tzData = dict, each element being a list of (t,z) tuples
    '''
    for lsrvy in tzData:
        tzPairs = tzData[lsrvy]
        ll = len(tzPairs)
        # Need to modify tuples in list
        for indx in range(ll):
            tz = tzPairs[indx]
            tzPairs[indx] = (tz[0], tz[1]+dz)
        #tzData[lsrvy] = tzPairs # redundant

def AlignAllSegmentMedian(tzData, refDate, timeTol=30, **kwargs):
    '''
    Align tzData on time refDate.
    No extrapolation across segmentsm, so data that is not
    connected to refDate is dropped.
    '''
    # Calculate basics
    tzMed, dzData = AnalyzeTZSeries(tzData, timeTol=timeTol, **kwargs)

    # Figure out in which segment the time is located
    g0 = None
    tz0 = None
    dz = None
    for g, tzPairs in tzMed.items():
        if (g != MEDIAN):
            d1 = tzPairs[0][0]
            d2 = tzPairs[-1][0]
            if (d1<=refDate+timeTol) and (d2>=refDate-timeTol):
                dz = IF.Interpolate(tzPairs, refDate, extrapol=False)
                tz0 = tzPairs
                g0 = g
                break
    if (dz is None):
        print("No segment found for this time")
        return dict()
    #print("Segment found:", g0, ", shift", dz)

    # Get list of surveys in that segment
    srvys = [s for s in dzData[SEGMENT] if dzData[SEGMENT][s]==g0]

    # And filter the data to that
    tzData = {s:tzData[s] for s in srvys}

    # Apply the overall shift
    tzData[MEDIAN_SEGMENT]=tz0
    ApplyZShift(tzData, dz)

    return tzData

def CalcAlignment(tzData1, tzData2, focusAfterDated=None, timeTol=30): # days
    '''
    calc height shift needed to align 'tzData1' wih 'tzData2'
    '''
    # If one of the series is empty, nothing to do
    dz=0.0
    if(len(tzData1)==0 or len(tzData2)==0): return dz

    # Prepare admin
    dtz = []
    i1 = 0
    i2 = 0
    (tL1,zL1) = (None,None)
    (t1,z1) = tzData1[i1]
    (tL2,zL2) = (None,None)
    (t2,z2) = tzData2[i1]

    # Loop over all points in the two series.
    # Build a list of (t,dz) pairs, where each dz is a
    # z-value from one series minus an interpolation
    # from the other (or vice versa)
    while (True):
        if(t1<t2):
            # t1 is the first point in line
            # can we interpolate?
            if(tL2 is not None):
                zInt1=z1
                zInt2=(t1-tL2)/(t2-tL2)*(z2-zL2)+zL2
                dtz.append((t1,zInt2-zInt1))

            # Move to the next point
            i1+=1
            (tL1,zL1)=(t1,z1)
            if (i1>=len(tzData1)):
                break
            (t1,z1)=tzData1[i1]
        elif(t2<t1):
            # t2 is the first point in line
            # can we interpolate?
            if(tL1 is not None):
                zInt1=(t2-tL1)/(t1-tL1)*(z1-zL1)+zL1
                zInt2=z2
                dtz.append((t2,zInt2-zInt1))
            # Move to the next point
            i2+=1
            (tL2,zL2)=(t2,z2)
            if (i2>=len(tzData2)):
                break
            (t2,z2)=tzData2[i1]
        else: #(t2==t1):
            # t1=t2 is the first point in line
            # can we interpolate?
            zInt1=z1
            zInt2=z2
            dtz.append((t1,zInt2-zInt1))
            tA=t1

            # Move to the next point depending on the next value
            if (i1>=len(tzData1)-1):
                if (i2>=len(tzData2)-1):
                    # both at the end: we're done
                    break
                #1 at the end, move #2
                moveIt=2
            elif (i2>=len(tzData2)-1):
                #2 at the end, move #1
                moveIt=1
            else:
                #both have space. Move the one with the smallest next value
                if (tzData1[i1+1][0]<tzData2[i2+1][0]):
                    moveIt=1
                else:
                    moveIt=2

            if (moveIt==1):
                (tL1,zL1)=(t1,z1)
                i1+=1
                (t1,z1)=tzData1[i1]
            else:
                (tL2,zL2)=(t2,z2)
                i2+=1
                (t2,z2)=tzData2[i2]

    # Was a focusdate supplied? Set a dummy date to facilitate comparison
    if (focusAfterDated is None): focusAfterDated=0

    # Final integration. Handle cases with zero/one points
    if (len(dtz)==0):
        #print("Zero points, no overlap")
        if (i1>=len(tzData1) and i2==0):
            if (tL1+timeTol>t2):
                #print("but it's close!")
                dtz.append(((tL1+t2)/2,z2-zL1))
        elif (i2>=len(tzData2) and i1==0):
            if (tL2+timeTol>t1):
                #print("but it's close!")
                dtz.append(((t1+tL2)/2,zL2-z1))

    if (len(dtz)==0):
        raise NoOverlapException("Really zero points, no overlap")
    elif (len(dtz)==1) or (dtz[-1][0]==dtz[0][0]):
        #print("One point")
        dz=(dtz[-1][1]+dtz[0][1])/2
    else:
        # Calculate the actual alignment
        # Focus on time after 'focusAfterDated' if possible
        (t1,dz1)=dtz[0]
        dt=0.0
        for indx in range(1,len(dtz)):
            (t2,dz2)=dtz[indx]

            w=1.0
            if (t2<focusAfterDated):
                w=0.001 # TODO: UGLY

            dz += (t2-t1)*w*(dz1+dz2)/2
            dt += (t2-t1)*w

            (t1,dz1)=(t2,dz2)

        dz /= dt

    return -dz
