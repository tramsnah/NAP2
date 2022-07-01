''''
Auxiliary interpolation functions
'''

###############################################################################
def GetClosest(tzPairs, t): 
    '''
    Get closest tz pair  
    If series has length 1, the t value supplied is the answer
    If the series has length 0, an IndexError is raised
    '''
    nx = len(tzPairs)
    if (nx<2):
        return tzPairs[0]

    i0 = 0
    i9 = nx-1
    xmin = tzPairs[i0][0]
    xmax = tzPairs[i9][0]
    #increasing = 1
    
    # Increasing or decreasing?
    if (xmin > xmax):
        (i0,i9) = (i9,i0)
        (xmin,xmax) = (xmax,xmin)
        #increasing = -1
    
    # Underflow (below min xa)
    if (t <= xmin):
        r = tzPairs[i0]
    # Overflow (above max xa)
    elif (t >= xmax):
        r = tzPairs[i9]
    # Binary search in table
    else:
        while (abs(i9-i0)>1):
            imid=int(0.5*(i0+i9))
            xmid=tzPairs[imid][0]
            if (xmid<t):
                i0=imid
            else:
                i9=imid

        x1 = tzPairs[i0][0]
        x2 = tzPairs[i9][0]
        r = tzPairs[i0] if abs(t-x1)<abs(t-x2) else tzPairs[i9]
    
    return r

###############################################################################
def Interpolate(tzPairs, t, extrapol=True):
    '''
    Returns height from interpolating 't' in 'tzPairs'.
    'tzPairs' is a sorted list of (t,z) tuples.
    
    It is assumed there are no duplicate times.
    
    Linear extrapolation takes place, unless 'extrapol' is False
    
    raises IndexError if tzPairs is empty
    '''    
    
    # If series has length 1, the z value supplied is the answer
    # If the series has length 0, an IndexError is raised
    nx = len(tzPairs)
    if (nx<2):
        return tzPairs[0][1]

    i0 = 0
    i9 = nx-1
    xmin = tzPairs[i0][0]
    xmax = tzPairs[i9][0]
    #increasing = 1
    
    # Increasing or decreasing?
    if (xmin > xmax):
        (i0,i9) = (i9,i0)
        (xmin,xmax) = (xmax,xmin)
        #increasing = -1
    
    # Underflow (below min xa)
    if (not extrapol) and t <= xmin:
        r = tzPairs[i0][1]
    # Overflow (above max xa)
    elif (not extrapol) and t >= xmax:
        r = tzPairs[i9][1]
    # Interpolate in table
    else:
        while (abs(i9-i0)>1):
            imid=int(0.5*(i0+i9))
            xmid=tzPairs[imid][0]
            if (xmid<t):
                i0=imid
            else:
                i9=imid

        y1 = tzPairs[i0][1]
        y2 = tzPairs[i9][1]
        x1 = tzPairs[i0][0]
        x2 = tzPairs[i9][0]
        g = (y2 - y1) / (x2 - x1)
        r = y1 + g * (t - x1)
    
    return r
