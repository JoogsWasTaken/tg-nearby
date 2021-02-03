# tg-nearby

Trilateration of nearby Telegram users as described in my corresponding [article](https://owlspace.xyz/cybersec/tg-nearby).

## Setup

If you want to toy with the code in this repository and collect some location data with Telegram yourself, please keep in mind that there is a high likelihood that something will break when the Telegram Android app updates. Familiarize yourself with the following steps, make sure you know what you're doing and be prepared to troubleshoot problems when they arise.

1. Clone the Telegram Android app source code from the [official repository](https://github.com/DrKLO/Telegram) and follow the outlined steps to creating your own development build.
2. Apply the [PeopleNearbyActivity patch](PeopleNearbyActivity.patch) to the Java class of the same name.
3. Install all Python dependencies using `python -m pip install -r requirements.txt`. It is recommended to create a separate virutal environment in the root of this repository first.

## Usage

**Note:** You will need a working Telegram account. When navigating to the "People Nearby" menu entry on your dev build, Telegram will ask you to share your location. This is necessary to be able to get a list of nearby users. This won't automatically show your presence to other users in proximity.

1. Install the patched Telegram Android app onto an Android device. Navigate to the "People Nearby" menu entry in the app's sidebar.
2. Keep the "People Nearby" screen open and active for as long as you wish to collect data. Walk around to achieve better location estimates.
3. Copy the corresponding log files from your device. They will be located in a directory called `logs` in the app's data directory, either on external or internal storage. You will need to copy the files either through adb or with Android Studio's integrated device file explorer.
4. Feed the logs into a SQLite database. Navigate to the root of this repository and execute `python ingest.py my_database.sqlite logs/my_awesome_log.txt`. You can append multiple logs to a single database by simply changing the log file path argument.
5. Run the web interface. Navigate to the `server` directory of this repository and execute `python server.py my_database.sqlite`.
