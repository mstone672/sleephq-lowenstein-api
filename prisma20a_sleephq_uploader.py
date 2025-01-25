""" Lowenstein Prisma 20a (Darth Vader) data import to SleepHQ

Script used to uploading Lowenstein Prisma device data to SleepHQ via API


Version History:
    Verison 1.0.3: 22-Jan-2025
    Author: Mike Stone
    Changes:
       - Added TEAM_ID variable to the .env file
       - Added obtaining the team id as part of the initial run/configuration

    Version 1.0.2: 14-Jan-2025
    Author: Mike Stone
    Changes:
       - fixed issue with message notifications
       - added local logging, 1MB with a rotation of 3 logs
       - added during first setup to enable ntfy notifications

    Version 1.0.1: 14-Jan-2025
    Authoer Mike Stone
    Changes:
        - added support for ntfy notifcaitons. Please refer to:
            https://docs.ntfy.sh for more information
        - requires 3 new variables in the .env file:
          NTFY_ENABLE='NO'
          NTFY_TOKEN='<place holder, authentication not implemented yet>'
          NTFY_TOPIC='<topic>'
        - If these are not present, they will be create upon first run on the script

    version 1.0: 07-Jan-2025
    Author: Mike Stone
    Changes: Initial development

This is based off of the work by Jay M (https://github.com/jmasarweh/cpap-sleephq-uploader)
with the MD5 hash calculation provided by Adam Pallozzi and converted to python by
Thorsten Brinkmann.

Requirements:
 - This requires the python-dotenv to be installed via pip install python-dotenv
 - a .env located in the same folder as the script with the following lines:
    CLIENT_ID = '<your client id>'
    CLIENT_SECRET = '<your secret>'
    DIR_PATH = '<path to the config.pcfg and therapy.pdat files>'
    SERIAL = 'ANY | <serial number of your  Prisma device>'
 If you have more than one xPAP machine associated with your account, goto My Devices
 and locate the Lowenstein device serial number to attach the date to.  If you have
 a single xPAP machine only on your account, use the 'ANY' value to get the serial number
 of the device.

 Potential future enhancements:
  1 -  Add one or more optional modules for notifications
    - e.g. MQTT publishing for other systems such as Home Assistant to pull in daily job status
    - email notification
  2 - A routine to notify users about failures
"""
class NTFY:
    """
     Encapsulataed everything needed to utilize ntfy notifications
     Also includes the ability to write to the screen and a log file
     This keeps all messaging to a single object rather than passing
     multiple paramters to all function definitions
    """
    def __init__(self, enabled, token, topic, logger):
        """
        Construct a new ntfy object.

        :param enabled : Should alerts go out via ntft?  Valid values are YES to enable, anything else
                         do disable it
        :param token   : ntfy token for protected topics
        :param topic   : topic to post messages to
        """
        self.enabled = enabled
        self.token = token
        self.topic = topic
        self.logger = logger

    def display_message(self, message):
        """
        Display a message to the screen and log it to the logfile
        """
        self.logger.info(message)
        print(message)
        return

    def send_success(self, message):
        """
        Send a success message via the ntfy service

        :param message : The message to send 
        """
        if self.enabled == "YES":
            ntfy_url = "https://ntfy.sh/" + self.topic
            requests.post(ntfy_url,
                data=message,
                headers={ "Title": "Success",
                          "Priority": "default",
                          "Tags": "white_check_mark"})

    def send_failure(self, message):
        """
        Send a failure message via the ntfy service

        :param message : The message to send 
        """
        if self.enabled == "YES":
            ntfy_url = "https://ntfy.sh/" + self.topic
            requests.post(ntfy_url,
                data=message,
                headers={ "Title": "Failure",
                          "Priority": "default",
                          "Tags": "rotating_light"})

class FileDetails:
    """
     Encapsulates all data required to be able to upload files to the SleepHQ API
    """

    def __init__(self, short_name, long_name, file_hash):
        """
        Construct a new FileDetail object.

        :param short_name: The filename of a file to upload
        :param long_name : The full path and filename of a file to upload
        :param file_hash : The MD5 filehash conforming to the API requirement of the file+filename.
                          Please refer to the /v1/imports/files/calculate_content_hash information at
                          https://sleephq.com/api-docs/index.html
        """
        self.ShortName = short_name
        self.LongName = long_name
        self.FileHash = file_hash

    def __str__(self):
        """
        Return the details of the class instance.
        """
        return f"(Filename = {self.ShortName}, Full path = {self.LongName}, MD5 File hash is {self.FileHash})"


def display_failure_and_exit(message, msg_ntfy):
    """
    Routine for displaying any error messages related to a failure of an API call
    After displaying the message, exit the script.

    Any hooks into additional notifications can be added here

    :param message: The message to display
    :param my_ntfy : the ntfy object for sending notifications

    Return value: None
    """
    ntfy.display_message( message)
    msg_ntfy.send_failure(message)
    sys.exit(1)


def get_access_token(client_id, client_secret, my_ntfy):
    """
    Function to obtain an API access token for querying and uploading a user's SleepHQ account

    :param client_id     : The client UUID generated when adding an API key
    :param client_secret : The client secret generated when adding an API key
    :param my_ntfy : the ntfy object for sending notifications

    Return value: an API token if the API call is successful; otherwise terminate the script
    """
    url = "https://sleephq.com/oauth/token"
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'password',
        'scope': 'read write'
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        ntfy.display_message("\tAuthorization successful")
        return 'Bearer ' + response.json()['access_token']
    except requests.RequestException as e:
        display_failure_and_exit(f"\tFailed to get access token: {e}", my_ntfy)


def calculate_md5(full_file_name):
    """
    Create a SleepHQ API compliance file hash.  Each of the data chunks
    need to be utf-8 encoded to ensure the file hash matches how SleepHQ
    calculates the hash values.

    :param full_file_name : The full path of the file to create the MD5 hash from

    returns: a SleepHQ API compliant hash
    """
    hasher = hashlib.md5()  # Create a hasher instance
    short_file_name = os.path.basename(full_file_name)
    with open(full_file_name, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            utf8_chunk = ''.join([chr(b) for b in chunk])
            hasher.update(utf8_chunk.encode('utf-8'))
    # Update the hasher with the file name encoded in UTF-8
    hasher.update(short_file_name.encode('utf-8'))
    return hasher.hexdigest()


def get_team_id(headers, my_ntfy):
    """
    Retrieve the Team ID based upon your Client ID

    :param headers : JSON headers for the request
    :param my_ntfy : the ntfy object for sending notifications

    Return value:  None
    """
    url = "https://sleephq.com/api/v1/teams"
    try:
        response = requests.request("GET", url, headers=headers)
        response.raise_for_status()

        for index, team in enumerate(teams):
            ntfy.display_message(f"Found:id {team['id']}, " + 
                                 f"Name: {team['attributes']['name']}, ")
        return()
    except requests.RequestException as e:
        display_failure_and_exit(f"\tFailed to get Team Id: {e}", my_ntfy)


def collect_files(dir_path):
    """
    Create a list of FileDetail class objects based upon files found
           in the given folder.

    :param dir_path : The full path to where the xPAP data files are

    Return value: a List of FileDetail objects
    """
    # create an empty list
    import_files = []
    # retrieve the list of files and directories from the file system
    # only care about the list of files
    for (dirpath, dirnames, filenames) in walk(dir_path):
        for f in filenames:
            # Create an instance of the FileDetails class and assign values
            #  to all members
            fullname = os.path.abspath(os.path.join(dir_path, f))
            hash_value = calculate_md5(fullname)
            # Get the calculated hash
            fdetail = FileDetails(f, fullname, hash_value)
            # Add the FileDetail object to the list of files
            import_files.append(fdetail)
    return import_files


def reserve_import_id(team_id, headers, my_ntfy):
    """
    Obtains an import ID from SleepHQ

    :param team_id   : your team ID
    :param headers : JSON headers for the request
    :param my_ntfy : the ntfy object for sending notifications

    Return value: The import ID to be used with the current data upload
    """
    url = f"https://sleephq.com/api/v1/teams/{team_id}/imports"
    payload = {'programmatic': False}
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        return response.json()['data']['id']
    except requests.RequestException as e:
        display_failure_and_exit(f"\tFailed to reserve import ID: {e}", my_ntfy)

def get_machine_id(team_id, headers, serial_number, my_ntfy):
    """
    Get the machine ID to associate data to. Match against the provided serial number

    :param team_id      : your team ID
    :param headers : JSON headers for the request
    :param serial_number : The Serial Number of the Machine to upload data against
    :param my_ntfy : the ntfy object for sending notifications

    Return value : The machine_id that matches the serial number provided
    """
    url = f"https://sleephq.com/api/v1/teams/{team_id}/machines"
    payload = {'programmatic': True}
    status_message = ""
    try:
        response = requests.get(url, headers=headers, data=payload)
        response.raise_for_status()
        machines = response.json()['data']
        for index, machine in enumerate(machines):
            if serial_number == "GETLIST":
                ntfy.display_message(f"Found:{machine['attributes']['brand']}, " + 
                      f"{machine['attributes']['model']}, " +
                      f"Serial Number: {machine['attributes']['serial_number']}")
            else:
                shq_machine_serial = machine['attributes']['serial_number']
                status_message+=(f"\t{machine['attributes']['brand']}, " + 
                                f"{machine['attributes']['model']}, " +
                                f"Serial Number: {machine['attributes']['serial_number']}\n")
                if shq_machine_serial == serial_number or serial_number == "ANY":
                    ntfy.display_message(f"Found machine ID {machine['id']}")
                    return (machine['id'])
        if serial_number == "GETLIST":
            return()
        # fail as a last resort if the matching serial number can't be located
        display_failure_and_exit(f"Failed to get Device_ID that matches {serial_number}\nFound:\n" + status_message + 
                                  "\nUpdate your .env file with the correct serial number and try again.", my_ntfy)
    except requests.RequestException as e:
        display_failure_and_exit(f"\tFailed to query Device ID: {e}", my_ntfy)


def upload_files(import_id, headers, file_detail_list, my_ntfy):
    """
    Upload data files one by one to SleepHQ

    :param import_id  : The import identifier previously obtained
    :param headers : JSON headers for the request
    :param file_details_list : List of FileDetail objects to import
    :param my_ntfy : the ntfy object for sending notifications

    Return value: None
    """
    url = f"https://sleephq.com/api/v1/imports/{import_id}/files"
    for item in file_detail_list:
        with open(item.LongName, 'rb') as f:
            file_content = f
            files = {
                'import_id': import_id,
                'name': (None, item.ShortName),
                'path': (None, "./"),
                # 'file': (file_name, file_content),
                'file': (file_content),'content_hash': (None, item.FileHash)}
            try:
                response = requests.post(url, headers=headers, files=files)
                response.raise_for_status()
                ntfy.display_message(f"\tFile {item.ShortName} has been imported")
            except requests.RequestException as e:
                display_failure_and_exit(f"\tFailed to upload file {item.ShortName}: {e}", my_ntfy)
            time.sleep(1.5)


def process_imported_files(import_id, headers, my_ntfy):
    """
    Tell SleepHQ to process the files that were uploaded as part of the import
    identified by import_id

    :param import_id : The import ID used to upload files
    :param headers : JSON headers for the request
    :param my_ntfy : the ntfy object for sending notifications

    Return values: None
    """
    url = f"https://sleephq.com/api/v1/imports/{import_id}/process_files"
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        ntfy.display_message(f"\tFiles are now being processed in SleepHQ for Import ID: {import_id}")
    except requests.RequestException as e:
        display_failure_and_exit(f"\tFailed to process imported files: {e}" +
                                 f"But you can try the Process Import request again later by calling: {url}", my_ntfy)


def check_imported_files(import_id, headers, my_ntfy):
    """
    Check for errors with an import ID

    :param: import_id : The import_id to check
    :param headers : JSON headers for the request
    :param my_ntfy : the ntfy object for sending notifications

    Return value: None
    """
    url = f"https://sleephq.com/api/v1/imports/{import_id}"
    r_result = ""
    f_result = ""
    try:
        while (not r_result == "complete"):
            time.sleep(15)
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            status_msg = response.json()['data']
            ntfy.display_message(f"\timport status:{status_msg['attributes']['status']}; Failure Reason: " +
                  f"{status_msg['attributes']['failed_reason']}")
            r_result = status_msg['attributes']['status']
            f_result = status_msg['attributes']['failed_reason']
    except requests.RequestException as e:
        display_failure_and_exit(f"\tFailed to process imported files: {e}" +
                                 f"But you can try the Process Import request again later by calling: {url}". my_ntfy)
        sys.exit(1)
    if not r_result == "complete":
        display_failure_and_exit(f"\tFailed to process imported files.  Result is {r_result}. Failure code is {f_result}", my_ntfy)
    else:
        my_ntfy.send_success("Data import into SleepIQ was successful")
    return

def display_message(logme, message):
    """
    Display a message to both the screen and the log file

    :param logme   : a logger instance
    :param message : the message to display/log
    """
    logme.info(message)
    print(message)
    return


##################
# Module imports #
##################
import importlib.util
import os  # used for OS file operations
import sys  # used to raise a system error
from os import walk  # used to get files from a folder
import time  # used for sleeping
from pathlib import Path
import json
import hashlib
import logging
from logging.handlers import RotatingFileHandler

# Modules not installed by debault on python3
requests_spec = importlib.util.find_spec("requests")
dotenv_spec = importlib.util.find_spec("dotenv")

# Check if all required modules are present
if requests_spec is None:
    display_failure_and_exit("Required module \"requests\" is not found. Please run: pip3 install requests")
else:
    import requests
if dotenv_spec is None:
    display_failure_and_exit("Required module \"dotenv\" is not found. Please run: pip3 install python-dotenv")
else:
    from dotenv import load_dotenv, find_dotenv, set_key  # For loading environment variables

if __name__ == '__main__':
    # define a rotating log file
    logging.basicConfig(
        handlers=[RotatingFileHandler('./prisma-api.log', maxBytes=100000, backupCount=3)],
        level=logging.DEBUG,
        format="[%(asctime)s] %(message)s",
        datefmt='%Y-%m-%dT%H:%M:%S')

    # create a dummy entry for logging purposes
    # this can't send out any notifications at this time
    ntfy = NTFY("NO", None, None, logging)

    # Load environment values
    my_client_id = ""
    my_client_secret = ""
    my_device_serial = ""
    my_dir_path = ""
    env_file_path = Path(os.getcwd()+ "/.env")
    env_path = find_dotenv()
    if not env_path:
        ntfy.display_message(".env file does not exist, let's create it..")
        my_client_id = input("Please enter your SleepHQ Client ID > ")
        my_client_secret = input("Please enter your SleepHQ Client Secret > ")
        my_dir_path = input("Please enter the path to the config.pcfg and therapy.pdat files > ")
        # Create header used for most API calls
        # Connect to SleepHQ and try to authenticate
        my_auth_token = get_access_token(my_client_id, my_client_secret, ntfy)
        my_header = {
            'Authorization': my_auth_token,
            'Accept': 'application/json'
        }

        # Get the current team ID associated with the client id
        get_team_id(my_header, ntfy)
        my_team_id = input("Please enter the team ID to use > ")
        print("Trying to get list of device(s) from SleepHQ.")
        # get the correct machine id to attach the data uplaod to
        machine_id = get_machine_id(my_team_id, my_header, "GETLIST", ntfy)
        my_device_serial = input("Please enter or copy/paste the device serial number > ")
        # create .env file in the current working folder
        env_file_path.touch(mode=0o600, exist_ok=False)
        set_key(dotenv_path=env_file_path, key_to_set="CLIENT_ID", value_to_set=my_client_id)
        set_key(dotenv_path=env_file_path, key_to_set="CLIENT_SECRET", value_to_set=my_client_secret)
        set_key(dotenv_path=env_file_path, key_to_set="SERIAL", value_to_set=my_device_serial)
        set_key(dotenv_path=env_file_path, key_to_set="DIR_PATH", value_to_set=my_dir_path)
        set_key(dotenv_path=env_file_path, key_to_set="TEAM_ID", value_to_set=my_team_id)
        ntfy.display_message(".env has been created, proceeding with uploading data")
    load_dotenv()
    my_client_id = os.getenv('CLIENT_ID')
    my_client_secret = os.getenv('CLIENT_SECRET')
    my_device_serial = os.getenv('SERIAL')
    my_dir_path = os.getenv('DIR_PATH')
    my_team_id = os.getenv('TEAM_ID')
    ntfy_enable = os.getenv('NTFY_ENABLE')
    ntfy_topic = os.getenv('NTFY_TOPIC')
    ntfy_token = os.getenv('NTFY_TOKEN')
    ## Add in ntfy entries if they don't exist
    if ntfy_enable == None:
        ntfy.display_message(".env does not contain entries for ntfy... creating")
        my_ntfy_enable = input("Enable ntfy push notifications? (YES/NO) > ")
        my_ntfy_token = input("Enter in your ntfy token (currently not used) > ")
        my_ntfy_topic = input("Enter in your ntfy topic name > ")
        set_key(dotenv_path=env_file_path, key_to_set="NTFY_ENABLE", value_to_set=my_ntfy_enable)
        set_key(dotenv_path=env_file_path, key_to_set="NTFY_TOKEN", value_to_set=my_ntfy_token)
        set_key(dotenv_path=env_file_path, key_to_set="NTFY_TOPIC", value_to_set=my_ntfy_topic)
        load_dotenv() # reload environment variables
    ntfy = NTFY(ntfy_enable, ntfy_token, ntfy_topic, logging)

    # Collect information on the config.pcfg and therapy.pdat files
    # Those two files should be the only files in the folder
    # specified by my_dir_path
    ntfy.display_message("Step 1: Gather files for uploading and comput MD5 hash.")
    my_file_details_list = collect_files(my_dir_path)
    if len(my_file_details_list) == 0:
        display_failure_and_exit(f"\tNo files found at path {my_dir_path} to import to SleepHQ." +
                                  "Check your folder path and update the .env file if needed.", ntfy)
    # Print out result file list
    for fname in my_file_details_list:  ntfy.display_message(f"\tProcessed: {fname.LongName} hash: {fname.FileHash}")
    ntfy.display_message("Completed Step 1")
    # Get the API authorization token
    ntfy.display_message("Starting Step 2: Obtain Access Token")
    my_auth_token = get_access_token(my_client_id, my_client_secret, ntfy)
    # Create header used for most API calls
    my_header = {
        'Authorization': my_auth_token,
        'Accept': 'application/json'
    }
    ntfy.display_message("Completed Step 2")
    # get the correct machine id to attach the data uplaod to
    machine_id = get_machine_id(my_team_id, my_header, my_device_serial, ntfy)
    ntfy.display_message("Starting Step 3: Obtaining machine ID")
    ntfy.display_message(f"\tMachine ID retrieved successfully: {machine_id}")
    ntfy.display_message("Completed Step 3")
    # get an import ID reservation
    ntfy.display_message("Starting Step 4: Obtain an Import ID")
    my_import_id = reserve_import_id(my_team_id, my_header, ntfy)
    ntfy.display_message(f"\tImport Id reserved successfully: {my_import_id}")
    ntfy.display_message("Completed Step 4")
    # upload files to SleepHQ API
    ntfy.display_message("Starting Step 5: Uploading files")
    upload_files(my_import_id, my_header, my_file_details_list, ntfy)
    ntfy.display_message("Completed Step 5")
    # tell SleepHQ to process the files
    ntfy.display_message("Starting Step 6: Processing Files")
    process_imported_files(my_import_id, my_header, ntfy)
    ntfy.display_message("Completed Step 6")
    time.sleep(10)

    # check the status for the file processing
    ntfy.display_message("Starting Step 7: Check processing status")
    check_imported_files(my_import_id, my_header,ntfy)
    ntfy.display_message("Completed Step 7.\nData Import Process is complete.")
