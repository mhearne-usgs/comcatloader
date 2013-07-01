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

#local imports
import quakeml
import ndk

QUICKURL = 'http://www.ldeo.columbia.edu/~gcmt/projects/CMT/catalog/NEW_QUICK/qcmt.ndk'
MONTHLYURL = 'http://www.ldeo.columbia.edu/~gcmt/projects/CMT/catalog/NEW_MONTHLY/'
COMCATBASE = 'http://comcat.cr.usgs.gov/earthquakes/feed/search.php?%s'

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

def eventInComCat(event):
    gcmtid = event['id']
    pdict = {'callback':'comsearch','id':gcmtid}
    inComCat = False
    params = urllib.urlencode(pdict)
    searchurl = COMCATBASE % params
    fh = urllib2.urlopen(searchurl)
    data = fh.read()
    data2 = data[len(pdict['callback'])+1:-2]
    datadict = json.loads(data2)
    if not datadict.has_key('message'):
        inComCat = True
    fh.close()
    return inComCat

if __name__ == '__main__':
    homedir = os.path.dirname(os.path.abspath(__file__)) #where is this script?
    #months should be stored as mmmyy (i.e., dec12)
    lastmonthfile = os.path.join(homedir,'lastmonth.txt')
    if not os.path.isfile(lastmonthfile):
        lastmonth = 'dec10'
        months = [lastmonth]
    else:
        months = open(lastmonthfile,'rt').readlines()
        lastmonth = months[-1]

    quake = quakeml.QuakeML(quakeml.TENSOR,'ndk',source='gcmt',
                            method='Mwc',agency='gcmt',
                            triggersource='pde')

    #download our monthly ndk file and our quick file
    mndkfile,newlastmonth,newstart = getRecentMonth(lastmonth)
    #process quick solutions first
    qndkfile = getQuickNDK()
    if qndkfile is None: #couldn't get the quick CMT files
        sys.exit(1)
    for event in ndk.getEvents([qndkfile],startDate=newstart):
        if eventInComCat(event):
            continue
        print 'Adding event %s' % event['id']
        quake.add(event)
    
    for event,origins,events in quake.generateEvents():
        #what to do with multiple or no origins?
        quakemlfile = quake.renderXML(event)
        print 'Rendering quick event %s' % event['id']
        #debugging remove this before deployment
        if event['time'] < datetime.datetime.now() - datetime.timedelta(days=30):
            continue
        quake.push(quakemlfile)

    #clean up after ourselves
    os.remove(qndkfile)
    #now process monthly reviewed stuff
    #clear the events out of our quakeml object
    quake.clear()
    #if we have a new month, add it to our lastmonth text file
    if newlastmonth not in months:
        months.append(newlastmonth)
        f = open(lastmonthfile,'wt')
        f.writelines(months)
        f.close()
        
    if mndkfile is None:
        quake.clearOutput()
        sys.exit(0)
    for event in ndk.getEvents([mndkfile]):
        quake.add(event)

    for event,origins,events in quake.generateEvents():
        #what to do with multiple or no origins?
        quakemlfile = quake.renderXML(event)
        print 'Rendering reviewed event %s' % event['id']
        quake.push(quakemlfile)
    #clean up after ourselves
    quake.clearOutput()
    os.remove(mndkfile)
    sys.exit(0)
    
    
