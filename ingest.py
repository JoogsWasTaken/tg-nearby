import os, sys
import sqlite3

def explode_line(line):
    res = {}

    line = line.strip()
    line = line[line.index("[") + 1:line.index("]")]

    for seg in line.split(", "):
        kv = seg.split("=")
        k = kv[0]   # key
        v = kv[1]   # value

        if v[0] == "\"" and v[-1] == "\"": # remove quotes from strings
            v = v[1:-1]
        
        res[k] = v
    
    return res

def main(out_path, in_path):
    if not os.path.exists(in_path):
        print("path \"{}\" does not exist".format(in_path))
        return
    
    loc_tuples = []
    user_tuples = []
    sight_tuples = []

    with open(in_path, "r", encoding="utf-8") as f:
        last_loc = None
        
        for line in f:
            if "location update" in line:
                l = explode_line(line)

                # in case the gps fix hasn't updated
                if last_loc is not None and l["fixTs"] == last_loc["fixTs"]:
                    continue

                last_loc = l

                loc_tuples.append((
                    int(l["fixTs"]),        # gps fix ts
                    int(l["currentTs"]),    # log ts
                    int(l["cmTs"]),         # cm ts
                    float(l["lat"]),        # latitude
                    float(l["lng"]),        # longitude
                    float(l["alt"]) if bool(l["hasAlt"]) else None,     # altitude
                    float(l["acc"]) if bool(l["hasAcc"]) else None      # hoz accuracy
                ))

                # skip until list start (should only be one line but still)
                while not "peer update list start" in line:
                    line = next(f)
                
                # get first peer update line
                line = next(f)
                
                # iterate over list
                while not "peer update list end" in line:
                    # hotfix
                    if not "peer update" in line:
                        line = next(f)
                        continue

                    p = explode_line(line)
                    user_tuples.append((
                        int(p["id"]),       # user id
                        p["displayName"]    # display name
                    ))
                    sight_tuples.append((
                        int(p["id"]),               # user id
                        int(last_loc["fixTs"]),     # ts of original gps fix
                        int(p["distance"]),         # distance
                        int(p["expires"])           # expire ts
                    ))
                    line = next(f)

    con = sqlite3.connect(out_path)

    con.executescript("""
        CREATE TABLE IF NOT EXISTS locations (
            fix_ts      INTEGER,
            log_ts      INTEGER NOT NULL,
            cm_ts       INTEGER NOT NULL,
            latitude    REAL NOT NULL,
            longitude   REAL NOT NULL,
            altitude    REAL,
            accuracy    REAL,
            PRIMARY KEY (fix_ts)
        );

        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER,
            display_name    TEXT NOT NULL,
            PRIMARY KEY (id)
        );

        CREATE TABLE IF NOT EXISTS sightings (
            id          INTEGER,
            user_id     INTEGER,
            fix_ts      INTEGER,
            distance    INTEGER NOT NULL,
            expire_ts   INTEGER NOT NULL,
            PRIMARY KEY (id AUTOINCREMENT),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (fix_ts) REFERENCES locations(fix_ts)
        );
    """)

    # there may be two updates using the same gps fix, so ignore on conflict
    con.executemany("""
        INSERT OR IGNORE INTO locations (fix_ts, log_ts, cm_ts, latitude, longitude, altitude, accuracy)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, loc_tuples)

    # users may be sighted multiple times, so ignore on conflict
    con.executemany("INSERT OR IGNORE INTO users (id, display_name) VALUES (?, ?)", user_tuples)
    con.executemany("INSERT INTO sightings (user_id, fix_ts, distance, expire_ts) VALUES (?, ?, ?, ?)", sight_tuples)
    con.commit()

    con.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: {} outfile infile".format(sys.argv[0]))
        exit()
    
    main(sys.argv[1], sys.argv[2])