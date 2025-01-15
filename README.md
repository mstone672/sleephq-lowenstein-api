This is an API for uploading Lowenstein APAP data files via the API to SleepIQ.  
  
To use this script:  
 - recommended to use a virtual python environment (e.g. python -m venv sleepiq-api).  
 - Install the required python modules:  pip install requests python-dotenv  
 -  Copy the uploader file to your desired location.  
 -  Upon first run of the script, it will walk you through asking for the required information and creating. 
    a .env file in the same location as the script.  
 
Verison History:  
14-Jan-2025 version 1.0.3
   - Fixed error when trying to send ntfy push notification.   
   - Added local logging for the script.  Max file size is 1MB with 3 log file rotation
                          
14-Jan-2025 version 1.0.2 - Added ntfy nortifications; Still working on resolving one bug with notifications.  
   
10-Jan-20225 Version 1.0.1 - fixed some typos. 

07-Jan-2025 Version 1:  First version
