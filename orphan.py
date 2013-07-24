#!/usr/bin/env python

#stdlib
import argparse
import urllib2,urllib
from datetime import datetime
import os.path
import json

#local
import quakeml

URLBASE = 'http://comcat.cr.usgs.gov/fdsnws/event/1/query?%s'
TIMEFMT = '%Y-%m-%d'
LONGTIMEFMT = '%Y-%m-%d %H:%M:%S'

def getEventStr(event):
    if event.has_key('timedelta'): #this is an origin
        fmt = '%30s,%s,%8.4f,%9.4f,%5.1f km,M%.1f,(%i seconds %.1f km)'
        tpl = (event['id'],event['time'].strftime(LONGTIMEFMT),
               event['lat'],event['lon'],event['depth'],
               event['mag'],event['timedelta'],event['distance'])
    else:
        fmt = '%30s,%s,%8.4f,%9.4f,%5.1f km, M%.1f,'
        tpl = (event['id'],event['time'].strftime(LONGTIMEFMT),
               event['lat'],event['lon'],event['depth'],
               event['mag'])
    eventstr = fmt % tpl
    return eventstr

def main(arguments):
    timewindow = None
    distwindow = None
    if arguments.timeWindow is not None:
        timewindow = arguments.timeWindow
    if arguments.distanceWindow is not None:
        distwindow = arguments.distanceWindow
    quake = quakeml.QuakeML('origin',os.getcwd(),catalog=arguments.catalog,
                            timewindow=timewindow,distwindow=distwindow,triggersource="")
    urlparams = {}
    urlparams['orderby'] = 'time-asc'
    urlparams['format'] = 'geojson'
    urlparams['minmagnitude'] = 5.5
    urlparams['format'] = 'geojson'
    urlparams['catalog'] = arguments.catalog
    starttime = datetime(1900,1,1)
    if arguments.startDate is not None:
        starttime = datetime.strptime(arguments.startDate,TIMEFMT)
    if arguments.endDate is not None:
        endtime = datetime.strptime(arguments.endDate,TIMEFMT)
    for year in range(starttime.year,endtime.year+1):
        urlparams['starttime'] = datetime(year,1,1,0,0,0)
        urlparams['endtime'] = datetime(year,12,31,23,59,59)
        params = urllib.urlencode(urlparams)
        url = URLBASE % params
        fh = urllib2.urlopen(url)
        feed_data = fh.read()
        fh.close()
        fdict = json.loads(feed_data)
        for feature in fdict['features']:
            lon,lat,depth = feature['geometry']['coordinates']
            eid = feature['id']
            mag = feature['properties']['mag']
            time = datetime.utcfromtimestamp(feature['properties']['time']/1000)
            event = {'lat':lat,'lon':lon,'time':time,'depth':depth,'id':eid,'mag':mag}
            eurl = feature['properties']['url']+'.json'
            fh = urllib2.urlopen(eurl)
            edata = fh.read()
            fh.close()
            edict = json.loads(edata)
            eventids = edict['summary']['properties']['eventids'].strip(',').split(',')
            if len(eventids) == 1 and eventids[0].startswith(arguments.catalog):
                eventstr = getEventStr(event)
                if arguments.doAssociate:
                    origins = quake.associate2(event)
                    hasother = [not origin['id'].startswith(arguments.catalog) for origin in origins]
                    if len(origins) and max(hasother) > 0:
                        fmt = '%s'
                        print fmt % (eventstr)
                    else:
                        fmt = '%s'
                        print fmt % (eventstr)
                    for origin in origins:
                        if origin['id'].startswith(arguments.catalog):
                            continue
                        ostr = getEventStr(origin)
                        print '%s' % ostr
                else:
                    print 'Event %s is unassociated.' % eventstr
                print
    

if __name__ == '__main__':
    usage = """Find all events from input catalog that are NOT associated with any other catalogs.
    Optionally, find possible events from other catalogs these orphans MIGHT be associated with.
    """
    cmdparser = argparse.ArgumentParser(usage=usage)
    cmdparser.add_argument('catalog', metavar='CATALOG', 
                           help='Catalog of events possibly containing orphans')
    cmdparser.add_argument("-s", "--startDate", dest="startDate",nargs='?',
                           help="""Start date for search""", metavar="STARTDATE")
    cmdparser.add_argument("-e", "--endDate", dest="endDate",nargs='?',
                           help="""End date for search""", metavar="ENDDATE")
    cmdparser.add_argument("-t", "--timeWindow", dest="timeWindow",nargs='?',type=int,
                           help="""Time window in seconds""", metavar="TIMEWINDOW")
    cmdparser.add_argument("-d", "--distanceWindow", dest="distanceWindow",nargs='?',type=int,
                           help="""Distance window in km""", metavar="DISTANCE")
    cmdparser.add_argument("-a", "--associate",
                           action="store_true", dest="doAssociate", default=False,
                           help="Return a list of possible associated events from other catalogs.")
    
    
    cmdargs = cmdparser.parse_args()
    main(cmdargs)
