#!/usr/bin/env python

#stdlib imports
import sys
import os.path
from datetime import datetime,timedelta
import re
import socket
import string
import argparse
import textwrap
import math
from collections import OrderedDict
import urllib2
import json


#local imports
from neicio.tag import Tag

CWBHOST = 'cwbpub.cr.usgs.gov'
CWBPORT = 2052

MINMAG = 4.0

URLBASE = 'http://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=[START]&endtime=[END]&latitude=[LAT]&longitude=[LON]&maxradiuskm=[RAD]'
RADIUS = 10 #km around an epicenter to search for matching earthquake
TIMEDELTA = 3 #seconds around an origin time to search for matching earthquake

SOURCE = 'rde'

TIMERROR = 5 #how many days can the phase time be from a given station epoch before we don't consider it to be part of that epoch 

TIMEFMT = '%Y-%m-%dT%H:%M:%S'
USAGE = {'+':1,'x':0,'-':0}
DEPTHTYPES = {'c':'operator assigned',
              'd':'constrained by depth phases',
              'e':'other',
              'f':'other',
              'l':'constrained by direct phases',
              'm':'from location',
              'n':'constrained by direct phases',
              'r':'from location',
              'u':'other',
              'w':'from moment tensor inversion'}

class StationTranslator(object):
    def __init__(self,dictionaryfile=None):
        self.stationdict = {}
        if dictionaryfile is not None:
            f = open(dictionaryfile,'rt')
            for line in f.readlines():
                key,value = line.split('=')
                self.stationdict[key.strip()] = value.strip()
            f.close()
            

    def save(self,dictfile):
        f = open(dictfile,'wt')
        for key,value in self.stationdict.iteritems():
            f.write('%s = %s\n' % (key.strip(),value.strip()))
        f.close()

    def callCWBServer(self,req):
        response = ''
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM,0)
            s.connect((CWBHOST,CWBPORT))
            s.send(req)
            while True:
                tresp = s.recv(10241)
                response += tresp
                if response.find('<EOR>') > -1:
                    break


            s.close()
        except Exception,msg:
            try:
                time.sleep(2)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM,0)
                s.connect((CWBHOST,CWBPORT))
                s.send(req)
                response = s.recv(10241)
                s.close()
            except:
                pass
        return response
        
    def getStationEpoch(self,station,phasetime):
        req = '-c c -s ..%s -b all \n' % station
        pad = chr(0) * (80 - len(req))
        req = str(req + pad)
        response = self.callCWBServer(req)
        lines = response.split('\n')
        epochs = []
        for line in lines:
            parts = line.split()
            if len(parts) < 9:
                continue
            datestr1 = parts[10]
            timestr1 = parts[11]+':00'
            datestr2 = parts[13]
            timestr2 = parts[14]+':00'
            t1 = datetime.strptime(datestr1 + ' ' + timestr1,'%Y-%m-%d %H:%M:%S')
            t2 = datetime.strptime(datestr2 + ' ' + timestr2,'%Y-%m-%d %H:%M:%S')
            epochs.append((t1,t2))
        etime = None
        for epoch in epochs:
            t1,t2 = epoch
            if phasetime > t1 - timedelta(seconds=86400*TIMERROR) and phasetime < t2 + timedelta(seconds=86400*TIMERROR):
                dt = t2-t1
                nseconds = dt.days*86400 + dt.seconds
                etime = t1 + timedelta(seconds=nseconds/2)
                if etime > datetime.utcnow():
                    etime = phasetime
                else:
                    pass
                break
        return etime

    def getIR(self,station):
        req = '-b all -a *.*.%s -c c \n' % station
        pad = chr(0) * (80 - len(req))
        req = str(req + pad)
        response = self.callCWBServer(req)
        lines = response.split('\n')
        nscl = station
        for line in lines:
            parts = line.split(':')
            if len(parts) < 2:
                continue
            f,d,s,n = parts[0].split('.')
            if f.lower() not in ['isc','iris']:
                continue
            nscl = '%s.%s..' % (d,s)
            break
        return nscl
    
    def getFSDN(self,station):
        req = '-c c -a FDSN.IR.%s -c c \n' % station
        pad = chr(0) * (80 - len(req))
        req = str(req + pad)
        response = self.callCWBServer(req)
        lines = response.split('\n')
        fsdn = station
        for line in lines:
            parts = line.split(':')
            if len(parts) < 2:
                continue
            parts = parts[0].split('.')
            if len(parts) < 2:
                continue
            if parts[2] != station:
                continue
            fsdn = '%s.%s..' % (parts[1],parts[2])
            break
        return fsdn
    
    def getNSCL(self,station,phasetype,phasetime):
        stationkey = station+'-'+phasetype[0:1]
        if self.stationdict.has_key(stationkey):
            #sys.stderr.write('Using cached station key %s\n' % stationkey)
            return self.stationdict[stationkey]
        
        dt = timedelta(seconds=86400)
        preferred = station
        epoch = self.getStationEpoch(station,phasetime) #get a date where valid metadata is available
        if epoch is not None:
            timestr = (epoch+dt).strftime('%Y/%m/%d')
            okchannels = ['HH','BH','SH','HN']
            scode = '..%s' % (station)
            req = '-c c -s %s -b %s \n' % (scode,timestr)
            pad = chr(0) * (80 - len(req))
            req = str(req + pad)
            response = self.callCWBServer(req)
            lines = response.split('\n')
            if response.find('no channels found to match') > -1:
                preferred = station
                lines = []
        else:
            lines = []
        nscl_list = []
        for line in lines:
            parts = line.split(':')
            if len(parts) < 2:
                continue
            net,sta,loc,channel = parts[0].split()
            if sta.lower() != station.lower():
                continue
            if channel[0:2] not in okchannels:
                continue
            if phasetype.lower().startswith('p') and not channel.lower().endswith('z'):
                continue
            if phasetype.lower().startswith('s') and re.search('[1|2|E|N]$',channel) is None:
                continue
            nscl = '%s.%s.%s.%s' % (net,sta,channel,loc)
            nscl_list.append(nscl)

        for nscl in nscl_list:
            net,sta,channel,loc = nscl.split('.')
            if channel.lower().startswith('hh'):
                preferred = nscl
                break
            if channel.lower().startswith('bh'):
                preferred = nscl
                break
            if channel.lower().startswith('sh'):
                preferred = nscl
                break
            if channel.lower().startswith('hn'):
                preferred = nscl
                break
        if preferred == station:
            preferred = self.getFSDN(station)
        if preferred == station:
            preferred = self.getIR(station)
        self.stationdict[stationkey] = preferred
        return preferred

def getPrefMag(event):
    url = URLBASE.replace('[RAD]','%i' % RADIUS)
    url = url.replace('[LAT]','%.4f' % event['lat'])
    url = url.replace('[LON]','%.4f' % event['lon'])
    stime = event['time'] - timedelta(seconds=TIMEDELTA)
    etime = event['time'] + timedelta(seconds=TIMEDELTA)
    url = url.replace('[START]','%s' % stime.strftime(TIMEFMT))
    url = url.replace('[END]','%s' % etime.strftime(TIMEFMT))
    try:
        fh = urllib2.urlopen(url)
    except:
        pass
    data = fh.read()
    fh.close()
    jdict = json.loads(data)
    if not jdict.has_key('features') or len(jdict['features']) > 1 or len(jdict['features']) == 0:
        #raise Exception,'No or multiple events found for %s M%.1f' % (event['time'],event['magnitude'])
        print 'No event matching %s M%.1f' % (event['time'],event['magnitude'][0]['magnitude'])
        return None
    try:
        pevent = jdict['features'][0]
    except:
        pass
    etime = datetime.utcfromtimestamp(pevent['properties']['time']/1000)
    elon,elat,edep = pevent['geometry']['coordinates']
    emag = pevent['properties']['mag']
    prefmag = emag
    return prefmag
    
def readLayerLine(event,line):
    depth,vp,vs = [float(p) for p in line[1:].strip().split()]
    if event.has_key('layer'):
        event['layer'].append([depth,vp,vs])
    else:
        event['layer'] = [[depth,vp,vs]]
    return event

def readStationLine(event,line):
    parts = line[1:].strip().split()
    station = parts[0]
    lat,lon,elev = [float(p) for p in parts[1:4]]
    if event.has_key('stations'):
        event['stations'].append({'id':station,'lat':lat,'lon':lon,'elev':elev})
    else:
        event['stations'] = [{'id':station,'lat':lat,'lon':lon,'elev':elev}]

    return event
    
def readCommentLine(event,line):
    com = line[1:].strip()
    if event.has_key('comment'):
        event['comment'] += ' '+com
    else:
        event['comment'] = ' '+com
    return event

def readHypoLine(event,line):
    parts = line[1:].strip().split()
    year = int(parts[0])
    month = int(parts[1])
    day = int(parts[2])
    hour = int(parts[3])
    minute = int(parts[4])
    second = float(parts[5])
    event['timeerror'] = float(parts[6])
    microsecond = int((second - int(second))*1e6)
    second = int(second) - 1
    if second == -1:
        second = 0
    event['time'] = datetime(year,month,day,hour,minute,second,microsecond)
    event['lat'] = float(parts[7])
    lon = float(parts[8])
    if lon > 180:
        lon -= 360
    event['lon'] = lon
    event['azimuth'] = int(parts[9])
    event['smajor'] = float(parts[10])
    event['sminor'] = float(parts[11])
    
    event['depth'] = float(parts[12])
    event['depthcode'] = parts[13]
    event['depthlower'] = float(parts[14])
    event['depthupper'] = float(parts[15])
    event['gtcu'] = parts[16]
    event['author'] = parts[17]
    event['clusterid'] = parts[18]
    return event

def readMagnitudeLine(event,line):
    parts = line[1:].split()
    mag = {}
    mag['magnitude'] = float(parts[0])
    magtype = parts[1]
    if magtype == 'UNK':
        magtype = 'ML'
    mag['magscale'] = magtype
    mag['magauthor'] = ' '.join(parts[2:])
    if event.has_key('magnitude'):
        event['magnitude'].append(mag)
    else:
        event['magnitude'] = [mag]
    return event

def readPhaseLine(event,line,st):
    #refactoring the phase list into a phase dictionary, to handle duplicate instances of station-phase pairs.
    #We wants the *second* instance of these, which requires that I keep a dictionary of phases instead of a 
    #list.  Grr.
    parts = line[1:].split()
    phase = {}
    phase['id'] = datetime.utcnow() #this will be used to link together picks and arrivals
    try:
        phase['usage'] = USAGE[parts[0]]
    except:
        pass
    station = parts[1]
    phase['name'] = parts[4]
    phase['distance'] = float(parts[2])
    phase['azimuth'] = int(parts[3])
    year = int(parts[5])
    month = int(parts[6])
    day = int(parts[7])
    hour = int(parts[8])
    minute = int(parts[9])
    second = float(parts[10])
    microsecond = int((second - int(second))*1e6)
    second = int(second) - 1 #assumption here is that input seconds are 1 to 60
    if second == -1: #sometimes seconds are 0 to 59, sometimes 1 to 60.  Not my problem.
        second = 0
    phase['time'] = datetime(year,month,day,hour,minute,second,microsecond)
    nscl_station = st.getNSCL(station,phase['name'],phase['time'])
    phase['sta'] = nscl_station
    if nscl_station == station:
        #print 'Could not find an NSCL name for %s.  Skipping.' % station
        print line.strip()
        return event
    phase['precision'] = int(parts[11])
    phase['residual'] = float(parts[12])
    phase['error'] = float(parts[13])
    phasekey = phase['sta']+'_'+phase['name']
    #if we have the phase already in the file, we'll replace it, which is easy.
    if event.has_key('phases'):
        event['phases'][phasekey] = phase.copy()
    else:
        event['phases'] = {phasekey:phase.copy()}
    return event

def createMagTag(event):
    prefmag = None
    for mag in event['magnitude']:
        if mag['magscale'].lower() == 'mw':
            prefmag = mag.copy()
            prefmag['magscale'] = 'Mw'
            break
        if mag['magscale'].lower() == 'mb':
            prefmag = mag.copy()
            break
        if mag['magscale'].lower() == 'ml':
            prefmag = mag.copy()
            break
        if mag['magscale'].lower() == 'mn':
            prefmag = mag.copy()
            break
        if mag['magscale'].lower() == 'md':
            prefmag = mag.copy()
            break
    if prefmag is None:
        raise Exception("No preferred magnitude scale for event %s" % event['id'])
    magtype = prefmag['magscale']
    magid = 'us_%s_%s' % (event['id'],magtype)
    magsource = prefmag['magauthor']
    #create the magnitude tag
    pubid = 'quakeml:us.anss.org/magnitude/%s/%s' % (event['id'],magtype)
    magnitudetag = Tag('magnitude',attributes = {'catalog:dataid':magid,
                                                 'catalog:datasource':magsource,
                                                 'publicID':pubid})
    #create all the pieces of the magnitude tag
    magvaluetag = Tag('value',data='%.1f' % prefmag['magnitude'])
    magtag = Tag('mag')
    magtag.addChild(magvaluetag)
    magtypetag = Tag('type',data=magtype)
    magcreationtag = Tag('creationInfo')
    magauthortag = Tag('author',data=prefmag['magauthor'])
    magcreationtag.addChild(magauthortag)

    #add the pieces to the magnitude tag
    magnitudetag.addChild(magtag)
    magnitudetag.addChild(magtypetag)
    magnitudetag.addChild(magcreationtag)

    return (magnitudetag,prefmag['magnitude'],pubid)

def createOriginTag(event,studyname):
    eventcode = event['id']
    catalog = SOURCE+studyname
    originid = 'quakeml:us.anss.org/origin/%s' % ('%s%s' % (catalog,event['id']))
    origintag = Tag('origin',attributes={'catalog:dataid':'%s%s' % (catalog,event['id']),
                                         'catalog:datasource':SOURCE,
                                         'catalog:eventid':'%s' % event['id'],
                                         'catalog:eventsource':catalog,
                                         'publicID':originid})

    #confidence ellipse
    uncertaintag = Tag('originUncertainty')
    atag = Tag('maxHorizontalUncertainty',data='%.2f' % (event['smajor']*1000))
    btag = Tag('minHorizontalUncertainty',data='%.2f' % (event['sminor']*1000))
    aztag = Tag('azimuthMaxHorizontalUncertainty',data='%.2f' % (event['azimuth']))
    uncertaintag.addChild(atag)
    uncertaintag.addChild(btag)
    uncertaintag.addChild(aztag)

    #time
    timetag = Tag('time')
    tvaluetag = Tag('value',data = event['time'].strftime(TIMEFMT))
    terrortag = Tag('uncertainty',data = '%.2f' % (event['timeerror']))
    timetag.addChild(tvaluetag)
    timetag.addChild(terrortag)

    #lat
    lattag = Tag('latitude')
    latvaluetag = Tag('value',data='%.4f' % (event['lat']))
    lattag.addChild(latvaluetag)

    #lon
    lontag = Tag('longitude')
    lonvaluetag = Tag('value',data='%.4f' % (event['lon']))
    lontag.addChild(lonvaluetag)

    #depth
    depthtag = Tag('depth')
    depthvaluetag = Tag('value',data='%i' % (int(event['depth']*1000)))
    depthlowertag = Tag('lowerUncertainty',data='%i' % (int(event['depthlower']*1000)))
    depthuppertag = Tag('upperUncertainty',data='%i' % (int(event['depthupper']*1000)))
    depthtypetag = Tag('depthType',data=DEPTHTYPES[event['depthcode']])
    depthtag.addChild(depthvaluetag)
    depthtag.addChild(depthlowertag)
    depthtag.addChild(depthuppertag)
    depthtag.addChild(depthtypetag)

    #quality
    stationlist = []
    nphases = 0
    azlist = []
    rmslist = []
    mindist = 999999999999
    for phasekey,phase in event['phases'].iteritems():
        if not phase['usage']:
            continue
        nphases += 1
        if phase['sta'] not in stationlist:
            stationlist.append(phase['sta'])
        rmslist.append(phase['residual'])
        if phase['distance'] < mindist:
            mindist = phase['distance']
        azlist.append(phase['azimuth'])

    azlist = sorted(azlist)
    resmean = sum(rmslist)/len(rmslist)
    sumsquares = sum([math.pow(xi - resmean,2) for xi in rmslist])
    stderr = math.sqrt(sumsquares/len(rmslist))
    gap = azlist[0] + 360.0 - azlist[-1]
    for i in range(1,len(azlist)):
        dt = azlist[i] - azlist[i-1]
        if dt > gap:
            gap = dt
    nstations = len(stationlist)
    qualitytag = Tag('quality')
    phasecounttag = Tag('usedPhaseCount',data = '%i' % nphases)
    stationcounttag = Tag('usedStationCount',data = '%i' % nstations)
    stderrtag = Tag('standardError',data = '%.2f' % stderr)
    gaptag = Tag('azimuthalGap',data = '%i' % int(gap))
    disttag = Tag('minimumDistance',data = '%.2f' % mindist)

    qualitytag.addChild(phasecounttag)
    qualitytag.addChild(stationcounttag)
    qualitytag.addChild(stderrtag)
    qualitytag.addChild(gaptag)
    qualitytag.addChild(disttag)

    #evaluation status and mode
    evaltag = Tag('evaluationStatus',data='reviewed')
    modetag = Tag('evaluationMode', data='manual')
    
    #creation info
    origincreationtag = Tag('creationInfo')
    originauthortag = Tag('author',data=event['author'])
    origincreationtag.addChild(originauthortag)

    #roll up the origin tag
    origintag.addChild(uncertaintag)
    origintag.addChild(timetag)
    origintag.addChild(lattag)
    origintag.addChild(lontag)
    origintag.addChild(depthtag)
    origintag.addChild(qualitytag)
    origintag.addChild(evaltag)
    origintag.addChild(modetag)
    origintag.addChild(origincreationtag)

    return (origintag,originid)

def createArrivalTag(phase,eventid):
    picktime = phase['id'].strftime('%s')+'.'+phase['id'].strftime('%f')
    arrid = 'quakeml:us.anss.org/arrival/%s/us_%s' % (eventid,picktime)
    arrivaltag = Tag('arrival',attributes={'publicID':arrid})
    pickid = 'quakeml:us.anss.org/pick/%s/us_%s' % (eventid,picktime)
    pickidtag = Tag('pickID',data=pickid)
    phasetag = Tag('phase',data=phase['name'])
    azimuthtag = Tag('azimuth',data='%.2f' % (phase['azimuth']))
    distancetag = Tag('distance',data='%.2f' % (phase['distance']))
    residualtag = Tag('timeResidual',data='%.2f' % (phase['residual']))
    weighttag = Tag('timeWeight',data='%.2f' % (phase['error']))

    
    arrivaltag.addChild(pickidtag)
    arrivaltag.addChild(phasetag)
    arrivaltag.addChild(azimuthtag)
    arrivaltag.addChild(distancetag)
    arrivaltag.addChild(residualtag)
    arrivaltag.addChild(weighttag)
    
    return arrivaltag

def createPickTag(phase,eventid):
    picktime = phase['id'].strftime('%s')+'.'+phase['id'].strftime('%f')
    pickid = 'quakeml:us.anss.org/pick/%s/us_%s' % (eventid,picktime)
    picktag = Tag('pick',attributes={'publicID':pickid})
    timetag = Tag('time')
    timevaluetag = Tag('value',data=phase['time'].strftime(TIMEFMT+'Z'))
    timetag.addChild(timevaluetag)
    network,station,channel,location = phase['sta'].split('.')
    attributes = {}
    if network.replace('-','').strip() != '':
        attributes['networkCode'] = network
    if station.replace('-','').strip() != '':
        attributes['stationCode'] = station
    if channel.replace('-','').strip() != '':
        attributes['channelCode'] = channel
    if location.replace('-','').strip() != '':
        attributes['locationCode'] = location
    wavetag = Tag('waveformID',attributes=attributes)
    hinttag = Tag('phaseHint',data=phase['name']) #duplicate of arrival->phase (??)
    evaltag = Tag('evaluationMode',data='manual')

    picktag.addChild(timetag)
    picktag.addChild(wavetag)
    picktag.addChild(hinttag)
    picktag.addChild(evaltag)
    return picktag

def createEventTag(event,studyname):
    quaketag = Tag('q:quakeml',attributes={'xmlns:q':'http://quakeml.org/xmlns/quakeml/1.2',
                                          'xmlns':'http://quakeml.org/xmlns/bed/1.2',
                                          'xmlns:catalog':'http://anss.org/xmlns/catalog/0.1',
                                          'xmlns:tensor':'http://anss.org/xmlns/tensor/0.1'})
    pubid = 'quakeml:us.anss.org/eventparameters/%s/%i' % (event['id'],int(datetime.utcnow().strftime('%s')))
    creationinfotag = Tag('creationInfo')
    agencyidtag = Tag('agencyID',data='us')
    creationtimetag = Tag('creationTime',data=datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')+'Z')
    creationinfotag.addChild(agencyidtag)
    creationinfotag.addChild(creationtimetag)
    paramtag = Tag('eventParameters',attributes={'xmlns':'http://quakeml.org/xmlns/bed/1.2',
                                                 'publicID':pubid})
    paramtag.addChild(creationinfotag)
    catalog = SOURCE+studyname
    eventtag = Tag('event',attributes={'catalog:dataid':'%s%s' % (catalog,event['id']),
                                       'catalog:datasource':SOURCE,
                                       'catalog:eventid':'%s' % event['id'],
                                       'catalog:eventsource':catalog})

    
    
    # commenttag = Tag('comment')
    # texttag = Tag('text',data=comment)
    # commenttag.addChild(texttag)
    # eventtag.addChild(commenttag)
    if event.has_key('magnitude'):
        magtag,prefmag,pubmagid = createMagTag(event)
    hypotag,originid = createOriginTag(event,studyname)
    preferredtag = Tag('preferredOriginID',data=originid)
    prefmagtag = Tag('preferredMagnitudeID',data=pubmagid)
    eventtag.addChild(preferredtag)
    eventtag.addChild(prefmagtag)

    for phasekey,phase in event['phases'].iteritems():
        arrivaltag = createArrivalTag(phase,event['id'])
        picktag = createPickTag(phase,event['id'])
        eventtag.addChild(picktag)
        hypotag.addChild(arrivaltag)

    #roll up eventtag
    if event.has_key('magnitude'):
        eventtag.addChild(magtag)
    eventtag.addChild(hypotag)

    #roll up eventParams tag
    paramtag.addChild(eventtag)

    #roll up quakeml tag
    quaketag.addChild(paramtag)

    return (quaketag,prefmag)

def main(args):
    qomfile = args.qomfile
    outfolder = args.outfolder

    if not os.path.isdir(outfolder):
        os.makedirs(outfolder)
    
    st = StationTranslator(dictionaryfile=args.dictionary)
    f = open(qomfile,'rt')
    events = []
    event = {}
    i = 1
    comment = ''
    nphases = 0
    phaselist = []
    
    for line in f.readlines():
        if line.startswith('L'):
            event = readLayerLine(event,line)
        if line.startswith('C'):
            event = readStationLine(event,line)
        if line.startswith('#'):
            comment += line.strip('#')
        if line.startswith('E'):
            event['id'] = '%08i' % i #ignore Eric's event ID fields
        if line.startswith('H'):
            event = readHypoLine(event,line)
        if line.startswith('M'):
            event = readMagnitudeLine(event,line)
        if line.startswith('P'):
            #sys.stderr.write('reading phase line %i ("%s")\n' % (nphases+1,line))
            nphases += 1
            event = readPhaseLine(event,line,st)
        if line.startswith('STOP'):
            events.append(event.copy())
            sys.stderr.write('Parsed event %i\n' % i)
            i += 1
            sys.stderr.flush()
            event = {}
    f.close()
    print 'Read %i events' % len(events)

    #try to find the best magnitude from comcat for the larger events
    for event in events:
        if event['magnitude'][0]['magnitude'] > MINMAG:
            prefmag = getPrefMag(event)
            if prefmag is not None:
                print 'For event %s, switching magnitude M%.1f to M%.1f' % (event['time'],event['magnitude'][0]['magnitude'],prefmag)
                event['magnitude'][0]['magnitude'] = prefmag
    
    dictfile = 'stationcodes.dat'
    print 'Saving dictionary of station codes to %s' % dictfile
    st.save(dictfile)
    
    #filter out non-ascii characters
    #comment = filter(lambda x: x in string.printable, comment)
    tmin = datetime(2500,1,1)
    tmax = datetime(1900,1,1)
    latmin = 95.0
    latmax = -95.0
    lonmin = 190000.0
    lonmax = -190000.0
    magmin = 10.1
    magmax = -0.1
    for event in events:
        etag,prefmag = createEventTag(event,args.studyname)
        
        if event['time'] < tmin:
            tmin = event['time']
        if event['time'] > tmax:
            tmax = event['time']
        if event['lat'] < latmin:
            latmin = event['lat']
        if event['lat'] > latmax:
            latmax = event['lat']
        if event['lon'] < lonmin:
            lonmin = event['lon']
        if event['lon'] > lonmax:
            lonmax = event['lon']
        if prefmag < magmin:
            magmin = prefmag
        if prefmag > magmax:
            magmax = prefmag
        
        fname = os.path.join(outfolder,SOURCE+event['id']+'.xml')
        #etag.renderToXML(fname)
        xmlstr = etag.renderTag(0)
        xmlstr = xmlstr.replace('\t','')
        xmlstr = xmlstr.replace('\n','')
        f = open(fname,'wt')
        f.write(xmlstr)
        f.close()

    # studyname = args.studyname
    # authors = args.authors.split(',')
    # desc = args.description
    # email = args.contactemail
    # name = args.contactname
    if args.pubid:
        pubid = args.pubid
    # print 
    # print 'Catalog Name: %s' % args.studyname
    # print 'Catalog Authors: %s' % ', '.join(args.authors.split(','))
    # print 'Point of Contact: %s, %s' % (args.contactname,args.contactemail)
    # print 'Short Description: %s' % (args.description)
    # print 'Time Span: %s to %s' % (tmin.strftime(TIMEFMT),tmax.strftime(TIMEFMT))
    # print 'Spatial Domain: Latitude %.4f to %.4f, Longitude %.4f to %.4f' % (latmin,latmax,lonmin,lonmax)
    # print 'Magnitude Range: %.1f to %.1f' % (magmin,magmax)
    # print 'Detailed Description:\n%s' % textwrap.fill(comment,80)
    
if __name__ == '__main__':
    desc = "Create QuakeML files and metadata output for an input RDE relocation cluster file"
    parser = argparse.ArgumentParser(description=desc,formatter_class=argparse.RawDescriptionHelpFormatter)
    #positional arguments
    parser.add_argument('qomfile', 
                        help='Input study data file')
    parser.add_argument('outfolder', 
                        help='Output folder where QuakeML files will be written')
    parser.add_argument('studyname', 
                        help='Short name of study (mineral2011) - will be prepended with rde and used as ComCat catalog name.')
    # parser.add_argument('authors', 
    #                     help='Comma separated list of authors (surround with quotes).')
    # parser.add_argument('description', 
    #                     help='One-line description of study.')
    # parser.add_argument('contactemail', 
    #                     help='Email of main point of contact.')
    # parser.add_argument('contactname', 
    #                     help='Name of main point of contact.')
    parser.add_argument('-p','--pubid', dest='pubid', 
                        help='(Optional) doi number.')
    parser.add_argument('-d','--dictionary', dest='dictionary', 
                        help='(Optional) File containing dictionary of station->NSCL codes.')
    pargs = parser.parse_args()
    main(pargs)
