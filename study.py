#!/usr/bin/env python

#stdlib
import datetime
import re
import sys
import csv

def getEvents(args,startDate=None,endDate=None):
    f = open(args[0],'rt')
    csvreader = csv.reader(f,dialect='excel')
    csvreader.next()
    for parts in csvreader:
        record = {}
        try:
            mstr,dstr,ystr = parts[0].split('/')
        except:
            continue
        year = int(ystr)
        month = int(mstr)
        day = int(dstr)
        if parts[1].strip() == '':
            hour = 0
            minute = 0
            second = 0
        else:
            hstr,mstr,sstr = parts[1].split(':')
            hour = int(hstr)
            minute = int(mstr)
            second = int(sstr)
        record['time'] = datetime.datetime(year,month,day,hour,minute,second)
        if record['time'] < datetime.datetime(1976,1,1):
            continue
        record['id'] = record['time'].strftime('%Y%m%d%H%M%S')
        if parts[3].strip() == '': #what are we supposed to do without location?
            continue
        record['lat'] = float(parts[3])
        record['lon'] = float(parts[4])
        record['depth'] = 0.0
        try:
            record['mag'] = float(re.findall('[0-9\.]*',parts[6])[0])
        except:
            pass
                
        yield record
    f.close()

if __name__ == '__main__':
    fname = sys.argv[1]
    for record in getEvents([fname]):
        print record['time'],record['mag']
