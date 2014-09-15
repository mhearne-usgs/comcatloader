#!/usr/bin/env python

#stdlib imports
import sys
import os.path
from datetime import datetime

#local imports
from neicio.tag import Tag

TIMEFMT = '%Y-%m-%dT%H:%M:%S'
USAGE = {'+':'valid','x':'invalid'}
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
    event['lon'] = float(parts[8])
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
    event['magnitude'] = float(parts[0])
    event['magscale'] = parts[1]
    event['magauthor'] = parts[2:]
    return event

def readPhaseLine(event,line):
    parts = line[1:].split()
    phase = {}
    phase['id'] = datetime.utcnow() #this will be used to link together picks and arrivals
    phase['usage'] = USAGE[parts[0]]
    phase['sta'] = parts[1]
    phase['distance'] = float(parts[2])
    phase['azimuth'] = int(parts[3])
    phase['name'] = parts[4]
    year = int(parts[5])
    month = int(parts[6])
    day = int(parts[7])
    hour = int(parts[8])
    minute = int(parts[9])
    second = float(parts[10])
    microsecond = int((second - int(second))*1e6)
    second = int(second) - 1
    if second == -1: #sometimes seconds are 0 to 59, sometimes 1 to 60.  Not my problem.
        second = 0
    phase['time'] = datetime(year,month,day,hour,minute,second,microsecond)
    phase['precision'] = int(parts[11])
    phase['residual'] = float(parts[12])
    phase['error'] = float(parts[13])
    if event.has_key('phases'):
        event['phases'].append(phase.copy())
    else:
        event['phases'] = [phase.copy()]
    return event

def createMagTag(event):
    try:
        magtype = event['magscale']
    except:
        pass
    magid = 'us_%s_%s' % (event['id'],magtype)
    #create the magnitude tag
    magnitudetag = Tag('magnitude',attributes = {'catalog:dataid':magid,
                                                 'catalog:datasource':'us',
                                                 'publicID':'quakeml:us.anss.org/magnitude/%s/%s' % (event['id'],magtype)})
    #create all the pieces of the magnitude tag
    magvaluetag = Tag('value',data='%.1f' % 6.9)
    magtag = Tag('mag')
    magtag.addChild(magvaluetag)
    magtypetag = Tag('type',data=magtype)
    magcreationtag = Tag('creationInfo')
    magauthortag = Tag('author',data='magauthor')
    magcreationtag.addChild(magauthortag)

    #add the pieces to the magnitude tag
    magnitudetag.addChild(magtag)
    magnitudetag.addChild(magtypetag)
    magnitudetag.addChild(magcreationtag)

    return magnitudetag

def createOriginTag(event):
    eventcode = event['id']
    origintag = Tag('origin',attributes={'catalog:dataid':'us'+eventcode,
                                         'catalog:datasource':'us',
                                         'catalog:eventid':eventcode,
                                         'publicID':'quakeml:us.anss.org/origin/%s' % eventcode})
    #confidence ellipse
    ellipsetag = Tag('confidenceEllipsoid')
    atag = Tag('semiMajorAxisLength',data='%.2f' % (event['smajor']*1000))
    btag = Tag('semiMinorAxisLength',data='%.2f' % (event['sminor']*1000))
    aztag = Tag('majorAxisAzimuth',data='%.2f' % (event['azimuth']))
    ellipsetag.addChild(atag)
    ellipsetag.addChild(btag)
    ellipsetag.addChild(aztag)

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
    
    #creation info
    origincreationtag = Tag('creationInfo')
    originauthortag = Tag('author',data=event['author'])
    origincreationtag.addChild(originauthortag)

    #roll up the origin tag
    origintag.addChild(ellipsetag)
    origintag.addChild(timetag)
    origintag.addChild(lattag)
    origintag.addChild(lontag)
    origintag.addChild(depthtag)
    origintag.addChild(origincreationtag)

    return origintag

def createArrivalTag(phase,eventid):
    arrid = 'quakeml:us.anss.org/arrival/%s/us_%s' % (eventid,phase['id'].strftime('%s'))
    arrivaltag = Tag('arrival',attributes={'publicID':arrid})
    pickid = 'quakeml:us.anss.org/pick/%s/us_%s' % (eventid,phase['id'].strftime('%s'))
    pickidtag = Tag('pickID',data=pickid)
    phasetag = Tag('phase',data=phase['name'])
    azimuthtag = Tag('azimuth',data='%.2f' % (phase['azimuth']))
    distancetag = Tag('distance',data='%.2f' % (phase['distance']))
    residualtag = Tag('timeResidual',data='%.2f' % (phase['residual']))

    arrivaltag.addChild(pickidtag)
    arrivaltag.addChild(phasetag)
    arrivaltag.addChild(azimuthtag)
    arrivaltag.addChild(distancetag)
    arrivaltag.addChild(residualtag)

    return arrivaltag

def createPickTag(phase,eventid):
    pickid = 'quakeml:us.anss.org/pick/%s/us_%s' % (eventid,phase['id'].strftime('%s'))
    picktag = Tag('pick',attributes={'publicID':pickid})
    timetag = Tag('time')
    timevaluetag = Tag('value',data=phase['time'].strftime(TIMEFMT+'Z'))
    timetag.addChild(timevaluetag)
    wavetag = Tag('waveformID',attributes={'channelCode':'',
                                           'locationCode':'',
                                           'networkCode':'',
                                           'stationCode':phase['sta']})
    hinttag = Tag('phaseHint',data=phase['name']) #duplicate of arrival->phase (??)

    picktag.addChild(timetag)
    picktag.addChild(wavetag)
    picktag.addChild(hinttag)

    return picktag

def createEventTag(event):
    quaketag = Tag('q:quakeml',attributes={'xmlns:q':'http://quakeml.org/xmlns/quakeml/1.2',
                                          'xmlns':'http://quakeml.org/xmlns/bed/1.2',
                                          'xmlns:catalog':'http://anss.org/xmlns/catalog/0.1',
                                          'xmlns:tensor':'http://anss.org/xmlns/tensor/0.1'})
    pubid = 'quakeml:us.anss.org/eventparameters/%s/%i' % (event['id'],int(datetime.utcnow().strftime('%s')))
    paramtag = Tag('eventParameters',attributes={'xmlns':'http://quakeml.org/xmlns/bed/1.2',
                                                 'publicID':pubid})
    eventtag = Tag('event',attributes={'catalog:dataid':'us%s' % event['id'],
                                       'catalog:datasource':'us',
                                       'catalog:eventid':'%s' % event['id'],
                                       'catalog:eventsource':'us'})
    if event.has_key('magnitude'):
        magtag = createMagTag(event)
    hypotag = createOriginTag(event)

    for phase in event['phases']:
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

    return quaketag

def main(qomfile):
    f = open(qomfile,'rt')
    events = []
    event = {}
    for line in f.readlines():
        if line.startswith('L'):
            event = readLayerLine(event,line)
        if line.startswith('C'):
            event = readStationLine(event,line)
        if line.startswith('#'):
            event = readCommentLine(event,line)
        if line.startswith('E'):
            event['id'] = line[1:].strip()
        if line.startswith('H'):
            event = readHypoLine(event,line)
        if line.startswith('M'):
            event = readMagnitudeLine(event,line)
        if line.startswith('P'):
            event = readPhaseLine(event,line)
        if line.startswith('STOP'):
            events.append(event.copy())
            event = {}
    f.close()
    print 'Read %i events' % len(events)
    for event in events:
        etag = createEventTag(event)
        fname = event['id']+'.xml'
        #etag.renderToXML(fname)
        xmlstr = etag.renderTag(0)
        xmlstr = xmlstr.replace('\t','')
        xmlstr = xmlstr.replace('\n','')
        f = open(fname,'wt')
        f.write(xmlstr)
        f.close()
    
if __name__ == '__main__':
    qomfile = sys.argv[1]
    main(qomfile)
