#!/usr/bin/env python

#stdlib imports
import urllib2
import urllib
import urlparse
import re
import json
import os.path
import StringIO
import tempfile
import datetime
import sys
import argparse

#local imports
import quakeml
import ndk

QUICKURL = 'http://www.ldeo.columbia.edu/~gcmt/projects/CMT/catalog/NEW_QUICK/qcmt.ndk'
MONTHLYURL = 'http://www.ldeo.columbia.edu/~gcmt/projects/CMT/catalog/NEW_MONTHLY/'
COMCATBASE = 'http://comcat.cr.usgs.gov/earthquakes/eventpage/[EVENTID]'
DEVCOMCATBASE = 'http://dev-earthquake.cr.usgs.gov/earthquakes/eventpage/[EVENTID]'

def getQuickNDK():
    ndkfilename = None
    try:
        fh = urllib2.urlopen(QUICKURL)
        data = fh.read()
        f,ndkfilename = tempfile.mkstemp(suffix='.ndk')
        os.close(f)
        ndkfile = open(ndkfilename,'wt')
        ndkfile.write(data)
        ndkfile.close()
        fh.close()
    except:
        pass
    return ndkfilename

def addMonth(dinput):
    year = dinput.year
    month = dinput.month
    if dinput.month == 12:
        month = 1
        year += 1
    doutput = datetime.datetime(year,month,1)
    return doutput
        
    
def getRecentMonth(lastmonth):
    months = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
    year = int(lastmonth[3:5]) + 2000
    month = months.index(lastmonth[0:3]) + 1
    recentmonth = datetime.datetime(year,month,1)
    ndkfilename = None
    newrecentmonth = lastmonth
    newstart = None
    try:
        fh = urllib2.urlopen(MONTHLYURL)
        data = fh.read()
        fh.close()
        matches = re.findall('>[0-9]{4}\/<',data)
        matches = sorted(matches)
        endyear = matches[-1][1:6]
        endyearurl = urlparse.urljoin(MONTHLYURL,endyear)
        fh = urllib2.urlopen(endyearurl)
        data = fh.read()
        fh.close()
        pat = '[a-z]{3}[0-9]{2}\.ndk'
        matches = re.findall(pat,data)
        matches = list(set(matches)) #unique values
        eventmonths = []
        for match in matches:
            eyear = int(match[3:5]) + 2000
            emonth = months.index(match[0:3]) + 1
            eventmonth = datetime.datetime(eyear,emonth,1)
            eventmonths.append((eventmonth,match))

        eventmonths = sorted(eventmonths,key=lambda e: e[0])
        if eventmonths[-1][0] > recentmonth:
            f,ndkfilename = tempfile.mkstemp(suffix='.ndk')
            os.close(f)
            ndkurl = urlparse.urljoin(endyearurl,eventmonths[-1][1])
            fh = urllib2.urlopen(ndkurl)
            data = fh.read()
            fh.close()
            ndkfile = open(ndkfilename,'wt')
            ndkfile.write(data)
            ndkfile.close()
            newrecentmonth = eventmonths[-1][1]
            newstart = addMonth(eventmonths[-1][0])
    except Exception,message:
        pass
    return (ndkfilename,newrecentmonth,newstart)

def eventInComCat(event,isdev=False):
    gcmtid = 'gcmt'+event['id']
    if isdev:
        url = COMCATBASE.replace('[EVENTID]',gcmtid)
    else:
        url = DEVCOMCATBASE.replace('[EVENTID]',gcmtid)
    inComCat = True
    try:
        fh = urllib2.urlopen(url)
        fh.close()
    except:
        inComCat = False
    return inComCat

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('ndkfile', metavar='NDKFILE', 
                           help='NDK file to load')
    parser.add_argument('-d','--dev', dest='useDev',action='store_true',
                        help='Use development comcat server')
    parser.add_argument('-n','--noclean', dest='noClean',action='store_true',
                        help='Leave generated quakeml files behind')
    parser.add_argument('-t','--test-mode', dest='testMode',action='store_true',
                        help='Run in test mode - write QuakeML to disk then stop.')
    parser.add_argument('-m','--moment-category', dest='momentCategory',choices=['teleseismic','regional'],
                        default='teleseismic',help='Choose the moment tensor category.')
    
    args = parser.parse_args()
    homedir = os.path.dirname(os.path.abspath(__file__)) #where is this script?
    quake = quakeml.QuakeML(quakeml.TENSOR,'ndk',method='Mww',
                            contributor='us',catalog='us',agency='us',
                            triggersource='us')


    #get ndk file
    ndkfile = args.ndkfile
    if not os.path.isfile(ndkfile):
        print '%s is not a valid file.  Returning.' % ndkfile
        sys.exit(1)
    
    for event in ndk.getEvents([ndkfile]):
        event['method'] = 'Mww' #we need to override the default Mwc (hack-ish)
        for magobj in event['magnitude']:
            magobj['method'] = 'Mww'
        event['momentcategory'] = args.momentCategory
        quake.add(event)
    
    for event,origins,events in quake.generateEvents():
        #what to do with multiple or no origins?
        quakemlfile = quake.renderXML(event,origins[0])
        if not args.testMode:
            print 'Rendering quick event %s' % event['id']
            res,output,errors = quake.push(quakemlfile)
            if res:
                print output
            else:
                print errors
        else:
            print 'Saving file %s' % quakemlfile

    if not args.noClean:
        os.remove(quakemlfile)

    sys.exit(0)
    
    
