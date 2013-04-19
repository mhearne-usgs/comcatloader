#!/usr/bin/env python

#stdlib imports
import sys
import os.path
import datetime
import optparse
import importlib

#local imports
import quakeml

TIMEFMT = '%Y-%m-%d %H:%M:%S'
DEFAULT_START = datetime.datetime(1000,1,1)
DEFAULT_END = datetime.datetime(3000,1,1)

def getSummary(event,origins,oidx):
    fmt = '%s M%.1f (%.4f,%.4f) %.1f km'
    tpl = (event['time'].strftime('%Y-%m-%d %H:%M:%S'),event['mag'],event['lat'],event['lon'],event['depth'])
    eventdesc = fmt % tpl
    summary = ''
    if not len(origins):
        summary = 'No ComCat origins were associated with event %s' % eventdesc
        return summary
    if oidx > -1:
        summary += 'Event %s was associated with event %i:\n' % (eventdesc,oidx+1)
        i = 1
        for o in origins:
            if o['mag'] is None:
                o['mag'] = 0.0
            fmt = '\t%i) %s M%.1f (%.4f,%.4f) %.1f km (%.1f seconds, %.1f km distance)\n'
            if o.has_key('triggerlat'):
                tpl = (i,o['triggertime'].strftime('%Y-%m-%d %H:%M:%S'),o['mag'],o['triggerlat'],o['triggerlon'],
                       o['triggerdepth'],o['timedelta'],o['distance'])
            else:
                tpl = (i,o['time'].strftime('%Y-%m-%d %H:%M:%S'),o['mag'],o['lat'],o['lon'],o['depth'],
                       o['timedelta'],o['distance'])
            summary += fmt % tpl
            i += 1
        return summary
    if oidx == -1:
        summary += 'Event %s was associated with NONE of the following events:\n' % (eventdesc)
        i = 1
        for o in origins:
            fmt = '\t%i) %s M%.1f (%.4f,%.4f) %.1f km (%.1f seconds, %.1f km distance)'
            if o.has_key('triggerlat'):
                tpl = (i,o['triggertime'].strftime('%Y-%m-%d %H:%M:%S'),o['mag'],o['triggerlat'],o['triggerlon'],
                       o['triggerdepth'],o['timedelta'],o['distance'])
            else:
                tpl = (i,o['time'].strftime('%Y-%m-%d %H:%M:%S'),o['mag'],o['lat'],o['lon'],o['depth'],
                       o['timedelta'],o['distance'])
            summary += fmt % tpl
            i += 1
        return summary
        
def processEvent(quake,event,origins,events,numevents,ievent):
    filename = None
    norg = len(origins)
    nevents = len(events)
    eventdesc = '%s: %s M%.1f (%.4f,%.4f)' % (event['id'],str(event['time']),event['mag'],event['lat'],event['lon'])
    ofmt = '\t%i) %s M%.1f (%.4f,%.4f) %.1f km - %.1f km distance, %i seconds'
    oidx = -1
    if norg == 1:
        quake.renderXML(event,origins[0])
        print 'Writing event %s to file (%i of %i).' % (eventdesc,ievent,numevents)
    if norg == 0:
        if quake.type == quakeml.ORIGIN:
            filename = quake.renderXML(event)
            print 'No events associated with %s - rendering origin to XML' % eventdesc
        else:
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
            if mag is None:
                mag = 0.0
            lat = origin['lat']
            lon = origin['lon']
            depth = origin['depth']
            timedelta = origin['timedelta']
            distance = origin['distance']
            tpl = (ic,time,mag,lat,lon,depth,distance,timedelta)
            try:
                print ofmt % tpl
            except:
                pass
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
                filename = quake.renderXML(event,origins[oidx])
                output_origin = origins[oidx].copy()
            else:
                print 'Not associating event, as requested.'
        else:
            print "You obviously can't read.  Moving on."
    return (filename,oidx)

#this should be a generator
def getEvents():
    #yield event
    pass

def main(options,args):
    modulefile = args[0]
    if not os.path.isfile(modulefile):
        print 'Module file %s does not exist!'
        sys.exit(1)
    module = None
    mpath,mfile = os.path.split(modulefile)
    modname,modext = os.path.splitext(mfile)
    try:
        module = importlib.import_module(modname)
    except ImportError:
        print '%s does not appear to be a valid Python module.'
        sys.exit(1)
    if not module.__dict__.has_key('getEvents'):
        print '%s does not appear to have the required function getEvents().'
        sys.exit(1)
    twindow = 16
    dwindow = 100
    if options.timewindow is not None:
        twindow = int(options.timewindow)
    if options.distance is not None:
        dwindow = float(options.distance)
    author = 'neic'
    agency = 'us'
    source = quakeml.DEFAULT_SOURCE
    triggersource = None
    method = None
    ptype = 'origin'
    startdate = DEFAULT_START
    enddate = DEFAULT_END
    folder = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
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
    if options.beginDate is not None:
        try:
            startdate = datetime.datetime.strptime(options.beginDate,'%Y%m%d')
        except:
            print 'Could not parse start date "%s"' % options.beginDate
            sys.exit(1)
    if options.endDate is not None:
        try:
            enddate = datetime.datetime.strptime(options.endDate,'%Y%m%d')
        except:
            print 'Could not parse end date "%s"' % options.endDate
            sys.exit(1)
    if options.producttype is not None:
        types = [quakeml.ORIGIN,quakeml.FOCAL,quakeml.TENSOR]
        ptype = options.producttype
        if ptype not in types:
            print '%s not in %s.  Exiting.' % (ptype,','.join(types))
            sys.exit(1)
    quake = quakeml.QuakeML(ptype,folder,agency=agency,author=author,
                            triggersource=triggersource,source=source,
                            method=method,timewindow=twindow,distwindow=dwindow)
    if options.clear:
        resp = raw_input('You set the option to clear all existing QuakeML output.  Are you sure? Y/[n]')
        if resp.strip().lower() == 'y':
            quake.clearOutput()
        else:
            print 'Not clearing QuakeML output.'

    #parse the input data from file, database, webserver, whatever
    earliest = datetime.datetime(3000,1,1)
    latest = datetime.datetime(1,1,1)
    xmlfiles = []
    numevents = 0
    #the module getEvents() function doesn't have to do anything with the startDate and endDate parameters
    for event in module.getEvents(args[1:],startDate=startdate,endDate=enddate):
        if event['time'] < earliest:
            earliest = event['time']
        if event['time'] > latest:
            latest = event['time']
        xmlfile = os.path.join(quake.xmlfolder,'%s.xml' % event['id'])
        if os.path.isfile(xmlfile):
            xmlfiles.append(xmlfile)
            continue
        quake.add(event)
        numevents += 1
        
    numnear = len(quake.NearEventIndices)
    numprocessed = 0
    summary = [] #list of events that were not associated, or were associated manually
    for event,origins,events in quake.generateEvents():
        xmlfile,oidx = processEvent(quake,event,origins,events,numevents,numprocessed)
        if len(origins) != 1:
            summary.append(getSummary(event,origins,oidx))
        xmlfiles.append(xmlfile)
        numprocessed += 1

    if options.load:
        for xmlfile in xmlfiles:
            res,output = quake.push(xmlfile)
            if not res:
                p,fname = os.path.split(xmlfile)
                print 'Failed to send quakeML file %s. Error: "%s"' % (fname,output)

    if not len(summary):
        sys.exit(0)
    DAYFMT = '%Y-%m-%d'
    print
    print 'Summary for period %s to %s:' % (earliest.strftime(DAYFMT),latest.strftime(DAYFMT))
    for eventinfo in summary:
        print eventinfo
        print
        
        
if __name__ == '__main__':
    types = [quakeml.ORIGIN,quakeml.FOCAL,quakeml.TENSOR]
    usage = '''usage: %prog [options] modulefile arg2 ... argN'''
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
    parser.add_option("-l", "--load", dest="load",default=False,action="store_true",
                  help="Load catalog of created XML into ComCat")
    parser.add_option("-f", "--folder", dest="folder",
                  help="""Set folder for output QuakeML, appended to config output folder.  
    Defaults to current date/time""", metavar="FOLDER")
    parser.add_option("-b", "--beginDate", dest="beginDate",
                  help="""Specify starting date for loading from input catalog
    (YYYYMMDD) (defaults to 18000101)""",metavar="BEGINDATE")
    parser.add_option("-e", "--endDate", dest="endDate",
                  help="""Specify ending date for loading from input catalog
    (YYYYMMDD) (defaults to 30000101)""",metavar="ENDDATE")
    parser.add_option("-p", "--producttype", dest="producttype",
                  help="Define type of product (one of %s) (default to %s)" % (','.join(types),quakeml.ORIGIN), 
                  metavar="PRODUCTTYPE")
    parser.add_option("-c", "--clear",
                  action="store_true", dest="clear", default=False,
                  help="Clear XML output")
    

    (options, args) = parser.parse_args()
    if len(args) == 0:
        parser.print_help()
        sys.exit(0)
    main(options,args)
