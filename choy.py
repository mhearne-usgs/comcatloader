#!/usr/bin/env python

#stdlib imports
import datetime
import pytz
import math
import copy
import json
import os.path
import subprocess
import sys
import urllib,urllib2

TIMEFMT = '%Y-%m-%dT%H:%M:%S.%f'

def getEvents(args,startDate=None,endDate=None):
    if startDate is None:
        startDate = datetime.datetime(1800,1,1)
    if endDate is None:
        endDate = datetime.utcnow()
    fname = args[0]
    if not os.path.isfile(fname):
        raise Exception('File %s does not exist' % fname)
    
    f = open(fname,'rt')
    f.readline()
    lines = f.readlines()
    f.close()
    for line in lines:
        event = {}
        line = line.strip()
        datestr = line[0:8]
        year = int(datestr[0:4])
        month = int(datestr[4:6])
        day = int(datestr[6:8])
        line = line[9:]
        timestr = line[0:9]
        try:
            hour = int(timestr[0:2])
        except:
            hour = 0
        try:
            minute = int(timestr[2:4])
        except:
            minute = 0
        try:
            second = int(timestr[4:6])
        except:
            second = 0
        microsecond = int(int(timestr[7:9])*1e4) #multiplying hundredths of a second by 10000
        time = datetime.datetime(year,month,day,hour,minute,second,microsecond)
        if time < startDate or time > endDate:
            continue
        line = line[10:]
        parts = line.split()
        event = {}
        event['time'] = time
        event['id'] = time.strftime('%Y%m%d%H%M%S')
        event['lat'] = float(parts[0])
        event['lon'] = float(parts[1])
        event['depth'] = float(parts[2])
        event['np1strike'] = float(parts[3])
        event['np1dip'] = float(parts[4])
        event['np1rake'] = float(parts[5])
        event['np2strike'] = float(parts[6])
        event['np2dip'] = float(parts[7])
        event['np2rake'] = float(parts[8])
        event['energy'] = float(parts[9])
        me = (2.0/3.0) * (math.log10(event['energy']) - 4.4)
        mag = {'mag':round(me*10.0)/10.0,'method':'Me','evalstatus':'reviewed','evalmode':'manual'}
        event['magnitude'] = [mag]
        yield event

if __name__ == '__main__':
    main()
    
