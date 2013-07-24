#!/usr/bin/env python

#stdlib imports
import urllib,urllib2
import datetime
import math
import copy
import json
import os.path
import subprocess
import sys
import re
from xml.etree import ElementTree
import StringIO
from xml.dom import minidom
import glob
import optparse
import ConfigParser

#third party imports
import obspy.imaging.beachball
import numpy
import pytz

#local imports
from pagermap import distance
from pagerutil import timeutil

#module constants
ORIGIN = 'origin'
TENSOR = 'moment-tensor'
FOCAL = 'focal-mechanism'
TIMEFMT = '%Y-%m-%dT%H:%M:%SZ'
DEFAULT_MOMENT_METHOD = 'Mwc'
DEFAULT_SOURCE = 'us'
PRODUCT_TYPES = [ORIGIN,TENSOR,FOCAL]

#string formatting for all of the possible event parameters (for rendering in XML)
FORMATS = {'id':'%s',
           'lat':'%.4f',
           'lon':'%.4f',
           'depth':'%.1f',
           'mag':'%.1f',
           'time':TIMEFMT,#special case here...
           'mrr':'%.3e',
           'mtt':'%.3e',
           'mpp':'%.3e',
           'mtp':'%.3e',
           'mrp':'%.3e',
           'mrt':'%.3e',
           'np1strike':'%i',
           'np1dip':'%i',
           'np1rake':'%i',
           'np2strike':'%i',
           'np2dip':'%i',
           'np2rake':'%i',
           'triggertime':TIMEFMT,
           'triggerlat':'%.4f',
           'triggerlon':'%.4f',
           'triggerdepth':'%.1f',
           'triggerid':'%s',
           'moment':'%.2e',
           'tazimuth':'%i',
           'tplunge':'%i',
           'tvalue':'%.1e',
           'nazimuth':'%i',
           'nplunge':'%i',
           'nvalue':'%.1e',
           'pazimuth':'%i',
           'pplunge':'%i',
           'pvalue':'%.1e',
           'agency':'%s',
           'version':'%s',
           'method':'%s',
           'ctime':TIMEFMT,
           'source':'%s',
           'triggersource':'%s',
           'gap':'%.1f',
           'numchannels':'%i',
           'contributor':'%s',
           'catalog':'%s',
           'evalmode':'%s',
           'evalstatus':'%s',
           'nstations':'%i',
           'magcomment':'%s',
           }

MACROPATTERN = r'\[([^]]*)\]'

def getEventId(quakemlfile):
    dom = minidom.parse(quakemlfile)
    eventid = dom.getElementsByTagName('event')[0].getAttribute('catalog:eventid')
    dom.unlink()
    return eventid

def getCommandOutput(cmd):
    """
    Internal method for calling external command.
    @param cmd: String command ('ls -l', etc.)
    @return: Two-element tuple containing a boolean indicating success or failure, 
    and the output from running the command.
    """
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                            )
    output,errors = proc.communicate()
    retcode = proc.returncode
    if retcode == 0:
        retcode = True
    else:
        retcode = False
    return (retcode,output,errors)

def getEuclidean(lat1,lon1,time1,lat2,lon2,time2,dwindow=100.0,twindow=16.0):
    dd = distance.sdist(lat1,lon1,lat2,lon2)/1000.0
    normd = dd/dwindow
    if time2 > time1:
        dt = time2-time1
    else:
        dt = time1-time2
    nsecs = dt.days*86400 + dt.seconds
    normt = nsecs/twindow
    euclid = numpy.sqrt(normd**2 + normt**2)
    return (euclid,dd,nsecs)

def parseTime(milliseconds):
    seconds = milliseconds/1000
    microseconds = int((milliseconds/1000.0 - seconds)*1e6)
    etime = datetime.datetime.utcfromtimestamp(seconds)
    etime = etime + datetime.timedelta(0,0,microseconds)
    return etime

def calculateMagnitude(moment):
    #Calculate moment magnitude from scalar moment in units of ????
    magnitude = (2./3.)*(math.log10(moment)-9.1)
    magnitude = round(magnitude*10)/10.0
    return magnitude

def getMomentTensorAngles(event):
    keylist = ['mrr','mtt','mpp','mrt','mrp','mtp']
    keys = set(keylist)
    ekeys = set(event.keys())
    if not keys.issubset(ekeys):
        raise Exception,'Not all of the keys %s are found in event.' % ','.join(keylist)
    mrr = event['mrr']
    mtt = event['mtt']
    mpp = event['mpp']
    mrt = event['mrt']
    mrp = event['mrp']
    mtp = event['mtp']
    mt = obspy.imaging.beachball.MomentTensor(mrr,mtt,mpp,mrt,mrp,mtp,1)
    axes = obspy.imaging.beachball.MT2Axes(mt) #T, N and P
    plane1 = obspy.imaging.beachball.MT2Plane(mt)
    plane2 = obspy.imaging.beachball.AuxPlane(plane1.strike,plane1.dip,plane1.rake)
    event['tazimuth'] = axes[0].strike
    event['tplunge'] = axes[0].dip
    event['tvalue'] = axes[0].val
    event['nazimuth'] = axes[1].strike
    event['nplunge'] = axes[1].dip
    event['nvalue'] = axes[1].val
    event['pazimuth'] = axes[2].strike
    event['pplunge'] = axes[2].dip
    event['pvalue'] = axes[2].val
    event['np1strike'] = plane1.strike
    event['np1dip'] = plane1.dip
    event['np1rake'] = plane1.rake
    event['np2strike'] = plane2[0]
    event['np2dip'] = plane2[1]
    event['np2rake'] = plane2[2]
    return event
    
def calculateTotalMoment(mrr,mtt,mpp,mrt,mrp,mtp):
    wm1 = mrr**2 + mtt**2 + mpp**2
    wm2 = wm1+2.0*(mrt**2 + mrp**2 + mtp**2)
    moment = numpy.sqrt((wm2/2.0))
    return moment

def calculateDoubleCoupleMoment(eigenvalues):
    #takes a sequence of eigen values (T,N,P)
    eigenvalues = sorted(eigenvalues,reverse=True)
    if eigenvalues[1] == 0:
        return eigenvalues[0]
    else:
        return (eigenvalues[0] - eigenvalues[2])/2.0

def findMacros(xmltext):
    pattern = MACROPATTERN
    macros = re.findall(pattern,xmltext)
    umacros = []
    for macro in macros:
        if macro not in umacros:
            umacros.append(macro)
    return umacros

class QuakeML(object):
    REQMTFIELDS = ['id','lat','lon','depth','time',
                   'mrr','mtt','mpp','mtp','mrp','mrt']
    REQFMFIELDS = ['id','lat','lon','depth','mag','time',
                   'np1strike','np1dip','np1rake',
                   'np1strike','np1dip','np1rake']
    REQORFIELDS = ['id','lat','lon','depth','magnitude','time']
    SEARCHURL = 'http://ehpd-earthquake.cr.usgs.gov/earthquakes/jffeed/v1.0/nearby.php?'
    #2013-04-01T18:11:53Z
    TIMEFMT = '%Y-%m-%dT%H:%M:%S'
    KM2DEG = 1.0/111.191
    def __init__(self,type,xmlfolder,distwindow=100,timewindow=16,source='us',method=DEFAULT_MOMENT_METHOD,
                 catalog=None,triggersource=None,contributor='us'):

        self.DistanceWindow = distwindow
        self.TimeWindow = timewindow
        #look for template xml files where this code lives
        homedir = os.path.dirname(os.path.abspath(__file__)) #where is this script?
        originfile = os.path.join(homedir,'origin_template.xml')
        momentfile = os.path.join(homedir,'moment_template.xml')
        focalfile = os.path.join(homedir,'focal_template.xml')
        magfile = os.path.join(homedir,'magnitude_template.xml')
        flist = [originfile,momentfile,focalfile,magfile]
        if not os.path.isfile(originfile) or not os.path.isfile(momentfile) or not os.path.isfile(focalfile) or not os.path.isfile(magfile):
            raise IOError,"Could not find one or more of the following template files: %s" % (','.join(flist))
        if type == ORIGIN:
            self.type = 'origin'
            self.xml = open(originfile,'rt').read()
            self.magxml = open(magfile,'rt').read()
        elif type == TENSOR:
            self.type = 'moment'
            self.xml = open(momentfile,'rt').read()
            self.magxml = open(magfile,'rt').read()
        elif type == FOCAL:
            self.type = 'focal'
            self.xml = open(focalfile,'rt').read()
            self.magxml = open(magfile,'rt').read()
        else:
            raise IOError,"Unsupported product type '%s'" % type

        #load a config file
        configfile = os.path.join(homedir,'config.ini')
        if not os.path.isfile(configfile):
            raise Exception('Config file config.ini not found in %s.' % (homedir))
        self.config = ConfigParser.RawConfigParser()
        self.config.read(configfile)
        
        self.EventList = []
        self.NearEventIndices = [] #list of tuples of indices of events that are closer than timethresh/distthresh from each other
        self.Lat = []
        self.Lon = []
        self.Time = []
        self.catalog = catalog
        self.source = source
        self.method = method
        self.contributor = contributor
        self.triggersource = triggersource
        self.xmlfolder = os.path.join(self.config.get('OUTPUT','folder'),xmlfolder)
        isfolder = os.path.isdir(self.xmlfolder)
        if not isfolder:
            try:
                os.makedirs(self.xmlfolder)
            except Exception,expobj:
                raise 'Could not create directory "%s"'

    def push(self,quakemlfile,trumpWeight=None):
        MCMD = 'java -jar [PDLFOLDER]/ProductClient.jar --mainclass=gov.usgs.earthquake.eids.EIDSInputWedge --parser=gov.usgs.earthquake.eids.QuakemlProductCreator --configFile=[PDLFOLDER]/[CONFIGFILE] --privateKey=[PDLFOLDER]/[KEYFILE] --file=[QUAKEMLFILE]'
        TCMD = 'java -jar [PDLFOLDER]/ProductClient.jar --send --configFile=[PDLFOLDER]/[CONFIGFILE] --privateKey=[PDLFOLDER]/[KEYFILE] --source=us --code=[ID] --property-weight=[WEIGHT] --link-product=urn:usgs-product:[CONTRIBUTOR]:origin:[CATALOG][ID]:[VERSION]'

        pdlfolder = self.config.get('PDL','folder')
        pdlkey = self.config.get('PDL','keyfile')
        pdlconfig = self.config.get('PDL','configfile')
        cmd = MCMD.replace('[PDLFOLDER]',pdlfolder)
        cmd = cmd.replace('[CONFIGFILE]',pdlconfig)
        cmd = cmd.replace('[KEYFILE]',pdlkey)
        cmd = cmd.replace('[QUAKEMLFILE]',quakemlfile)
        res,output,errors = getCommandOutput(cmd)

        #if the user wants to send a trump message, detect that by trumpWeight not None
        if trumpWeight is not None:
            tcmd = TCMD.replace('[PDLFOLDER]',pdlfolder)
            tcmd = tcmd.replace('[CONFIGFILE]',pdlconfig)
            tcmd = tcmd.replace('[KEYFILE]',pdlkey)
            tcmd = tcmd.replace('[CONTRIBUTOR]',self.contributor)
            tcmd = tcmd.replace('[CATALOG]',self.catalog)
            eid = getEventId(quakemlfile)#this is sort of a hack, but it's the easiest way to get the ID for the event
            tcmd = tcmd.replace('[ID]',eid)
            tcmd = tcmd.replace('[WEIGHT]',trumpWeight)
            res1,output1,errors1 = getCommandOutput(cmd)
            if not res1:
                res = res1
                output = output1
                errors = errors1
        return (res,output,errors)
            
    def getRequiredKeys(self):
        if self.type == 'origin':
            reqfields = set(self.REQORFIELDS)
        elif self.type == 'focal':
            reqfields = set(self.REQFMFIELDS)
        elif self.type == 'moment':
            reqfields = set(self.REQMTFIELDS)
        else:
            pass
        return reqfields 

    def getOptionalKeys(self):
        macros = findMacros(self.xml)
        keys = []
        for macro in macros:
            keys.append(re.sub('\[\]','',macro.lower()))
        rkeys = self.getRequiredKeys()
        keys = list(set(keys).difference(set(rkeys)))
        return keys
            
    def clearOutput(self):
        xmlfiles = glob.glob(os.path.join(self.xmlfolder,'*.xml'))
        for xmlfile in xmlfiles:
            if xmlfile.find('template') > -1:
                continue
            os.remove(xmlfile)
        return

    def clear(self):
        self.EventList = []
        self.Lat = []
        self.Lon = []
        self.Time = []
        self.NearEventIndices = []
        return

    def hasAngles(self,eqdict):
        reqfields = ['tazimuth','tplunge','tvalue',
        'nazimuth','nplunge','nvalue',
        'pazimuth','pplunge','pvalue',
        'np1strike','np1dip','np1rake',
        'np2strike','np2dip','np2rake']
        for field in reqfields:
            if not eqdict.has_key(field):
                return False
        return True
        
    def add(self,eqdict):
        eqfields = eqdict.keys()
        seteqfields = set(eqfields)
        if self.type == 'origin':
            reqfields = set(self.REQORFIELDS)
        elif self.type == 'focal':
            reqfields = set(self.REQFMFIELDS)
        elif self.type == 'moment':
            reqfields = set(self.REQMTFIELDS)
        issub = reqfields.issubset(seteqfields)
        if not issub:
            missing = reqfields.difference(seteqfields)
            raise Exception,'Missing required fields "%s" from input dictionary' % (','.join(list(missing)))

        #add in the fields that apply to the whole catalog we are loading
        eqdict['source'] = self.source
        if not eqdict.has_key('method'):
            eqdict['method'] = self.method
        eqdict['catalog'] = self.catalog #this may be None
        eqdict['triggersource'] = self.triggersource
        eqdict['contributor'] = self.contributor
        
        if self.type == 'moment' and not self.hasAngles(eqdict):
            eqdict = getMomentTensorAngles(eqdict)
        if self.type == 'moment' and not eqdict.has_key('moment'):
            mrr = eqdict['mrr']
            mtt = eqdict['mtt']
            mpp = eqdict['mpp']
            mrt = eqdict['mrt']
            mrp = eqdict['mrp']
            mtp = eqdict['mtp']
            eqdict['moment'] = calculateTotalMoment(mrr,mtt,mpp,mrt,mrp,mtp)
            mag = calculateMagnitude(eqdict['moment'])
        if not eqdict.has_key('magnitude') and self.type != 'origin':
            eqdict['magnitude'] = calculateMagnitude(eqdict['moment'])
        
        self.EventList.append(eqdict)
        self.updateCloseEvents()
        

    def updateCloseEvents(self):
        thiseq = self.EventList[-1]
        time = float(thiseq['time'].strftime('%s'))
        lat = thiseq['lat']
        lon = thiseq['lon']
        if not len(self.Lat):
            self.Lat.append(lat)
            self.Lon.append(lon)
            self.Time.append(time)
            return
        nplat = numpy.array(self.Lat)
        nplon = numpy.array(self.Lon)
        nptime = numpy.array(self.Time)
        normdist = (distance.sdist(lat,lon,nplat,nplon)/1000)/self.DistanceWindow
        normtdelta = (numpy.abs(time - nptime))/self.TimeWindow
        eucdistance = numpy.sqrt(normdist**2+normtdelta**2)
        iclose = numpy.where(eucdistance <= numpy.sqrt(2))
        thisidx = len(self.Lat)
        near = []
        for idx in iclose[0]:
            self.NearEventIndices.append((idx,thisidx))
        self.Lat.append(lat)
        self.Lon.append(lon)
        self.Time.append(time)
        return

    def associate2(self,event):
        if event.has_key('triggerlat'):
            lat = event['triggerlat']
            lon = event['triggerlon']
            etime = event['triggertime']
        else:
            lat = event['lat']
            lon = event['lon']
            etime = event['time']
        APITIMEFMT = '%Y-%m-%dT%H:%M:%S.%f'
        mintime = etime - datetime.timedelta(seconds=self.TimeWindow)
        maxtime = etime + datetime.timedelta(seconds=self.TimeWindow)
        minlat = lat - self.DistanceWindow * self.KM2DEG
        maxlat = lat + self.DistanceWindow * self.KM2DEG
        minlon = lon - self.DistanceWindow * self.KM2DEG * (1/distance.cosd(lat))
        maxlon = lon + self.DistanceWindow * self.KM2DEG * (1/distance.cosd(lat))

        #handle meridian crossing problem
        # if minlon < 180 and maxlon > 180:
        #     maxlon = 360-maxlon
        # if minlon < -180 and maxlon > -180:
        #     minlon = 360 + minlon
        
        etimestr = etime.strftime(self.TIMEFMT)+'Z'
        searchurl = 'http://comcat.cr.usgs.gov/fdsnws/event/1/query?%s'
        #searchurl = 'http://comcat.cr.usgs.gov/earthquakes/feed/search.php?%s'
        pdict = {'minlatitude':minlat,'minlongitude':minlon,
                 'maxlatitude':maxlat,'maxlongitude':maxlon,
                 'starttime':mintime.strftime(APITIMEFMT),'endtime':maxtime.strftime(APITIMEFMT),
                 'catalog':self.triggersource,'format':'geojson','eventtype':'earthquake'}
        if self.triggersource == "":
            pdict.pop('catalog')
        params = urllib.urlencode(pdict)
        searchurl = searchurl % params
        if etime.year >= 2006:
            pass
        origins = []
        try:
            fh = urllib2.urlopen(searchurl)
            data = fh.read()
            #data2 = data[len(pdict['callback'])+1:-2]
            datadict = json.loads(data)['features']
            for feature in datadict:
                eventdict = {}
                eventdict['lon'] = feature['geometry']['coordinates'][0]
                eventdict['lat'] = feature['geometry']['coordinates'][1]
                eventdict['depth'] = feature['geometry']['coordinates'][2]
                eventdict['mag'] = feature['properties']['mag']
                otime = int(feature['properties']['time'])
                eventdict['time'] = parseTime(otime)
                idlist = feature['properties']['ids'].strip(',').split(',')
                eventdict['id'] = idlist[0]
                euclid,ddist,tdist = getEuclidean(lat,lon,etime,eventdict['lat'],eventdict['lon'],eventdict['time'])
                eventdict['euclidean'] = euclid
                eventdict['timedelta'] = tdist
                eventdict['distance'] = ddist
                origins.append(eventdict.copy())
            fh.close()
            origins = sorted(origins,key=lambda origin: origin['euclidean'])
            return origins
        except Exception,exception_object:
            raise exception_object,'Could not reach "%s"' % searchurl
        
    def associate(self,event):
        lat = event['lat']
        lon = event['lon']
        etime = event['time']
        etimestr = etime.strftime(self.TIMEFMT)+'Z'
        searchurl = self.SEARCHURL + '%s'
        pdict = {'action':'search','latitude':lat,'longitude':lon,'time':etimestr,
                 'eventSource':self.triggersource}
        params = urllib.urlencode(pdict)
        searchurl = searchurl % params
        origins = []
        try:
            fh = urllib2.urlopen(searchurl)
            data = fh.read()
            jsondata = json.loads(data)
            for feature in jsondata['features']:
                eventdict = {}
                eventdict['lon'] = feature['geometry']['coordinates'][0]
                eventdict['lat'] = feature['geometry']['coordinates'][1]
                eventdict['depth'] = feature['geometry']['coordinates'][2]
                eventdict['mag'] = feature['properties']['mag']
                eventdict['time'] = parseTime(int(feature['properties']['time']))
                eventdict['id'] = feature['properties']['ids'].split(',')[0]
                eventdict['distance'] = getEuclidean(lat,lon,etime,eventdict['lat'],eventdict['lon'],eventdict['time'])
                origins.append(event.copy())
            fh.close()
            origins = sorted(origins,key=lambda origin: origin['distance'])
            return origins
        except Exception,exception_object:
            raise exception_object,'Could not reach "%s"' % searchurl

    def renderXML(self,event,origin=None):
        event['ctime'] = datetime.datetime.utcnow()
        event['version'] = event['ctime'].strftime('%s')

        #treat magnitude field specially - it is possible with origins to have
        #multiple magnitudes input - we have a separate magnitude template file
        #that we fill in with each group of magnitude information
        magtext = ''
        for magdict in event['magnitude']:
            tmptext = self.magxml
            for key in magdict.keys():
                if key not in FORMATS.keys():
                    continue
                macro = '[%s]' % key.upper()
                value = FORMATS[key] % magdict[key]
                tmptext = tmptext.replace(macro,value)
            magtext += tmptext
        
        if origin is not None:
            event['triggertime'] = origin['time']
            event['triggerlon'] = origin['lon']
            event['triggerlat'] = origin['lat']
            event['triggerdepth'] = origin['depth']
            event['triggerid'] = origin['id']
                
        xmltext = self.xml
        xmltext = xmltext.replace('[MAGNITUDES]',magtext)
        
        for key in event.keys():
            if key not in FORMATS.keys():
                continue
            macro = '[%s]' % key.upper()
            value = event[key]
            if isinstance(value,datetime.datetime):
                value = value.strftime(TIMEFMT)
            else:
                try:
                    value = FORMATS[key] % value #use our pre-approved list of 
                except:
                    pass
            xmltext = xmltext.replace(macro,value)


        #get the preferred magnitude ID from the xml we just made
        prefmethod = event['magnitude'][0]['method']
        try:
            dom = minidom.parseString(xmltext)
            mags = dom.getElementsByTagName('magnitude')
            prefid = None
            for mag in mags:
                pid = mag.getAttribute('publicID')
                if pid.lower().endswith((prefmethod.lower())):
                    prefid = pid
                    break
            dom.unlink()
        except:
            open('debug.xml','wt').write(xmltext)
            sys.exit(1)
        #now put it into the xml
        xmltext = xmltext.replace('[PREFMAGID]',prefid)
        #get rid of any fields that weren't filled in by the catalog module
        xmltext = self.removeUnusedMacros(xmltext)

        #strip out all newline characters
        xmltext = xmltext.replace('\n','')
        xmltext = xmltext.replace('\t','')
        
        filename = os.path.join(self.xmlfolder,'%s.xml' % event['id'])
        f = open(filename,'wt')
        f.write(xmltext)
        f.close()
        return filename

    def removeUnusedMacros(self,xmltext):
        #ElementTree seems to want to parse from a file, so fake it with StringIO
        xmlio = StringIO.StringIO()
        xmlio.write(xmltext)
        xmlio.seek(0)
        tree = ElementTree.parse(xmlio)
        xmlio.close()
        #make a map of the parent-child relationships
        #the child elements are the keys, the parents are the values
        parent_map = dict((c, p) for p in tree.getiterator() for c in p)
        root = tree.getroot()
        trashcan = []
        for element in root.iter():
            for key,value in element.items():
                matchlist = re.findall(MACROPATTERN,value)
                if len(matchlist):
                    trashcan.append(element)
            tagdata = element.text
            if re.search(MACROPATTERN,tagdata) is not None:
                trashcan.append(element)
        for trash in trashcan:
            #print 'Removing unfilled element %s' % str(element)
            parent = parent_map[trash]
            try:
                parent.remove(trash)
            except Exception,e:
                pass
        f = StringIO.StringIO()
        tree.write(f,xml_declaration=False,default_namespace='')
        xmloutput = f.getvalue()
        f.close()

        #There are a bunch of things that ElementTree does to the XML, all having to do with namespaces.
        #What follows is some hacky search/replace code to undo the changes
        #I don't want the "nsX" namespace identifiers in here - nuking them with a regular expression
        pattern = 'ns[0-9]*:'
        xmloutput = re.sub(pattern,'',xmloutput)
        
        #there are three namespace defining attributes in the q:quakeml element.  ElementTree blows these away.
        #let's just replace everything in the <quakeml> opening tag with the right stuff...
        m1 = re.search('<quakeml',xmloutput)
        m2 = re.compile('>').search(xmloutput,m1.start())
        repltext = """<q:quakeml xmlns="http://quakeml.org/xmlns/bed/1.2" xmlns:catalog="http://anss.org/xmlns/catalog/0.1" xmlns:q="http://quakeml.org/xmlns/quakeml/1.2">"""
        xmloutput = xmloutput.replace(xmloutput[m1.start():m2.end()],repltext)

        #ElementTree took away the "q:" namespace qualifier, so let's put it back
        xmloutput = xmloutput.replace('<quakeml','<q:quakeml')
        xmloutput = xmloutput.replace('</quakeml','</q:quakeml')

        #The catalog: namespace qualifiers in the event tag are gone too, so lets fix that
        xmloutput = xmloutput.replace('eventid','catalog:eventid')
        xmloutput = xmloutput.replace('eventsource','catalog:eventsource')
        xmloutput = xmloutput.replace('datasource','catalog:datasource')
        
        return xmloutput

    def generateEvents(self):
        i = 0
        while i < len(self.EventList):
            event = self.EventList[i]
            events = [] #will contain list of events that are "near" this event
            origins = []
            if self.type == 'focal' or self.type == 'moment':
                origins = self.associate2(event)
                for otuple in self.NearEventIndices:
                    if i in otuple:
                        events.append(copy.deepcopy(self.EventList[otuple[0]]))
            yield (event,origins,events)
            i += 1

if __name__ == '__main__':
    usage = "usage: %prog [options] product-type"
    parser = optparse.OptionParser(usage=usage)

    parser.add_option("-g", "--get-types",action="store_true", 
                      dest="getTypes", default=False,help="List supported product types")
    parser.add_option("-r", "--get-required-keys",action="store_true", 
                      dest="getRequiredKeys", default=False,help="List required keys for given product type")
    parser.add_option("-o", "--get-optional-keys",action="store_true", 
                      dest="getOptionalKeys", default=False,help="List optional keys for given product type")
    (options, args) = parser.parse_args()
    if options.getTypes:
        for t in PRODUCT_TYPES:
            print t
        sys.exit(0)

    if len(args) == 0:
        print 'Either submit a product type and an option, or -g for getTypes'
        sys.exit(1)
    if args[0] not in PRODUCT_TYPES:
        print 'Product type %s not in %s' % (args[0],','.join(PRODUCT_TYPES))
        sys.exit(1)
    if options.getRequiredKeys:
        quake = QuakeML(args[0],os.getcwd())
        for key in quake.getRequiredKeys():
            print key
        sys.exit(0)
    if options.getOptionalKeys:
        quake = QuakeML(args[0],os.getcwd())
        for key in quake.getOptionalKeys():
            print key
        sys.exit(0)
