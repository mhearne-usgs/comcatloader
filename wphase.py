#!/usr/bin/env python

#stdlib imports
import sys
import datetime
import optparse
import os.path

TIMEFMT = '%Y-%m-%d %H:%M:%S'

#this should be a generator
def getEvents(args,startDate=None,endDate=None):
    fname = args[0]
    if not os.path.isfile(fname):
        raise Exception('File %s does not exist' % fname)
    
    f = open(fname,'rt')
    f.readline()
    lines = f.readlines()
    f.close()
    for line in lines:
        event = {}
        parts = line.strip().split()
        event['id'] = parts[0]
        date = parts[1]
        time = parts[2]
        dtime = '%s %s' % (date,time)
        event['time'] = datetime.datetime.strptime(dtime,TIMEFMT)
        if startDate is not None:
            if event['time'] < startDate:
                continue
        if endDate is not None:
            if event['time'] > endDate:
                continue
        #parts[3] is the GCMT magnitude - we don't care about that here
        event['mag'] = float(parts[4])
        event['numchannels'] = int(parts[5])
        event['gap'] = float(parts[6])
        event['ts'] = float(parts[7])
        event['duration'] = float(parts[8]) * 2
        event['lat'] = float(parts[9])
        event['lon'] = float(parts[10])
        event['depth'] = float(parts[11])
        event['mrr'] = float(parts[12])/1.0e7 #convert these values from dyne-cm units to N-m
        event['mtt'] = float(parts[13])/1.0e7
        event['mpp'] = float(parts[14])/1.0e7
        event['mrt'] = float(parts[15])/1.0e7
        event['mrp'] = float(parts[16])/1.0e7
        event['mtp'] = float(parts[17])/1.0e7
        yield event

def main(args):
    if len(args) < 2:
        print 'You must enter a filename as the first argument'
        sys.exit(1)
    for event in getEvents(args[1:]):
        print event['time']

if __name__ == '__main__':
    main(sys.argv[0:])
