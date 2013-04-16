#!/usr/bin/env python

#stdlib imports
import sys
import os.path
import datetime
import optparse
import re
import math
import pickle


TIMEFMT = '%Y-%m-%d %H:%M:%S'

class MTReader(object):
    fh = None
    def __init__(self,mtfile,type=None):
        self.mtfile = mtfile
        self.type = type
        
    def generateRecords(self,startDate=None,enddate=None,hasHeader=False):
        pass

class NDKReader(MTReader):
    def generateRecords(self,startdate=None,enddate=None,hasHeader=False):
        tdict = {}
        if self.fh is None:
            self.fh = open(self.mtfile,'rt')
        lc = 0
        for line in self.fh.readlines():
            if (lc+1) % 5 == 1:
                self.parseLine1(line,tdict)
                lc += 1
                continue
            if (lc+1) % 5 == 2:
                self.parseLine2(line,tdict)
                lc += 1
                continue
            if (lc+1) % 5 == 3:
                self.parseLine3(line,tdict)
                lc += 1
                continue
            if (lc+1) % 5 == 4:
                self.parseLine4(line,tdict)
                lc += 1
                continue
            if (lc+1) % 5 == 0:
                self.parseLine5(line,tdict)
                if startdate is not None and enddate is not None:
                    if tdict['eventTime'] >= startdate and tdict['eventTime'] <= enddate:
                        yield self.trimFields(tdict)
                else:
                    yield self.trimFields(tdict)
                lc += 1
                tdict = {}
        
        self.fh.close()
        
    def trimFields(self,tdict):
        record = {}
        record['id'] = tdict['eventTime'].strftime('%Y%m%d%H%M%S')
        record['time'] = tdict['eventTime']
        record['type'] = self.type
        record['lat'] = tdict['eventLatitude']
        record['lon'] = tdict['eventLongitude']
        record['depth'] = tdict['eventDepth']
        record['mag'] = tdict['momentMagnitude']
        record['tazimuth'] = tdict['eigenVectorAzimuths'][0]
        record['tplunge'] = tdict['eigenVectorPlunges'][0]
        record['nazimuth'] = tdict['eigenVectorAzimuths'][1]
        record['nplunge'] = tdict['eigenVectorPlunges'][1]
        record['pazimuth'] = tdict['eigenVectorAzimuths'][2]
        record['pplunge'] = tdict['eigenVectorPlunges'][2]
        record['np1strike'] = tdict['nodalPlane1Strike']
        record['np1dip'] = tdict['nodalPlane1Dip']
        record['np1rake'] = tdict['nodalPlane1Rake']
        record['np2strike'] = tdict['nodalPlane2Strike']
        record['np2dip'] = tdict['nodalPlane2Dip']
        record['np2rake'] = tdict['nodalPlane2Rake']
        record['mrr'] = tdict['tensorMrr']
        record['mpp'] = tdict['tensorMpp']
        record['mtt'] = tdict['tensorMtt']
        record['mtp'] = tdict['tensorMtp']
        record['mrp'] = tdict['tensorMrp']
        record['mrt'] = tdict['tensorMrt']
        return record

    def parseLine1(self,line,tdict):
        tdict['eventSource'] = line[0:4]
        dstr = line[5:26]
        year = int(dstr[0:4])
        month = int(dstr[5:7])
        day = int(dstr[8:10])
        hour = int(dstr[11:13])
        minute = int(dstr[14:16])
        fseconds = float(dstr[17:])
        seconds = int(fseconds)
        if seconds > 59: #
            seconds = 59
        microseconds = int((fseconds-seconds)*1e6)
        if microseconds > 999999:
            microseconds = 999999
        try:
            tdict['eventTime'] = datetime.datetime(year,month,day,hour,minute,seconds,microseconds)
        except:
            pass
        tdict['eventLatitude'] = float(line[27:33])
        tdict['eventLongitude'] = float(line[34:41])
        tdict['eventDepth'] = float(line[42:47])
        parts = line[48:55].split()
        mag1 = float(line[47:51])
        mag2 = float(line[51:55])
        tdict['eventMagnitudes'] = [mag1,mag2]
        tdict['eventLocation'] = line[56:80].strip()
    
    def parseLine2(self,line,tdict):
        tdict['eventID'] = line[0:16].strip()

        tdict['BodyWaveStations'] = int(line[19:22].strip())
        tdict['BodyWaveComponents'] = int(line[22:27].strip())
        tdict['BodyWaveShortestPeriod'] = float(line[27:31].strip())

        tdict['SurfaceWaveStations'] = int(line[34:37].strip())
        tdict['SurfaceWaveComponents'] = int(line[37:42].strip())
        tdict['SurfaceWaveShortestPeriod'] = float(line[42:46].strip())

        tdict['MantleWaveStations'] = int(line[49:52].strip())
        tdict['MantleWaveComponents'] = int(line[52:57].strip())
        tdict['MantleWaveShortestPeriod'] = float(line[57:61].strip())

        cmt = line[62:68].strip()
        m0 = re.search("CMT:\\s*0",cmt)
        m1 = re.search("CMT:\\s*1",cmt)
        m2 = re.search("CMT:\\s*2",cmt)

        if (m0 is not None):
            tdict['sourceInversionType'] = "general moment tensor"
        elif (m1 is not None):
            tdict['sourceInversionType'] = "standard moment tensor"
        elif (m2 is not None):
            tdict['sourceInversionType'] = "double couple source"
        else:
            tdict['sourceInversionType'] = "unknown source inversion"

        tdict['momentRateFunction'] = line[69:74]
        tdict['momentRateFunctionDuration'] = float(line[75:].strip())

    def parseLine3(self,line,tdict):
        centroid = line[9:59]
        parts = centroid.split()

        microseconds = float(line[9:18].strip())*1e6;
        tdict['derivedEventTime'] = tdict['eventTime']+datetime.timedelta(microseconds=microseconds)

        tdict['derivedEventTimeError'] = float(line[18:23])
        tdict['derivedEventLatitude'] = float(line[23:30])
        tdict['derivedEventLatitudeError'] = float(line[29:34])
        tdict['derivedEventLongitude'] = float(line[34:42])
        tdict['derivedEventLongitudeError'] = float(line[42:47])
        tdict['derivedEventDepth'] = float(line[47:53])
        tdict['derivedEventDepthError'] = float(line[53:58])
        tdict['derivedDepthType'] = line[58:61].strip()

    def parseLine4(self,line,tdict):
        tdict['exponent'] = float(line[0:2])
        tdict['tensorMrr'] = float(line[2:9])*math.pow(10.0,tdict['exponent'])
        tdict['tensorMrrError'] = float(line[9:15])*math.pow(10.0,tdict['exponent'])
        tdict['tensorMtt'] = float(line[15:22])*math.pow(10.0,tdict['exponent'])
        tdict['tensorMttError'] = float(line[22:28])*math.pow(10.0,tdict['exponent'])
        tdict['tensorMpp'] = float(line[28:35])*math.pow(10.0,tdict['exponent'])
        tdict['tensorMppError'] = float(line[35:41])*math.pow(10.0,tdict['exponent'])
        tdict['tensorMrt'] = float(line[41:48])*math.pow(10.0,tdict['exponent'])
        tdict['tensorMrtError'] = float(line[48:54])*math.pow(10.0,tdict['exponent'])
        tdict['tensorMrp'] = float(line[54:61])*math.pow(10.0,tdict['exponent'])
        tdict['tensorMrpError'] = float(line[61:67])*math.pow(10.0,tdict['exponent'])
        tdict['tensorMtp'] = float(line[67:74])*math.pow(10.0,tdict['exponent'])
        tdict['tensorMtpError'] = float(line[74:])*math.pow(10.0,tdict['exponent'])

    def parseLine5(self,line,tdict):
        tdict['programVersion'] = line[0:3].strip()
        tdict['eigenVectorValues'] = []
        tdict['eigenVectorPlunges'] = []
        tdict['eigenVectorAzimuths'] = []

        tdict['eigenVectorValues'].append(float(line[3:11])*math.pow(10.0,tdict['exponent']))
        tdict['eigenVectorPlunges'].append(float(line[11:14]))
        tdict['eigenVectorAzimuths'].append(float(line[14:18]))

        tdict['eigenVectorValues'].append(float(line[18:26])*math.pow(10.0,tdict['exponent']))
        tdict['eigenVectorPlunges'].append(float(line[26:29]))
        tdict['eigenVectorAzimuths'].append(float(line[29:33]))

        tdict['eigenVectorValues'].append(float(line[33:41])*math.pow(10.0,tdict['exponent']))
        tdict['eigenVectorPlunges'].append(float(line[41:44]))
        tdict['eigenVectorAzimuths'].append(float(line[44:48]))

        tdict['scalarMoment'] = float(line[49:56].strip())*math.pow(10.0,tdict['exponent'])
        tdict['momentMagnitude'] = ((2.0/3.0) * math.log10(tdict['scalarMoment'])) - 10.7

        tdict['nodalPlane1Strike'] = float(line[56:60])
        tdict['nodalPlane1Dip'] = float(line[60:63])
        tdict['nodalPlane1Rake'] = float(line[63:68])

        tdict['nodalPlane2Strike'] = float(line[68:72])
        tdict['nodalPlane2Dip'] = float(line[72:75])
        tdict['nodalPlane2Rake'] = float(line[75:])


#this should be a generator
def getEvents(args,startDate=None,endDate=None):
    ndkfile = args[0]
    ndkreader = NDKReader(ndkfile)
    i = -1
    for record in ndkreader.generateRecords(startdate=startDate,enddate=endDate):
        i += 1
        yield record

        
if __name__ == '__main__':
    ndkfile = sys.argv[1]
    for record in getEvents(ndkfile):
        print record['time'],record['mag']
