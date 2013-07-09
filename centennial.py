#!/usr/bin/env python

import datetime
import math

#1900-07-29 06:59:00.00
TIMEFMT = '%Y-%m-%d %H:%M:%S.%f'

AZGAP = {'':'Unknown azimuthal gap',
               'A':'Azimuthal gap less than 180 degrees',
               'B':'Azimuthal gap between 180 and 210 degrees',
               'C':'Azimuthal gap between 210 and 240 degrees',
               'D':'Azimuthal gap between 240 and 270 degrees',
               'F':'Azimuthal gap greater than 270 degrees',
               '':'Azimuthal gap less than 180 degrees',
               'Z':'Azimuthal gap greater than or equal to 180 degrees'}

#format
#ABE        1905  4 19  12 25  0.00  -32.000-171.000   0.0 179   0 6.8 Ms AN2   0.0          0.0          0.0          0.0          0.0          0.0          0.0
#---- SCHL  1905  7 23   2 46 12.00   49.300  94.900   0.0 333   0 8.5 Mw SCHL  7.7 Ms AN2   8.2 mB ABE1  8.2 UK G&R   8.7 UK PAS   0.0          0.0          0.0

def getEvents(args,startDate=None,endDate=None):
    f = open(args[0],'rt')
    lines = f.readlines()
    f.close()
    eqdict = {}
    for line in lines:
        eqdict = {}
        line = line.strip()
        eqdict['icat'] = line[0:6].strip()
        eqdict['asol'] = line[5].strip()
        
        eqdict['isol'] = line[7:11].strip()
        year = int(line[11:15])
        #fortran 2i3
        month = int(line[15:18].strip())
        day = int(line[18:21].strip())
        #fortran 2i3
        hour = int(line[22:25].strip())
        minute = int(line[25:28].strip())
        #fortran f6.2
        second = float(line[28:34].strip())
        millisecond = int((second - math.floor(second))*1e6)
        second = int(math.floor(second))

        #at least one event appears to have undefined values for day,hour,min
        if day == 0:
            day = 1
        if hour == 0:
            hour = 1
        if minute == 0:
            minute = 1
            
        eqdict['time'] = datetime.datetime(year,month,day,hour,minute,second,millisecond)
        #filter out events outside time window
        if eqdict['time'] < startDate or eqdict['time'] > endDate:
            continue
        
        if eqdict['asol'] in AZGAP.keys():
            eqdict['magcomment'] = AZGAP[eqdict['asol']]
        else:
            eqdict['magcomment'] = 'Unknown azimuthal gap'
        eqdict['id'] = eqdict['time'].strftime('%Y%m%d%H%M%S')

        
        
        #fortran 2f8.3
        eqdict['lat'] = float(line[35:43].strip())
        eqdict['lon'] = float(line[43:51].strip())

        #f6.1
        eqdict['depth'] = float(line[51:57].strip())*1000

        #2i4
        eqdict['fereg'] = int(line[57:61].strip())
        
        eqdict['nstations'] = int(line[61:65].strip())
    
        #there can be as many as 8 (?) contributed magnitudes - let's get them all
        #f4.1
        maglist = []
        startidx = 65
        for ic in range(0,2):
            magdict = {}
            magdict['mag'] = float(line[startidx:startidx+4].strip())
            if magdict['mag'] == 0:
                break
            magdict['method'] = line[startidx+5:startidx+7].strip()
            if magdict['method'].lower() != 'ms' and ic > 0:
                break
            magdict['evalstatus'] = 'final'
            magdict['evalmode'] = 'manual'
            maglist.append(magdict.copy())
            startidx += 13
        eqdict['magnitude'] = maglist

        #a2
        try:
            eqdict['method'] = line[70:72].strip()
        except:
            pass    

        #a5
        eqdict['source'] = line[72:77].strip()

        #tell PDL what the evaluation mode/status are
        eqdict['evalmode'] = 'manual'
        eqdict['evalstatus'] = 'reviewed'
        yield eqdict
