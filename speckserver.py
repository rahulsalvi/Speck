#!/usr/bin/env python3

from math import degrees, radians, cos, sin, asin, sqrt, atan2
import io
import os
import requests
from flask import Flask, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

MAPS_API_KEY = os.environ["MAPS_API_KEY"]
MAPS_API_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
WOLFRAM_APP_ID = os.environ["WOLFRAM_APP_ID"]
WOLFRAM_API_URL = 'http://api.wolframalpha.com/v2/query'

# http://stackoverflow.com/questions/4913349/haversine-formula-in-python-bearing-and-distance-between-two-gps-points
def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    miles = 3956 * c
    return miles

def findDistantLonLat(lon, lat, direction, dist):
    dist = dist / 3956
    direction = radians(direction)
    lon, lat = map(radians, [lon, lat])
    destLat = asin(sin(lat)*cos(dist)+
                   cos(lat)*sin(dist)*cos(direction))
    destLon = lon + atan2(sin(direction)*sin(dist)*cos(lat),
                          cos(dist)-sin(lat)*sin(destLat))
    return degrees(destLon), degrees(destLat)

def headingBetweenTwoPoints(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    heading = atan2(sin(dlon)*cos(lat2), cos(lat1)*sin(lat2)-
                                         sin(lat1)*cos(lat2)*cos(dlon))
    heading = degrees(heading)
    heading = (heading + 360) % 360
    return heading

@app.route('/', methods=['GET'])
def main():
    args = request.args.to_dict()

    addr1 = args["addr1"]
    addr2 = args["addr2"]
    scaleQuery = args["scale"]

    # get the locations of the two places
    param1 = {'address':addr1, 'key':MAPS_API_KEY}
    param2 = {'address':addr2, 'key':MAPS_API_KEY}
    r1 = requests.get(MAPS_API_URL, params=param1)
    r2 = requests.get(MAPS_API_URL, params=param2)
    loc1 = r1.json()["results"][0]["geometry"]["location"]
    loc2 = r2.json()["results"][0]["geometry"]["location"]

    # compute distance between them
    lon1, lat1, lon2, lat2 = map(float, [loc1["lng"], loc1["lat"], loc2["lng"], loc2["lat"]])
    dist = haversine(lon1, lat1, lon2, lat2)
    head = headingBetweenTwoPoints(lon1, lat1, lon2, lat2)

    if head < 60 or head > 120:
        head = headingBetweenTwoPoints(lon1, lat1, -98.57, 39.82)

    # get the scale distance by querying Wolfram
    param3 = {'appid':WOLFRAM_APP_ID, 'input':scaleQuery}
    r3 = requests.get(WOLFRAM_API_URL, params=param3)

    # read in locations from the file outputted by the Wolfram notebook
    locationDistances = []
    with open("/Users/rahulsalvi/Desktop/speck/data.out", "r") as f:
        lines = f.readlines()
        lines = [x.strip() for x in lines]
        for line in lines:
            t = line.split('"')
            key = t[1]
            value = t[2]
            if "*^" in value:
                base,exp = value.split("*^")
                value = float(base) * pow(10,float(exp))
            locationDistances.append([key.lower(), float(value)])

    # extract the actual distance from the Wolfram query
    # it's easier to start in km, then convert to miles because of how Wolfram formats its output
    # miles are formatted as "... million miles", instead of scientific notation
    scale = 0
    for line in r3.text.split('\n'):
        if "kilometers" in line:
            chunk = line.strip().split(" ")[0]
            chunk = chunk[5:]
            base = float(chunk.split("×")[0])
            t = chunk.split("^")
            if len(t) > 1:
                exp = int(t[1])
            else:
                exp = 0
            scale = base * pow(10, exp) * 0.621371
            break

    output = io.StringIO()

    output.write("distance:")
    output.write(str(round(dist, 4)))
    output.write(":")
    output.write(str(scale))
    output.write(":")
    output.write('\n')

    # write outputs
    scaleFactor = dist/scale
    sunDist = 0
    for i in range(len(locationDistances)):
        if i == 0:
            sunDist = locationDistances[0][1]*scaleFactor
            output.write(":".join([locationDistances[0][0],
                                   str(round(sunDist, 4)),
                                   str(lat1),
                                   str(lon1),
                                   "\n"]))
        elif i < 3:
            scaledDist = locationDistances[i][1]*scaleFactor
            correctedDist = sunDist - scaledDist
            if (correctedDist < 0) or (correctedDist > 10000):
                destLon = lon1
                destLat = lat1
            else:
                destLon, destLat = findDistantLonLat(lon1, lat1, head, correctedDist)
            output.write(":".join([locationDistances[i][0],
                                   str(round(scaledDist, 4)),
                                   str(destLat),
                                   str(destLon),
                                   "\n"]))
        else:
            scaledDist = locationDistances[i][1]*scaleFactor
            correctedDist = sunDist+scaledDist
            if (correctedDist < 0) or (correctedDist > 10000):
                destLon = lon1
                destLat = lat1
            else:
                destLon, destLat = findDistantLonLat(lon1, lat1, head, correctedDist)
            output.write(":".join([locationDistances[i][0],
                                   str(round(scaledDist, 4)),
                                   str(destLat),
                                   str(destLon),
                                   "\n"]))

    contents = output.getvalue()
    output.close()
    return contents
