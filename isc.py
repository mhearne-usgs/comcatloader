#!/usr/bin/env python

import datetime

#1900-07-29 06:59:00.00
TIMEFMT = '%Y-%m-%d %H:%M:%S.%f'

def getEvents(args,startDate=None,endDate=None):
    f = open(args[0],'rt')
    lines = f.readlines()
    f.close()
    for line in lines:
        if line.strip().startswith('#'):
            continue
        parts = line.split(',')
        eqdict = {}
        timestr = parts[0].strip()
        eqdict['time'] = datetime.datetime.strptime(timestr,TIMEFMT)
        if eqdict['time'] < startDate or eqdict['time'] > endDate:
            continue
        eqdict['lat'] = float(parts[1])
        eqdict['lon'] = float(parts[2])
        try:
            eqdict['smajax'] = float(parts[3])
            
        except:
            eqdict['smajax'] = float('nan')

        try:
            eqdict['sminax'] = float(parts[4])
        except:
            eqdict['sminax'] = float('nan')

        try:       
            eqdict['strike'] = float(parts[5])
        except:
            eqdict['strike'] = float('nan')
                
        eqdict['locquality'] = parts[6].strip()
        eqdict['depth'] = float(parts[7])*1000
        eqdict['deptherror'] = float(parts[8])
        eqdict['depthquality'] = parts[9]
        mag = {'mag':float(parts[10]),'method':'Mw','evalstatus':'reviewed','evalmode':'manual'}
        eqdict['magnitude'] = [mag]
        eqdict['magerror'] = float(parts[11])
        eqdict['magquality'] = parts[12].strip()
        eqdict['id'] = parts[23].strip()
        yield eqdict
