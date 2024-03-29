#coding:utf-8
"""
Module for using DataCore REST API
"""
from __future__ import unicode_literals
import sys

def msg_error_import(module_name):
    print("Need '{}' module, you have to install it".format(module_name))
    print("Run 'pip install {}'".format(module_name))
    sys.exit(1)

try:
    import logging
except:
    msg_error_import("logging")
try:
    import configparser
except:
    msg_error_import("configparser")
try:
    import requests
except:
    msg_error_import("requests")
try:
    import json
except:
    msg_error_import("json")
try:
    from concurrent.futures import ThreadPoolExecutor
except:
    msg_error_import("futures")
try:
    from concurrent.futures import ProcessPoolExecutor
except:
    msg_error_import("concurrent")
try:
    import time
except:
    msg_error_import("time")



# Read config file
config = configparser.ConfigParser()
try:
    config.read('./datacore_get_perf.ini')
except:
    print("Config file (datacore_get_perf.ini) not found")
    sys.exit(1)

# Enable logging
if config['LOGGING'].getboolean('log'):
    logging.basicConfig(filename=config['LOGGING']['logfile'],
                        format='%(asctime)s - %(message)s',
                        level=logging.INFO)
else:
    logging.basicConfig(format='%(asctime)s - %(message)s')

# Construct rest url and headers
url = "http://{}/RestService/rest.svc/1.0".format(config['SERVERS']['rest_server'])
headers = {'ServerHost': config['SERVERS']['datacore_server'],
           'Authorization': 'Basic {} {}'.format(config['CREDENTIALS']['user'],
                                                 config['CREDENTIALS']['passwd'])}




# lambdas

dcs_b2g = lambda value:value/1024/1024/1024 # Convert Bytes to GigaBytes

#dcs_request_perf = lambda value:requests.get('{}/performance/{}'.format(url,value), headers=headers) # request perf from dcs_object Id


# fuctions

def print_cool(msg):
    msg = "  " + msg + "  "
    print("".center(80,"#"))
    print(msg.center(80,"#"))
    print("".center(80,"#"))
    print("\n")

def dcs_monitorid_to_str(i):
    """
    Helper that convert a monitor state int to a str.
    """
    if i == 1:
        return "Undefined"
    elif i == 2:
        return "Healthy"
    elif i == 4:
        return "Attention"
    elif i == 8:
        return "Warning"
    elif i == 16:
        return "Critical"
    else:
        return "Undefined"



def dcs_get_object(dcs_object):
    """
    Get DataCore Object (ex: servers, virtualdisks...)
    """
    logging.info('Begin to query the REST server at {}'.format(config['SERVERS']['rest_server']))
    
    try:
        r = requests.get('{}/{}'.format(url,dcs_object), headers=headers)
    except:
        logging.error("Something wrong during connection")
        sys.exit(1)
    else:
        logging.info("Querying {}".format(dcs_object))
        tmp = r.json()
        result = []
        try:
            err = tmp["ErrorCode"]
        except:
            logging.info("No Rest ErrorCode")
        else:
            logging.error(tmp["Message"])
            sys.exit(1)
        if dcs_object == "servers":
            for item in tmp:
                test = str(item["RegionNodeId"])
                if str(test) != "None":
                    item["dcs_resource"] = dcs_object
                    result.append(item)
                else:
                    logging.info("Exception: Partner server: " +item["Caption"])
            return result
        elif dcs_object == "ports":      
            for item in tmp:
                if "Microsoft iSCSI" in item["Caption"] or "Loop" in item["Caption"]:
                    test = 1
                else:
                    item["dcs_resource"] = dcs_object
                    result.append(item)
            return result
        elif dcs_object == "physicaldisks":
            for item in tmp:
                if item["Type"] == 4:
                    item["dcs_resource"] = dcs_object
                    result.append(item)
            return result
        else:
            for item in tmp:
                item["dcs_resource"] = dcs_object
                result.append(item)
            return result



def dcs_request_perf(dcs_object):
    res = requests.get('{}/performance/{}'.format(url,dcs_object["Id"]), headers=headers)
    logging.info("Querying perf for {}".format(dcs_object["Caption"]))
    dcs_object["Performances"] = res.json()[0]
    return dcs_object

def dcs_get_perf(dcs_objects):
    """
    Get DataCore Objects performances (ex: servers, virtualdisks...)
    """

    logging.info('Begin to query the REST server for perf at {}'.format(config['SERVERS']['rest_server']))

    result = []
    with ProcessPoolExecutor() as executor:
        for  dcs_perf in zip(dcs_objects, executor.map(dcs_request_perf, dcs_objects)):
            result.append(dcs_perf[1])
    return result


def dcs_caption_from_id(dcs_id,dcs_json_data):
    """
    Find Caption from an DataCore Id
    """ 
    for item in dcs_json_data:
        if item["Id"] == dcs_id:
            return str(item["Caption"])





def put_in_json_line(datas):

    result = []

    for data in datas:
        if "servers" in data["dcs_resource"]:
            line = '"instance":"{}","objecttype":"{}","host":"{}"{},{},{}'
            objecttype = "DataCore Servers"
            instance = str(data["ExtendedCaption"])
            host = str(data["Caption"])
            # Add specific info
            add_info = ',"id":"{}"'.format(str(data["Id"]))
            add_info += ',"OsVersion":"{}"'.format(str(data["OsVersion"]))
            add_info += ',"ProductBuild":"{}"'.format(str(data["ProductBuild"]))
            add_info += ',"ProductVersion":"{}"'.format(str(data["ProductVersion"]))
            add_info += ',"ProductName":"{}"'.format(str(data["ProductName"]))
            add_info += ',"ProductType":"{}"'.format(str(data["ProductType"]))
            add_info += ',"Caption":"{}"'.format(str(data["Caption"]))
            for k,v in data["Performances"].items():
                if "CollectionTime" in k:
                    continue
                result.append(line.format(
                    instance,
                    objecttype,
                    host,
                    add_info,
                    ":".join(['"'+str(k)+'"', '"'+str(v)+'"']),
                    '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                ))
            result.append(line.format(
                instance,
                objecttype,
                host,
                add_info,
                ":".join(['"State"', '"'+str(data["State"])+'"']),
                '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
            ))
            result.append(line.format(
                instance,
                objecttype,
                host,
                add_info,
                ":".join(['"CacheState"', '"'+str(data["CacheState"])+'"']),
                '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
            ))
            result.append(line.format(
                instance,
                objecttype,
                host,
                add_info,
                ":".join(['"PowerState"', '"'+str(data["PowerState"])+'"']),
                '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
            ))
        elif "pools" in data["dcs_resource"]:
            line = '"instance":"{}","objecttype":"{}","host":{}{},{},{}'
            objecttype = "DataCore Disk pools"
            instance = str(data["ExtendedCaption"])
            host = '"'+str(dcs_caption_from_id(data["ServerId"],dcs_servers))+'"'
            # Add specific info
            add_info = ',"id":"{}"'.format(str(data["Id"]))
            add_info += ',"InSharedMode":"{}"'.format(str(data["InSharedMode"]))
            add_info += ',"AutoTieringEnabled":"{}"'.format(str(data["AutoTieringEnabled"]))
            add_info += ',"Caption":"{}"'.format(str(data["Caption"]))
            for k,v in data["Performances"].items():
                if "CollectionTime" in k:
                    continue
                result.append(line.format(
                    instance,
                    objecttype,
                    host,
                    add_info,
                    ":".join(['"'+str(k)+'"', '"'+str(v)+'"']),
                    '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                ))
            result.append(line.format(
                instance,
                objecttype,
                host,
                add_info,
                ":".join(['"PoolStatus"', '"'+str(data["PoolStatus"])+'"']),
                '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
            ))
            result.append(line.format(
                instance,
                objecttype,
                host,
                add_info,
                ":".join(['"TierReservedPct"', '"'+str(data["TierReservedPct"])+'"']),
                '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
            ))
            result.append(line.format(
                instance,
                objecttype,
                host,
                add_info,
                ":".join(['"ChunkSize"', '"'+str(data["ChunkSize"]["Value"])+'"']),
                '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
            ))
            result.append(line.format(
                instance,
                objecttype,
                host,
                add_info,
                ":".join(['"MaxTierNumber"', '"'+str(data["MaxTierNumber"])+'"']),
                '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
            ))
        elif "virtualdisks" in data["dcs_resource"]:
            if data["StorageProfileId"] != None:
                line = '"instance":"{}","objecttype":"{}"{},{},{}'
                objecttype = "DataCore Virtual disks"
                instance = str(data["ExtendedCaption"])
                # Add specific info
                add_info = ',"id":"{}"'.format(str(data["Id"]))
                add_info += ',"ScsiDeviceIdString":"{}"'.format(str(data["ScsiDeviceIdString"]))
                add_info += ',"Type":"{}"'.format(str(data["Type"])) 
                if data["FirstHostId"] != None:
                    add_info += ',"FirstHost":"{}"'.format(str(dcs_caption_from_id(data["FirstHostId"],dcs_servers)))
                if data["SecondHostId"] != None:
                    add_info += ',"SecondHost":"{}"'.format(str(dcs_caption_from_id(data["SecondHostId"],dcs_servers)))
                add_info += ',"Caption":"{}"'.format(str(data["Caption"]))
                for k,v in data["Performances"].items():
                    if "CollectionTime" in k:
                        continue
                    result.append(line.format(
                        instance,
                        objecttype,
                        add_info,
                        ":".join(['"'+str(k)+'"', '"'+str(v)+'"']),
                        '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                    ))
                result.append(line.format(
                        instance,
                        objecttype,
                        add_info,
                        ":".join(['"DiskStatus"', '"'+str(data["DiskStatus"])+'"']),
                        '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                    ))
                result.append(line.format(
                        instance,
                        objecttype,
                        add_info,
                        ":".join(['"Size"', '"'+str(data["Size"]["Value"])+'"']),
                        '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                    ))
        elif "physicaldisks" in data["dcs_resource"]:
            line = '"instance":"{}","objecttype":"{}","host":{}{},{},{}'
            objecttype = "DataCore Physical disk"
            instance = str(data["ExtendedCaption"])
            host = '"'+str(dcs_caption_from_id(data["HostId"],dcs_servers))+'"'
            # Add specific info
            add_info = ',"id":"{}"'.format(str(data["Id"]))
            if data["InquiryData"]["Serial"] != None:
                add_info += ',"Serial":"{}"'.format(str(data["InquiryData"]["Serial"]))
            else:
                add_info += ',"Serial":"UNKNOWN"'
            add_info += ',"Type":"{}"'.format(data["Type"])
            add_info += ',"Caption":"{}"'.format(data["Caption"])
            for k,v in data["Performances"].items():
                if "CollectionTime" in k:
                    continue
                result.append(line.format(
                    instance,
                    objecttype,
                    host,
                    add_info,
                    ":".join(['"'+str(k)+'"', '"'+str(v)+'"']),
                    '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                ))
            result.append(line.format(
                    instance,
                    objecttype,
                    host,
                    add_info,
                    ":".join(['"DiskStatus"', '"'+str(data["DiskStatus"])+'"']),
                    '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                ))
        elif "ports" in data["dcs_resource"]:
            line = '"instance":"{}","objecttype":"{}","host":{}{},{},{}'
            objecttype = "DataCore SCSI ports"
            instance = str(data["ExtendedCaption"])
            if data["HostId"] != None:
                host = '"'+str(dcs_caption_from_id(data["HostId"],dcs_servers))+'"'
            else:
                host = "'NA'"
            # Add specific info
            add_info = ',"id":"{}"'.format(str(data["Id"]))
            try:
                if data["__type"] != None:
                    add_info += ',"__type":"{}"'.format(str(data["__type"]))
                    add_info += ',"Role":"{}"'.format(str(data["ServerPortProperties"]["Role"]))
            except:
                logging.info("No __type")
                
            add_info += ',"PortType":"{}"'.format(str(data["PortType"]))
            
            try:
                add_info += ',"PortRole":"{}"'.format(str(data["ServerPortProperties"]["Role"]))
            except:
                add_info += ',"PortRole":"N/A"'

            add_info = ',"Caption":"{}"'.format(str(data["Caption"]))
            for k,v in data["Performances"].items():
                if "CollectionTime" in k:
                    continue
                result.append(line.format(
                    instance,
                    objecttype,
                    host,
                    add_info,
                    ":".join(['"'+str(k)+'"', '"'+str(v)+'"']),
                    '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                ))
        elif "hosts" in data["dcs_resource"]:
            line = '"instance":"{}","objectname":"{}","host":"{}"{},{},{}'
            objecttype = "DataCore Hosts"
            instance = str(data["ExtendedCaption"])
            host = str(data["Caption"])
            # Add specific info
            add_info = ',"id":"{}"'.format(str(data["Id"]))
            add_info += ',"MpioCapable":"{}"'.format(str(data["MpioCapable"]))
            add_info += ',"AluaSupport":"{}"'.format(str(data["AluaSupport"]))
            for k,v in data["Performances"].items():
                if "CollectionTime" in k:
                    continue
                result.append(line.format(
                    instance,
                    objecttype,
                    host,
                    add_info,
                    ":".join(['"'+str(k)+'"', '"'+str(v)+'"']),
                    '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                ))
            result.append(line.format(
                instance,
                objecttype,
                host,
                add_info,
                ":".join(['"State"', '"'+str(data["State"])+'"']),
                '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
             ))
        elif "servergroups" in data["dcs_resource"]:
            if data["OurGroup"] != True:
                continue
            line = '"instance":"{}","objectname":"{}",{},{},{}'
            objecttype = "DataCore Server Groups"
            instance = str(data["Alias"])
            add_info = ',"id":"{}"'.format(str(data["Id"]))
            for k,v in data["Performances"].items():
                if "CollectionTime" in k:
                    continue
                result.append(line.format(
                    instance,
                    objecttype,
                    add_info,
                    ":".join(['"'+str(k)+'"', '"'+str(v)+'"']),
                    '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                ))
            for k,v in data["LicenseSettings"].items():
                if str(k) == "StorageCapacity" or str(k) == "LicensedBulkStorage":
                    result.append(line.format(
                        instance,
                        objecttype,
                        add_info,
                        ":".join(['"'+str(k)+'"', '"'+str(v["Value"])+'"']),
                        '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                    ))
                else:
                    result.append(line.format(
                        instance,
                        objecttype,
                        add_info,
                        ":".join(['"'+str(k)+'"', '"'+str(v)+'"']),
                        '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                    ))

            # ExistingProductKeys
            for productkey in data["ExistingProductKeys"]:
                lastfive = ',"LastFive":"{}"'.format(str(productkey["LastFive"]))
                for k,v in productkey.items():
                    if str(k) == "ActualCapacity" or str(k) == "CapacityConsumed":
                        result.append(line.format(
                            instance,
                            objecttype,
                            add_info + lastfive,
                            ":".join(['"'+str(k)+'"', '"'+str(v["Value"])+'"']),
                            '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                        ))
                    if str(k) == "Capacity" or str(k) == "Capacity":
                        result.append(line.format(
                            instance,
                            objecttype,
                            add_info + lastfive,
                            ":".join(['"'+str(k)+'"', '"'+str(v["Value"])+'"']),
                            '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                        ))
                    else:
                        result.append(line.format(
                            instance,
                            objecttype,
                            add_info + lastfive,
                            ":".join(['"'+str(k)+'"', '"'+str(v)+'"']),
                            '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                        ))


            result.append(line.format(
                instance,
                objecttype,
                add_info,
                ":".join(['"State"', '"'+str(data["State"])+'"']),
                '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
             ))
            result.append(line.format(
                instance,
                objecttype,
                add_info,
                ":".join(['"StorageUsed"', '"'+str(data["StorageUsed"]["Value"])+'"']),
                '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
             ))
            
            if  "NextExpirationDate" in data:
                result.append(line.format(
                    instance,
                    objecttype,
                    add_info,
                    ":".join(['"NextExpirationDate"', '"'+str(data["NextExpirationDate"])+'"']),
                    '"CollectionTime":"'+data["Performances"]["CollectionTime"]+'"'
                ))
            
        else:
            logging.error("This resource ({}) is not yet implemented".format(resource))
    
    # Create json
    logging.info("create json file")       
    data = "}\n{".join(result)

    #print("{"+data+"}")
    f = open("datacore_perf_"+ time.strftime("%Y%m%d-%H%M%S") +".json", "w")
    f.write("{"+data+"}")
    f.close()
    




if __name__ == "__main__":
    
    dcs_servers = {}

    dcs_servers = dcs_get_object("servers")

    dcs_servers_hosts = dcs_servers + dcs_get_object("hosts")
    resources = [r for r in config['RESOURCES'] if config['RESOURCES'].getboolean(r)]
    
    dcs_objects = []
    for resource in resources:
        dcs_objects += dcs_get_object(resource)
    
    dcs_perfs = dcs_get_perf(dcs_objects)

    put_in_json_line(dcs_perfs)
  
