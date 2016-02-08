# -*- coding: utf-8 -*-

from __future__ import division
"""
Created on Thu Feb  4 11:04:41 2016

@author: fergal

$Id$
$URL$

Todo:
x Figure out a period list from a period range
x Check that wasp47 is found. Write as a test
o Add option of a condensed output to save memory, that gives an array
  of period, max(bls amplitude), epoch at max, duration at max
x Profile code
x Compute epoch of event from output array
o Adjust min points per transit duration



To profile code:
Add @profile decorator to functions you want to profile. From
command line run
> date; ~/bin/python ~/.local/lib/python2.7/site-packages/kernprof.py -l -v test_fbls.py > fbls.prof; date
Then edit the file fbls.prof
"""

__version__ = "$Id$"
__URL__ = "$URL$"



import matplotlib.pyplot as mp
import numpy as np

import dave.fileio.kplrfits as kplrfits



def meanZero(y):
    return y/np.mean(y) - 1



def fBls(time, flux, periodRange, durations):
    """
    Compute a bls spectrum of a lightcurve

    Inputs:
    ----------
    time, flux
        (1d np arrays) Times and fluxes of data. flux should have a mean
        of approximately zero.

    periodRange
        (2 element list) Minimum and maximum periods to search. Units
        the same as the time array

    durations
        (list) List of transit durations to search for. Note this
        is not necessarily in hours, but in the same units as the time array
        (which is commonly days).

    Returns:
    ----------
    Not yet decided

    Notes:
    ----------
    See bls.tex for notes on computationaly complexity.

    """

    assert(len(time) == len(flux))
    assert(np.all(np.isfinite(time)))
    assert(np.all(np.isfinite(flux)))
    assert(len(periodRange) == 2)

    if not hasattr(durations, "__len__"):
        durations = [durations]
    assert(len(durations) > 0)

    lwr, upr = periodRange
    periods = computePeriodList(lwr, upr, time, min(durations))

    bls = computeBlsForManyPeriods(time, flux, durations, periods)
    return bls, periods


def computePeriodList(Plwr, Pupr, time, duration, overres=2):
    """
    Compute the list of periods needed to comphrensively search a lightcurve
    with BLS.

    Inputs:
    -----------
    Plwr, Pupr
        (floats) Minimum and maximum periods to search

    time
        (list or array) times at which data is sampled. May be an array
        of all time values, or just a list of the first and last points.
    duration
        (float) Assumed transit duration in units of **time**
    overres
        How many times the minimum sampling should be performed

    Returns:
    -----------
    An array of periods to search at.

    Note:
    ---------
    See bls.tex in this directory for a description of this algorithm
    """


    assert(Pupr > Plwr)
    timespan = np.max(time) - np.min(time)
    q = duration/timespan/float(overres)

    nStep = int(np.round(np.log(Pupr/Plwr) / np.log(1+q)))
    n = np.arange(nStep)

    return Plwr*(1+q)**n


#@profile
def computeBlsForManyPeriods(t, y, durationList, periodList):
    """Worker function for fbls

    See fbls() for a description of inputs. Values for durationList
    and periodList should be given in the same units as t (usually days)

    Todo:
    Allow passing in weights on each data point to better account for
    varying noise.
    """
    assert(np.all(np.isfinite(t)))
    assert(np.all(np.isfinite(y)))

    durationList = np.array(durationList)
    periodList = np.array(periodList)
    if np.any(durationList <= 0):
        raise ValueError("Durations must be > 0")

    if np.any(periodList <= 0):
        raise ValueError("Periods must be > 0")

    minNumBinsPerTransit = 10  #Kovacs sugggest 15

    maxNumBins = minNumBinsPerTransit * max(periodList) / min(durationList)
    out = np.zeros((len(periodList), len(durationList), maxNumBins))
    dt = t - np.min(t)

    for i,period in enumerate(periodList):
        #Technically, the lightcurve should be refolded for each duration
        #But because the algorithm is only weakly sensitive to the bin width
        #above a certain value, we dramatically speed things up by
        #folding once per period
        nBins = int(minNumBinsPerTransit * period / min(durationList))

        if False:
            #Useful for debugging. This folder is much slower,
            #but well tested.
            expTime = np.median(np.diff(t))
            binned = kplrfits.foldAndBinData(dt, y, period, 0, expTime, nBins)
            binned = binned[:,1]
        else:
            binned = fastFoldAndBin(dt, y, period, nBins)


        for j,duration in enumerate(durationList):
            transitWidth = int(np.round(duration/period * nBins))  #nBins Wrong?

            if transitWidth > 0 and transitWidth < len(binned):
                bls = computeBlsForOnePeriod(binned, transitWidth)
                out[i,j, :nBins] = bls
    return out


#@profile
def fastFoldAndBin(t, y, period, nBins):
    """Fold and bin a (possibly unevenly spaced) lightcurve.

    Most of the time required to compute a BLS spectrum is spent
    folding and refolding the data at different periods. Time spent
    optimsing this action is time well spent. This is the fastest
    function I could think of. If you can think of away to do
    the same with one call to histogram you will halve the time spent
    on the entire BLS.

    Inputs:
    -----------
    t, y
        (1d arrays) Input time and flux. Time need not be evenly spaced.
    period
        (float) Period to fold at. Units the same as **t** (usually days)
    nBins
        (int) Number of bins to fold at.

    Returns:
    -----------
    1d array. The lightcurve is folded at the input period, then binned
    into nBin points. The epoch is chosen so that time==0 is mapped to
    phi==0.

    Note:
    ---------
    When using this function in a BLS code, you'd be wise to
    choose a time offset such that time==0 happens within the dataset. Otherwise
    the phase numbers might be unreliable..
    """
    phi = np.fmod(t, period)

    eps = 1e-10  #To prevent division by zero
    weights = np.histogram(phi, nBins, normed=False)[0] + eps
    binned = np.histogram(phi, nBins, weights=y, normed=False)[0]
    return binned/weights


#@profile
def computeBlsForOnePeriod(y, transitWidth):

    if transitWidth <= 0:
        raise ValueError("Transit width must be at least 1 cadence")

    if transitWidth >= len(y):
        raise ValueError("Transit width must be shorter than length of binned lightcurve")

    #If y has weights, s[], r = \Sigma s_i
    r = float(transitWidth)

    #if y has weights, s is the convolution of y*s by signal
    signal = np.ones(transitWidth)
    s = np.convolve(y, signal, mode='same')
    assert(len(s) == len(y))
    bls = s/np.sqrt(r)
    assert(len(bls) == len(y))

    return bls


#def getParamsOfDetection(blsArray, indices, duration_daysList, periodList):
#    assert(blsArray.ndim == 3)
#
#    if hasattr(indices, '__len__'):
#        assert(len(indices) in [1,3])
#    else:
#        indices = np.unravel_index(indices, blsArray.shape)
#
#    maxPeriod = np.max(periodList)
#
#    period = periodList[indices[0]]
#    duration_days = duration_daysList[indices[1]]
#    epoch = maxPeriod * (indices[2]/float(blsArray.shape[2]))
#
#    return period, epoch, duration_days


#@TODO, implement local copy of median detrend
import dave.fileio.kplrfits as kf
def findBestPeak(blsArray, nPointsForSmooth=100, offset=0):
    """Find the index of the best peak in the bls spectrum.

    The best peak is not usually the strongest one. The noise floor
    of a BLS increases at long period, so this must be accounted for
    before selecting the strongest amplitude.

    Inputs:
    -------------
    blsArray
        (3d numpy array)

    Optional Inputs:
    -----------------
    nPointsForSmooth
        (int) Tuning parameter. This is the number of points near a given
        period used to determine what the typical background BLS value is.

    offset
        (int) Debugging option. Change the chosen period by this number
        of indices.

    Returns:
    ------------
    A three element tuple of indices into blsArray giving the best
    period, duration and phase of transit.
    """
    bb = blsArray.max(axis=1)
    bbb = bb.max(axis=1)

    # bbb is 1d array of strongest peak at each period.
    # We need to remove background trend before we decide which peak
    # is the best choice
    filt = kf.medianSubtract1d(bbb, nPointsForSmooth)
    iPer = np.argmax(filt)
    iPer += offset
    subArray = blsArray[iPer,:,:]
    iDur, iPhase = np.unravel_index(np.argmax(subArray), subArray.shape)

    return iPer, iDur, iPhase


def getParamsOfIndex(blsArray, indices, duration_daysList, periodList):
    assert(blsArray.ndim == 3)

    if hasattr(indices, '__len__'):
        assert(len(indices) in [1,3])
    else:
        indices = np.unravel_index(indices, blsArray.shape)

    maxPeriod = np.max(periodList)

    period = periodList[indices[0]]
    duration_days = duration_daysList[indices[1]]
    epoch = maxPeriod * (indices[2]/float(blsArray.shape[2]))

    return period, epoch, duration_days