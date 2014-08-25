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
import calendar

#local imports
import quakeml
import ndk

QUICKURL = 'http://www.ldeo.columbia.edu/~gcmt/projects/CMT/catalog/NEW_QUICK/qcmt.ndk'
MONTHLYURL = 'http://www.ldeo.columbia.edu/~gcmt/projects/CMT/catalog/NEW_MONTHLY/'
COMCATBASE = 'http://comcat.cr.usgs.gov/earthquakes/eventpage/[EVENTID]'
DEVCOMCATBASE = 'http://dev-earthquake.cr.usgs.gov/earthquakes/eventpage/[EVENTID]'
TIMEFMT = '%Y-%m-%d %H:%M:%S.%f'

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
    else:
        month += 1
    doutput = datetime.datetime(year,month,1)
    return doutput

def getAllMonths(lastreviewed):
    months = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
    endofmonth = datetime.datetime(1990,1,1)
    ndkfiles = []
    try:
        fh = urllib2.urlopen(MONTHLYURL)
        data = fh.read()
        fh.close()
        matches = re.findall('>[0-9]{4}\/<',data)
        matches = sorted(matches)
        ndkfiles = []
        for match in matches:
            myear = int(match[1:5])
            checkdate = datetime.datetime(myear,1,1)
            if checkdate <= lastreviewed:
                continue
            tndkfiles,tmonth = getYearMonths(myear,lastreviewed)
            if tmonth > endofmonth:
                endofmonth = tmonth
            ndkfiles += tndkfiles
    except Exception,message:
        raise Exception,'Could not retrieve data from %s.  Message: "%s"' % (MONTHLYURL,message.message)

    return (ndkfiles,endofmonth)

def getYearMonths(year,lastreviewed):
    months = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
    ndkfiles = []
    yearurl = urlparse.urljoin(MONTHLYURL,str(year)+'/')
    fh = urllib2.urlopen(yearurl)
    data = fh.read()
    fh.close()
    endofmonth = datetime.datetime(1990,1,1)
    pat = '[a-z]{3}[0-9]{2}\.ndk'
    matches = re.findall(pat,data)
    matches = list(set(matches)) #unique values
    eventmonths = []
    for match in matches:
        eyear = int(match[3:5]) + 2000
        emonth = months.index(match[0:3]) + 1
        monthstart = datetime.datetime(eyear,emonth,1)
        wkday,numdays = calendar.monthrange(eyear,emonth)
        monthend = datetime.datetime(eyear,emonth,numdays,23,59,59)
        if monthend > endofmonth:
            endofmonth = monthend
        if monthstart > lastreviewed:
            ndkurl = urlparse.urljoin(yearurl,match)
            ndkfiles.append(getMonthlyNDK(ndkurl))
    return (ndkfiles,endofmonth)
    
def getRecentMonths(lastreviewed):
    ndkfiles = []
    try:
        fh = urllib2.urlopen(MONTHLYURL)
        data = fh.read()
        fh.close()
        matches = re.findall('>[0-9]{4}\/<',data)
        matches = sorted(matches)
        endyear = int(matches[-1][1:5])
        tndkfiles,endofmonth = getYearMonths(endyear,lastreviewed)
        ndkfiles += tndkfiles
    except Exception,message:
        raise Exception,'Could not retrieve data from %s.  Message: "%s"' % (MONTHLYURL,message.message)
    return (ndkfiles,endofmonth)

def getMonthlyNDK(ndkurl):
    f,ndkfilename = tempfile.mkstemp(suffix='.ndk')
    os.close(f)
    fh = urllib2.urlopen(ndkurl)
    data = fh.read()
    fh.close()
    ndkfile = open(ndkfilename,'wt')
    ndkfile.write(data)
    ndkfile.close()
    return ndkfilename

def eventInComCat(event,isdev=False):
    gcmtid = 'gcmt'+event['id']
    if not isdev:
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
    parser.add_argument('-d','--dev', dest='useDev',action='store_true',
                        help='Use development comcat server')
    parser.add_argument('-n','--no-clean', dest='noClean',action='store_true',
                        help='Do not clean up local quakeml files (debugging only!)')
    parser.add_argument('-t','--test-mode', dest='testMode',action='store_true',
                        help='Do not attempt to post events into Comcat')
    parser.add_argument('-f','--force', dest='force',action='store_true',
                        help='Force re-loading of events already found in ComCat.')
    parser.add_argument('-a','--alldata', dest='alldata',action='store_true',
                        help='Retrieve all data since last processtime (defaults to only current year).')
    
    args = parser.parse_args()
    homedir = os.path.dirname(os.path.abspath(__file__)) #where is this script?

    #this text file should have key:pair values
    lastprocessedfile = os.path.join(homedir,'lastprocessed.txt')
    processdict = {'lastreviewed':datetime.datetime(2010,1,1),'lastquick':datetime.datetime(2010,1,1)}
    if os.path.isfile(lastprocessedfile):
        f = open(lastprocessedfile,'rt')
        for line in f.readlines():
            pkey,pvalue = line.strip().split('=')
            if pkey == 'lastreviewed':
                processdict['lastreviewed'] = datetime.datetime.strptime(pvalue.strip(),TIMEFMT)
            if pkey == 'lastquick':
                processdict['lastquick'] = datetime.datetime.strptime(pvalue.strip(),TIMEFMT)
        f.close()


    quake = quakeml.QuakeML(quakeml.TENSOR,'ndk',method='Mwc',
                            contributor='us',catalog='gcmt',
                            triggersource='pde',agency='gcmt')

    #download our monthly ndk file and our quick file
    if args.alldata:
        mndkfiles,lastreviewed = getAllMonths(processdict['lastreviewed'])
    else:
        mndkfiles,lastreviewed = getRecentMonths(processdict['lastreviewed'])
    newstart = processdict['lastquick']
    if lastreviewed > newstart:
        newstart = lastreviewed - datetime.timedelta(days=7)
    else:
        newstart = processdict['lastquick'] - datetime.timedelta(days=7)

    #process quick solutions first
    qndkfile = getQuickNDK()
    if qndkfile is None: #couldn't get the quick CMT files
        sys.exit(1)
    for event in ndk.getEvents([qndkfile],startDate=newstart):
        if not args.force and eventInComCat(event,isdev=args.useDev):
            continue
        print 'Adding event %s' % event['id']
        quake.add(event)

    for event,origins,events in quake.generateEvents():
        #what to do with multiple or no origins?
        quakemlfile = quake.renderXML(event)
        print 'Rendering quick event %s' % event['id']
        if not args.testMode:
            nelapsed = (datetime.datetime.utcnow() - event['time']).days
            res,output,errors = quake.push(quakemlfile,nelapsed=nelapsed)
        if event['time'] > processdict['lastquick']:
            processdict['lastquick'] = event['time']

    #clean up quick NDK file
    os.remove(qndkfile)
    #clear the events out of our quakeml object
    quake.clear()
    
    #now process monthly reviewed stuff, if we have a new monthly file at all
    if not len(mndkfiles):
        quake.clearOutput()
        sys.exit(0)
    for mndkfile in mndkfiles:
        for event in ndk.getEvents([mndkfile]):
            quake.add(event)

    for event,origins,events in quake.generateEvents():
        #what to do with multiple or no origins?
        quakemlfile = quake.renderXML(event)
        print 'Rendering reviewed event %s' % event['id']
        if not args.testMode:
            nelapsed = (datetime.datetime.utcnow() - event['time']).days
            quake.push(quakemlfile,nelapsed=nelapsed)
        if event['time'] > processdict['lastreviewed']:
            processdict['lastreviewed'] = event['time']

    #Update the lastprocessed text file
    f = open(lastprocessedfile,'wt')
    f.write('lastreviewed=%s\n' % processdict['lastreviewed'].strftime(TIMEFMT))
    f.write('lastquick=%s\n' % processdict['lastquick'].strftime(TIMEFMT))
    f.close()
        
    #clean up after ourselves
    if not args.noClean:
        quake.clearOutput()
    for mndkfile in mndkfiles:
        os.remove(mndkfile)
    sys.exit(0)
    
    
