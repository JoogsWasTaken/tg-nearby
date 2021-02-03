import sys, os.path
import shutil
import sqlite3
import threading
import json

from http.server import HTTPServer, BaseHTTPRequestHandler, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from scipy.optimize import minimize
from geopy.distance import distance

def mse(x, locations, distances):
    """
    Computes the mean square error for a list of locations
    and distances to a point x.

        x -- Target location (lat, lng)
        locations -- Reference locations (list of (lat, lng))
        distances -- Reference distances (list of int)
    """
    mse = 0

    for loc, dist in zip(locations, distances):
        distance_calculated = distance(x, loc).m
        mse += (distance_calculated - dist) ** 2
    
    return mse / len(distances)

def make_custom_http_handler(con):        

    class CustomHTTPRequestHandler(BaseHTTPRequestHandler):

        def send_json(self, obj):
            self.send_response(200)
            self.send_header("Content-type", "application/json;charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(obj).encode("utf-8"))

        def do_GET(self):
            url = urlparse(self.path)
            res = url.path[1:].split("/")
            query = parse_qs(url.query)

            print(url, res, query)

            # show index page
            if url.path == "/":
                self.send_response(200)
                self.send_header("Content-type", "text/html;charset=utf-8")
                self.end_headers()

                with open("index.html", "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
                
                return
            
            # handle api calls
            if res[0] == "api":
                # send user listing
                if res[1] == "users":
                    self.handle_api_users()
                    return
                
                # send location listing
                if res[1] == "locations":
                    self.handle_api_locations()
                    return
                
                if res[1] == "query":
                    uid = int(query["id"][0])
                    max_distance = int(query["mdist"][0])
                    max_accuracy = float(query["macc"][0])

                    self.handle_api_query(uid, max_distance, max_accuracy)
                    return
            
            self.send_response(404)
            self.send_header("Content-type", "text/plain;charset=utf-8")
            self.end_headers()
            self.wfile.write("Not found".encode("utf-8"))
        
        def send_query_response(self, sightings, res_success, res_loc=None, res_reason=None):
            self.send_json({
                "sightings": sightings,
                "guess": {
                    "success":  res_success,
                    "reason":   res_reason if not res_success else "",
                    "result":   {
                        "latitude":     res_loc[0],
                        "longitude":    res_loc[1]
                    } if res_success else {}
                }
            })
        
        def handle_api_query(self, user_id, max_dist, max_acc):
            # list of all sightings for the client
            all_sightings = []
            # list of locations and distances for mse (filtered)
            locations = []
            distances = []
            # min distance to select closest point for initial guess
            distance_min = 1e9
            initial_guess = None
            # locations with distance <= 100, used for initial guess
            locations_100 = []

            for row in con.execute("SELECT l.latitude, l.longitude, s.distance, l.accuracy FROM locations l INNER JOIN sightings s ON l.fix_ts = s.fix_ts WHERE s.user_id = ?", [ user_id ]):
                loc = ( row[0], row[1] )
                dist = row[2]
                acc = row[3]

                # check against provided params
                if dist > max_dist:
                    continue

                if acc > max_acc:
                    continue

                # this'll be provided no matter what
                all_sightings.append({
                    "latitude":     loc[0],
                    "longitude":    loc[1],
                    "distance":     dist
                })

                # these coords are actually not used in minimization, but
                # rather to set an initial guess
                if dist <= 100:
                    locations_100.append(loc)
                    distance_min = 100
                    continue

                locations.append(loc)
                distances.append(dist)

                # check if initial guess needs to be updated
                # this won't happen if 100s have been found
                if dist < distance_min:
                    initial_guess = loc
                    distance_min = dist
            
            # check if any locations matched the user specs
            if len(all_sightings) == 0:
                self.send_query_response([], False, res_reason="No sightings matching given parameters.")
                return
            
            # check if there's even a point in minimizing
            if len(all_sightings) > 0 and len(locations) < 3:
                self.send_query_response(all_sightings, False, res_reason="Not enough sightings to estimate location, need at least three.")
                return
            
            # if 100s were found, then use those to make
            # an initial guess
            count_100s = len(locations_100)

            if count_100s > 0:
                lat, lng = (0, 0)

                for loc in locations_100:
                    lat += loc[0]
                    lng += loc[1]
                
                # simple average (just a guess)
                lat /= count_100s
                lng /= count_100s

                initial_guess = (lat, lng)
            
            result = minimize(
                mse,
                initial_guess,
                args=(locations, distances),
                method="L-BFGS-B",
                options={
                    "ftol": 1e-5,
                    "maxiter": 1e+7
                }
            )

            self.send_query_response(all_sightings, result.success, result.x, result.message)

        def handle_api_locations(self):
            all_locs = []

            for row in con.execute("SELECT fix_ts, latitude, longitude, altitude, accuracy FROM locations"):
                all_locs.append({
                    "timestamp": row[0],
                    "latitude": row[1],
                    "longitude": row[2],
                    "altitude": row[3],
                    "accuracy": row[4]
                })
            
            self.send_json(all_locs)

        def handle_api_users(self):
            all_users = []

            for row in con.execute("SELECT u.id, u.display_name, COUNT(*) AS sighting_count FROM users u INNER JOIN sightings s ON s.user_id = u.id GROUP BY u.id"):
                all_users.append({
                    "id": row[0],
                    "name": row[1],
                    "sightingCount": row[2]
                })
            
            self.send_json(all_users)
    
    return CustomHTTPRequestHandler

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: {} dbfile".format(sys.argv[0]))
    
    db_path = sys.argv[1]

    if not os.path.exists(db_path):
        print("file at path \"{}\" doesn't exist".format(db_path))
        exit()
    
    con = sqlite3.connect(db_path)
    srv = HTTPServer(("localhost", 8000), make_custom_http_handler(con))

    try:
        print("listening on port {}".format(srv.server_port))
        srv.serve_forever()
    except KeyboardInterrupt:
        print("shutting down")
        # pew
        t = threading.Thread(target=srv.shutdown)
        t.start()
        t.join()

        con.close()