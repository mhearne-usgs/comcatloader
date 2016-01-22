#!/usr/bin/env python

#stdlib
import sys
from datetime import datetime
import os.path

#third party
import math
from neicio.tag import Tag

# write(16,43) nyr, nmon, nday, time, lat, lon, depth,
#      2  energy (Joules), 
#      2  istrk, idip, islip,
#      2  istrk2, idip2, islip2
# 43	format(1x, i4, 1x, i2, 1x, i2,1x,f9.2, 
#      2  1x, f6.2, 1x, f7.2, 1x, f5.0, 1x,e10.2,
#      2  2(1x,i4,1x,i3,1x,i4))

   # 79  2 28 212706.09  60.64 -141.59   18.   0.14E+16  255  12   85  255  12   85
   # 79  6  2  94758.70 -30.73  117.21    3.   0.49E+13  190  40   90  190  40   90
   # 80  6 29  72005.50  34.81  139.18   17.   0.48E+15  258  78  165  258  78  165
   # 80 10 10 122523.50  36.19    1.35   15.   0.21E+15  240  60   90  240  60   90
   # 81 10 25  32215.50  18.05 -102.08   19.   0.79E+15  286  20   82  286  20   82
   # 82  1  9 125351.70  46.98  -66.57    6.   0.27E+13  195  65   70  195  65   70
   # 82  1 11 214108.00  46.97  -66.67    5.   0.30E+13  340  45   75  340  45   75
   # 82 12 13  91248.00  14.70   44.38    7.   0.48E+14  340  60  -60  340  60  -60
   # 83  4  3  25001.10   8.72  -83.12   25.   0.77E+15  300  30   93  300  30   93
   # 83  5  2 234247.70  36.22 -120.32   10.   0.16E+15  300  80   80  300  80   80

   
TIMEFMT = '%Y%m%d%H%M%S'
TIMEFMT2 = '%Y-%m-%dT%H:%M:%S.%f'
CREATIONTIMEFMT = '%Y-%m-%dT%H:%M:%S.%fZ'

def getOriginTag(etime,lat,lon,depth,pdedep):
    oatts = {'catalog:dataid':'choy%s' % etime.strftime(TIMEFMT),
             'catalog:datasource':'us',
             'catalog:eventid':etime.strftime(TIMEFMT),
             'catalog:eventsource':'choy',
             'publicID':'choy%s' % etime.strftime(TIMEFMT)}
    origintag = Tag('origin',attributes=oatts)

    #time
    timetag = Tag('time')
    timevaluetag = Tag('value',data=etime.strftime(TIMEFMT2)[0:22]+'Z')
    timetag.addChild(timevaluetag)

    #lat
    lattag = Tag('latitude')
    latvaluetag = Tag('value',data='%.4f' % lat)
    lattag.addChild(latvaluetag)

    #lon
    lontag = Tag('longitude')
    lonvaluetag = Tag('value',data='%.4f' % lon)
    lontag.addChild(lonvaluetag)

    #depth
    if depth == 999:
        depth = pdedep
        depthtypetag = Tag('depthType',data='from location')
        ocomment = """A broadband depth could not be determined for this earthquake.  A depth obtained from the PDE is used instead."""
    else:
        depthtypetag = Tag('depthType',data='from modeling of broad-band P waveforms')
        ocomment = """Broadband depths using Choy, G. L. and J.W. Dewey, Rupture process of an extended earthquake sequence: Teleseismic analysis of the Chilean earthquake of 3 March 1985, J. Geophys. Res.,93, 1103-111, 1988."""
        
        
    depthtag = Tag('depth')
    depthvaluetag = Tag('value',data='%i' % (depth*1000))
    depthtag.addChild(depthvaluetag)

    commenttag = Tag('comment',data=ocomment)
    creationtag = getCreationTag()

    evaltag = Tag('evaluationStatus',data='reviewed')
    modetag = Tag('evaluationMode',data='manual')
    
    origintag.addChild(timetag)
    origintag.addChild(lattag)
    origintag.addChild(lontag)
    origintag.addChild(depthtag)
    origintag.addChild(depthtypetag)
    origintag.addChild(commenttag)
    origintag.addChild(creationtag)
    origintag.addChild(evaltag)
    origintag.addChild(modetag)

    return origintag

def getMagTag(energy,emag,etime):
    #magnitude
    matts = {'catalog:dataid':'choy%s' % etime.strftime(TIMEFMT),
             'catalog:datasource':'us',
             'catalog:eventsource':'choy',
             'publicID':'choy%s' % etime.strftime(TIMEFMT)}
    magtag = Tag('magnitude',attributes=matts)
    magvtag = Tag('mag')
    magvaluetag = Tag('value',data = '%.2f' % emag)
    magvtag.addChild(magvaluetag)
    magtypetag = Tag('type',data='Me')
    energytag = Tag('energy',data='%.2g' % energy)
    ecomment = """The (radiated) energy field units are in Joules.  Radiated energy using Boatwright, J. and G. Choy, Teleseismic estimates of the energy radiated by shallow earthquakes, J. Geophys. Res., 91, 2095-2112, 1986. Energy magnitude using eq. 6 Choy, G. L. and J. Boatwright, Global patterns of radiated seismic energy and apparent stress, J. Geophys. Res., 100, 18205-18228, 1995."""
    magcommenttag = Tag('comment',data=ecomment)

    creationtag = getCreationTag()
    
    magtag.addChild(magvtag)
    magtag.addChild(magtypetag)
    magtag.addChild(magcommenttag)
    magtag.addChild(energytag)
    magtag.addChild(creationtag)

    return magtag

def getFocalTag(np1,np2,etime):
    #focal mechanism
    focaltag = Tag('focalMechanism',attributes={'publicID':'choy%s' % etime.strftime(TIMEFMT)})
    nodaltag = Tag('nodalPlanes')

    #plane 1
    plane1tag = Tag('nodalPlane1')
    strike1tag = Tag('strike')
    strike1valuetag = Tag('value',data='%i' % np1['strike'])
    strike1tag.addChild(strike1valuetag)
    dip1tag = Tag('dip')
    dip1valuetag = Tag('value',data='%i' % np1['dip'])
    dip1tag.addChild(dip1valuetag)
    rake1tag = Tag('rake')
    rake1valuetag = Tag('value',data='%i' % np1['rake'])
    rake1tag.addChild(rake1valuetag)
    plane1tag.addChild(strike1tag)
    plane1tag.addChild(dip1tag)
    plane1tag.addChild(rake1tag)

    #plane 2
    plane2tag = Tag('nodalPlane2')
    strike2tag = Tag('strike')
    strike2valuetag = Tag('value',data='%i' % np2['strike'])
    strike2tag.addChild(strike2valuetag)
    dip2tag = Tag('dip')
    dip2valuetag = Tag('value',data='%i' % np2['dip'])
    dip2tag.addChild(dip2valuetag)
    rake2tag = Tag('rake')
    rake2valuetag = Tag('value',data='%i' % np2['rake'])
    rake2tag.addChild(rake2valuetag)
    plane2tag.addChild(strike2tag)
    plane2tag.addChild(dip2tag)
    plane2tag.addChild(rake2tag)

    nodaltag.addChild(plane1tag)
    nodaltag.addChild(plane2tag)

    creationtag = getCreationTag()
    
    focaltag.addChild(nodaltag)
    focaltag.addChild(creationtag)

    return focaltag

def getQuakeTag(etime,lat,lon,depth,energy,np1,np2,pdedep):
    emag = (2.0/3.0) * (math.log10(energy) - 4.4)
    atts = {'xmlns:q':'http://quakeml.org/xmlns/quakeml/1.2',
            'xmlns:catalog':'http://anss.org/xmlns/catalog/0.1',
            'xmlns:tensor':'http://anss.org/xmlns/tensor/0.1'}
    quaketag = Tag('q:quakeml',attributes=atts)
    patts = {'xmlns':'http://quakeml.org/xmlns/bed/1.2',
             'publicID':'quakeml:us.anss.org/eventparameters/10002l37/1435063121'}
    paramtag = Tag('eventParameters',attributes=patts)
    eatts = {'catalog:dataid':'choy%s' % etime.strftime(TIMEFMT),
             'catalog:datasource':'us',
             'catalog:eventid':etime.strftime(TIMEFMT),
             'catalog:eventsource':'choy',
             'publicID':'choy%s' % etime.strftime(TIMEFMT)}
    eventtag = Tag('event',attributes=eatts)
    preforigin = Tag('preferredOriginID',data='choy%s' % etime.strftime(TIMEFMT))
    prefmag = Tag('preferredMagnitudeID',data='choy%s' % etime.strftime(TIMEFMT))

    origintag = getOriginTag(etime,lat,lon,depth,pdedep)

    magtag = getMagTag(energy,emag,etime)

    focaltag = getFocalTag(np1,np2,etime)

    eventtag.addChild(preforigin)
    eventtag.addChild(prefmag)
    eventtag.addChild(origintag)
    eventtag.addChild(magtag)
    eventtag.addChild(focaltag)

    eventcreationtag = getCreationTag()
    eventtag.addChild(eventcreationtag)

    paramcreationtag = getCreationTag()
    paramtag.addChild(eventtag)
    paramtag.addChild(paramcreationtag)
    quaketag.addChild(paramtag)

    return quaketag

def getCreationTag():
    ctag = Tag('creationInfo')
    atag = Tag('agencyID',data='us')
    ttag = Tag('creationTime',data=datetime.utcnow().strftime(CREATIONTIMEFMT))
    ctag.addChild(atag)
    ctag.addChild(ttag)
    return ctag

def main(catfile,outfolder):
    if not os.path.isdir(outfolder):
        os.makedirs(outfolder)
    f = open(catfile,'rt')
    hdrline = f.readline()
    lines = f.readlines()
    for line in lines:
        line = line.strip()
        parts = line.split(',')
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        plen = len(parts[3])
        if plen < 9:
            parts[3] = '0'*(9-plen)+parts[3]
        hour = int(parts[3][0:2])
        minute = int(parts[3][2:4])
        try:
            second = int(parts[3][4:6])
        except:
            pass
        if second == 60:
            second -= 1
        msec = int(float(parts[3][6:9])*1e6)
        etime = datetime(year,month,day,hour,minute,second,msec)
        lat = float(parts[4])
        lon = float(parts[5])
        depth = float(parts[6])
        energy = float(parts[7])
        np1 = {'strike':int(parts[8]),'dip':int(parts[9]),'rake':int(parts[10])}
        np2 = {'strike':int(parts[11]),'dip':int(parts[12]),'rake':int(parts[13])}
        pdedep = 0
        if len(parts[14]):
            pdedep = float(parts[14])
            
        quaketag = getQuakeTag(etime,lat,lon,depth,energy,np1,np2,pdedep)
        outfile = os.path.join(outfolder,'choy%s.xml' % (etime.strftime(TIMEFMT)))
        print 'Rendering %s' % outfile
        linestr = quaketag.renderTag(0)
        lines = linestr.split('\n')
        newlinestr = ''
        for line in lines:
            newlinestr += line.strip()
        f = open(outfile,'wt')
        f.write(newlinestr)
        f.close()
    f.close()

if __name__ == '__main__':
    datafile = sys.argv[1]
    outfolder = sys.argv[2]
    main(datafile,outfolder)    
