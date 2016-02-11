# -*- coding: utf-8 -*-
"""
Created on Mon Feb  8 20:44:54 2016

@author: fergal

$Id$
$URL$
"""

__version__ = "$Id$"
__URL__ = "$URL$"



import matplotlib.pyplot as mp
import numpy as np

import dave.fileio.kplrfits as kplrfits
import dave.pipeline.fergalmain as fm
import dave.pipeline.task as task
import dave.pipeline.clipboard as dpc
import dave.pipeline.pipeline as pl
import dave.pipeline.plotting as dpp
import dave.misc.noise as noise

import plotting


def main():

    cfg = loadConfigForTest()
    data = np.loadtxt("kees-c5.txt", delimiter=",", usecols=(0,))

#    setattr(fm, 'fblsTask', fblsTask)
    fm.fblsTask = fblsTask
    print fm.__dict__.keys()

#    for epic in data[:1]:
#        print epic
#        clip = fm.runOne(epic, cfg)

    fm.runAll(fm.runOne, data[:], cfg)
#    return clip


def loadConfigForTest():
    cfg = fm.loadMyConfiguration()
    cfg['debug'] = True
    cfg['campaign'] = 5
    cfg['clipSavePath'] = "./clips"

    tasks = """dpp.checkDirExistTask dpp.serveTask dpp.extractLightcurveTask
        dpp.cotrendDataTask
        dpp.detrendDataTask dpp.blsTask fblsTask dpp.saveClip""".split()
#
    cfg['taskList'] = tasks
    return cfg


from glob import glob
def compareResults():
    clipList = glob('clips/c*.clip')

    data = map(lambda x: getData(x), clipList)
    data = np.array(data)
    return data


def getData(fn):
    clip = dpc.loadClipboard(fn)
    clip = pl.serveTask(clip)

    out = [clip['value']]
    for k in "period epoch depth duration_hrs".split():
        key1 = "bls.%s" %(k)
        key2 = "fbls.%s" %(k)
        out.extend( [clip[key1], clip[key2]])

    #Recompute SNR
    time = clip['serve.time']
    flux = clip['detrend.flux_frac']
    flag = clip['detrend.flags']

    per = clip['fbls.period']
    epc = clip['fbls.epoch']
    depth_frac = clip['fbls.depth']
    dur_days = clip['fbls.duration_hrs']/24.

    #Try mesauring SNR assuming there is a transit and a secondary
    #we want to cut out.
    try:
        idx = kplrfits.markTransitCadences(time, per/2., epc, \
            dur_days, flags=flag)
        idx = idx | flag
        snr = estSnrForK2(flux[~idx], depth_frac, dur_days)
    except ValueError:
        #If the above results in no data points, try just excising
        #the primary
        try:
            idx = kplrfits.markTransitCadences(time, per, epc, \
                dur_days, flags=flag)
            idx = idx | flag
            snr = estSnrForK2(flux[~idx], depth_frac, dur_days)
        except ValueError:
            #Give up
            snr = -1


    out.append(snr)
    print out[0], out[-1]
    return out


def estSnrForK2(flux_norm, depth_frac, duration_days):
    duration_cadences = int(np.round(duration_days*48)) #Correct for K2
    noi_frac = noise.computeSgCdpp_ppm(flux_norm, duration_cadences)*1e-6
    return depth_frac/noi_frac * np.sqrt(duration_cadences)

import fbls
@task.task
def fblsTask(clip):
    time_days = clip['serve.time']
    flux_norm = clip['detrend.flux_frac']
    flags = clip['detrend.flags']
    minPeriod = clip['config.blsMinPeriod']
    maxPeriod = clip['config.blsMaxPeriod']

    durations = np.array([ 2,4,6,8, 10, 12])/24.
    idx = flags == 0
    blsObj = fbls.BlsSearch(time_days[idx], flux_norm[idx], \
        [minPeriod, maxPeriod], durations)

    period, epoch, depth, duration = blsObj.getEvent()
    spectrum = blsObj.compute1dBls()

    duration_cadences = int(np.round(duration*48)) #Correct for K2
    noi = noise.computeSgCdpp_ppm(flux_norm[idx], duration_cadences)*1e-6

    out = dict()
    out['period'] = period
    out['epoch'] = epoch
    out['duration_hrs'] = duration * 24
    out['depth'] = depth
    out['snr'] = depth/noi
    out['bls_search_periods'] = spectrum[:,0]
    out['convolved_bls'] = spectrum[:,1]
#    out['bls'] = bls  #bls array is extremely big
    clip['bls'] = out

    #Enforce contract
    clip['bls.period']
    clip['bls.epoch']
    clip['bls.duration_hrs']
    return clip


def runFblsOnClip(clip):
    """Debugging function"""

    time = clip['serve.time']
    flux = clip['detrend.flux_frac']
    flag = clip['detrend.flags']

    durations = np.array([2,4,6,8, 10, 12, 14, 16])/24.
    blsObj = fbls.BlsSearch(time[~flag], flux[~flag], [0.5,30], durations)

    print blsObj.getEvent()
    return blsObj


#####################################################


def plotResults(data):
    mp.figure(1)
    mp.clf()
#    pObj = plotting.InteractivePlot(data, 1, 2, compPeriods, loadClipAndCompFits)
    idx = data[:, -2] < 6.1

    pObj = plotting.InteractivePlot(data[idx], 2, 9, pVDepth, loadClipAndCompFits)
    return pObj

def compPeriods(data, xCol, yCol):
#    mp.clf()
    sVal = 1e5*data[:,6]
    mp.scatter(data[:,1], data[:,2], s=sVal, alpha=1, \
        c=data[:,6], cmap=mp.cm.rainbow_r);
#    mp.colorbar()

    x = np.array([-5, 35])
    mp.plot(x, x, 'k-', lw=2)
    mp.plot(x, 2*x, 'k-', lw=2)
    mp.plot(x, .5*x, 'k-', lw=2)
    mp.xlim(x)
    mp.ylim(x)


def pVDepth(data, xCol, yCol):
    sVal = 10*data[:,8]

    mp.scatter(data[:,2], data[:, 9], s=sVal, c=data[:,8], lw=0,\
        cmap=mp.cm.rainbow)
#    mp.colorbar()
#    mp.ylim(0, .005)

def loadClipAndCompFits(data, row):
    epic = data[row, 0]

    clip = dpc.loadClipboard("clips/c%09i-05.clip" %(epic))
    clip = pl.serveTask(clip)


    mp.figure(2)
    mp.clf()
    dpp.plotData(clip)
    mp.title('Epic %.0f' %(epic))

    mp.figure(3)
    mp.clf()
    compareFits(clip)
    mp.title('Epic %.0f' %(epic))

    mp.figure(1)

    print "**************"
    print row, epic
    print clip.bls
    print clip.fbls
    flux = clip.detrend.flux_frac
    flags = clip.detrend.flags
    noi = noise.computeSgCdpp_ppm(flux[~flags]) * 1e-6
    print "BLS SNR= %.2f" %(clip.bls.depth/noi)
    print "fBLS SNR= %.2f" %(clip.fbls.depth/noi)


def compareFits(clip):
    time = clip.serve.time
    flux = clip.detrend.flux_frac
    flags = clip.detrend.flags

    p1 = clip.bls.period
    p2 = clip.fbls.period
    e1 = clip.bls.epoch - p1
    e2 =  clip.fbls.epoch - p2

    if e2 > 4000:
        e2 -= np.min(time[~flags])

    depth1 = clip.bls.depth
    depth2 = clip.fbls.depth

    dur1 = clip.bls.duration_hrs/24.
    dur2 = clip.fbls.duration_hrs/24.

    off1 = .25*p1
    off2 = .25*p2
    phi1 = np.fmod(time - e1+off1, clip.bls.period)
    phi2 = np.fmod(time - e2+off2, clip.fbls.period)

    mp.clf()
    mp.plot(phi1[~flags]*24, flux[~flags], 'k.')
    mp.plot(phi2[~flags]*24, .01+ flux[~flags], 'r.')

    lwr = 24*(off1-dur1)
    upr = 24*(off1+dur1)
    mp.plot([lwr, upr], [-depth1, -depth1], 'c-', lw=4)

    lwr = 24*(off2-dur2)
    upr = 24*(off2+dur2)
    mp.plot([lwr,upr], [.01-depth2, .01-depth2], 'c-', lw=4)
    mp.xlabel("Time from mid transit (hrs)")

if __name__ == "__main__":
    main()