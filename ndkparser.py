#!/usr/bin/env python

#stdlib imports
import sys
import os.path
import datetime
import optparse
import re
import math
import pickle

#local imports
import quakeml

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
        record['id'] = tdict['eventTime']
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

def processEvent(quake,event,origins,events,numevents,ievent):
    norg = len(origins)
    nevents = len(events)
    eventdesc = '%s: %s M%.1f (%.4f,%.4f)' % (event['id'],str(event['time']),event['mag'],event['lat'],event['lon'])
    ofmt = '\t%i) %s M%.1f (%.4f,%.4f) %.1f km - %.1f km distance, %i seconds'
    if norg == 1:
        quake.renderXML(event,origins[0])
        print 'Writing event %s to file (%i of %i).' % (eventdesc,ievent,numevents)
    if norg == 0:
        print 'No events associated with %s' % eventdesc
    if norg > 1:
        fmt = 'Event %s M%.1f (%.4f,%.4f) %.1f km has %i possible associations:'
        tpl = (event['time'],event['mag'],event['lat'],event['lon'],event['depth'],norg)
        print
        print fmt % tpl
        ic = 0
        for origin in origins:
            time = origin['time']
            mag = origin['mag']
            lat = origin['lat']
            lon = origin['lon']
            depth = origin['depth']
            timedelta = origin['timedelta']
            distance = origin['distance']
            tpl = (ic,time,mag,lat,lon,depth,distance,timedelta)
            print ofmt % tpl
            ic += 1
        print '\t%i) None of the above (do not associate)' % (ic)
        nresp = 0
        maxresp = 3
        ischar = True
        oidx = -1
        while oidx < 0 and nresp <= maxresp:
            resp = raw_input('Choose one of the options above: ')
            try:
                oidx = int(resp)
            except:
                pass
            nresp += 1
        if oidx >= 0:
            if oidx < ic:
                quake.renderXML(event,origins[oidx])
            else:
                print 'Not associating event, as requested.'
        else:
            print "You obviously can't read.  Moving on."

#this should be a generator
def getEvents(ndkfile):
    ndkreader = NDKReader(ndkfile)
    i = -1
    for record in ndkreader.generateRecords():
        i += 1
        print 'NDK Record %i' % i
        yield record

def main(options,args):
    xmlfolder = '/Users/mhearne/quakeml/wphase'
    twindow = 16
    dwindow = 100
    if options.timewindow is not None:
        twindow = int(options.timewindow)
    if options.distance is not None:
        dwindow = options.distance
    author = 'neic'
    agency = 'us'
    source = quakeml.DEFAULT_SOURCE
    triggersource = None
    method = None
    ptype = 'origin'
    folder = os.getcwd()
    if options.author is not None:
        author = options.author
    if options.agency is not None:
        agency = options.agency
    if options.source is not None:
        source = options.source
    if options.method is not None:
        method = options.method
    if options.folder is not None:
        folder = options.folder
    if options.triggersource is not None:
        triggersource = options.triggersource
    if options.producttype is not None:
        types = [quakeml.ORIGIN,quakeml.FOCAL,quakeml.TENSOR]
        ptype = options.producttype
        if ptype not in types:
            print '%s not in %s.  Exiting.' % (ptype,','.join(types))
            sys.exit(1)
    quake = quakeml.QuakeML(quakeml.TENSOR,folder,agency=agency,author=author,
                            triggersource=triggersource,method=method)
    if options.clear:
        quake.clearOutput()

    #parse the input data from file, database, webserver, whatever
    if os.path.isfile('ndkdump.pickle'):
        f = open('ndkdump.pickle','rb')
        eventlist = pickle.load(f)
        f.close()
        numevents = len(eventlist)
        for event in eventlist:
            quake.add(event)
    else:
        eventlist = []
        numevents = 0
        for event in getEvents(args[0]):
            xmlfile = os.path.join(folder,'%s.xml' % event['id'])
            if os.path.isfile(xmlfile):
                continue
            if options.loadOnly:
                eventlist.append(event)
            else:
                quake.add(event)
            numevents += 1

    if options.loadOnly:
        f = open('ndkdump.pickle','wb')
        pickle.dump(eventlist,f)
        f.close()
        sys.exit(0)
    
    numnear = len(quake.NearEventIndices)
    numprocessed = 0
    for event,origins,events in quake.generateEvents():
        processEvent(quake,event,origins,events,numevents,numprocessed)
        numprocessed += 1
        
if __name__ == '__main__':
    types = [quakeml.ORIGIN,quakeml.FOCAL,quakeml.TENSOR]
    usage = "usage: %prog [options] arg1 ... argN"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-t", "--timewindow", dest="timewindow",
                  help="change to TIME timewindow from 16 sec default", metavar="TIME")
    parser.add_option("-d", "--distance", dest="distance",
                  help="change to DISTANCE search radius from 100 km default", metavar="DISTANCE")
    parser.add_option("-a", "--author", dest="author",
                  help="Set the author of this catalog", metavar="AUTHOR")
    parser.add_option("-g", "--agency", dest="agency",
                  help="Set the agency of this catalog", metavar="AGENCY")
    parser.add_option("-s", "--source", dest="source",
                  help="Set the source for this data", metavar="SOURCE")
    parser.add_option("-r", "--triggersource", dest="triggersource",
                  help="Set the trigger source for this data", metavar="TRIGGERSOURCE")
    parser.add_option("-m", "--method", dest="method",
                  help="Set the method used to determine catalog", metavar="METHOD")
    parser.add_option("-f", "--folder", dest="folder",
                  help="Set folder for output QuakeML (default to cwd)", metavar="FOLDER")
    parser.add_option("-p", "--producttype", dest="producttype",
                  help="Define type of product (one of %s) (default to %s)" % (','.join(types),quakeml.ORIGIN), 
                  metavar="PRODUCTTYPE")
    parser.add_option("-l", "--loadonly",
                  action="store_true", dest="loadOnly", default=False,
                  help="Load NDK events from file, save to pickle")
    parser.add_option("-c", "--clear",
                  action="store_true", dest="clear", default=False,
                  help="Clear XML output")
    

    (options, args) = parser.parse_args()
    if len(args) == 0:
        parser.print_help()
        sys.exit(0)
    main(options,args)
