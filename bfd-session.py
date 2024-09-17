"""
*  Copyright (c) 2016  Juniper Networks. All Rights Reserved.
*
*  YOU MUST ACCEPT THE TERMS OF THIS DISCLAIMER TO USE THIS SOFTWARE
*
*  JUNIPER IS WILLING TO MAKE THE INCLUDED SCRIPTING SOFTWARE AVAILABLE TO YOU
*  ONLY UPON THE CONDITION THAT YOU ACCEPT ALL OF THE TERMS CONTAINED IN THIS
*  DISCLAIMER. PLEASE READ THE TERMS AND CONDITIONS OF THIS DISCLAIMER
*  CAREFULLY.
*
*  THE SOFTWARE CONTAINED IN THIS FILE IS PROVIDED "AS IS." JUNIPER MAKES NO
*  WARRANTIES OF ANY KIND WHATSOEVER WITH RESPECT TO SOFTWARE. ALL EXPRESS OR
*  IMPLIED CONDITIONS, REPRESENTATIONS AND WARRANTIES, INCLUDING ANY WARRANTY
*  OF NON-INFRINGEMENT OR WARRANTY OF MERCHANTABILITY OR FITNESS FOR A
*  PARTICULAR PURPOSE, ARE HEREBY DISCLAIMED AND EXCLUDED TO THE EXTENT
*  ALLOWED BY APPLICABLE LAW.
*
*  IN NO EVENT WILL JUNIPER BE LIABLE FOR ANY LOST REVENUE, PROFIT OR DATA, OR
*  FOR DIRECT, SPECIAL, INDIRECT, CONSEQUENTIAL, INCIDENTAL OR PUNITIVE
*  DAMAGES HOWEVER CAUSED AND REGARDLESS OF THE THEORY OF LIABILITY ARISING
*  OUT OF THE USE OF OR INABILITY TO USE THE SOFTWARE, EVEN IF JUNIPER HAS
*  BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.

This script is triggered by an event policy on the Junos device when a BFD session
transitions to the "up" state. The following configuration is required on the Junos device:

Copy this bfd_session.py into /var/db/scripts/event/
cli config:

set event-options policy bfd-session events BFDD_TRAP_SHOP_STATE_UP
set event-options policy bfd-session within 60 trigger on
set event-options policy bfd-session within 60 trigger 1
set event-options policy bfd-session then event-script bfd-session.py
set event-options policy bfd-session-trap events SYSTEM
set event-options policy bfd-session-trap attributes-match SYSTEM.message matches "Session ID.*(is down|does not exist)"
set event-options policy bfd-session-trap then raise-trap
set event-options event-script file bfd-session.py python-script-user JNPR-RW
set system scripts language python3
set system scripts synchronize

The script checks the status of BFD sessions and generates syslog messages accordingly.
"""
import time
from jnpr.junos import Device
from lxml import etree
import jcs

# Delay the script execution by 10 seconds to wait for flapped bfd session be stablize.
time.sleep(10)

# Open a connection to the device
dev = Device()
dev.open()

# Fetch extensive BFD session information
bfd_session_ext = dev.rpc.get_bfd_session_information(extensive=True)

# Extract "Session ID" and "session-neighbor" values, excluding session_id = '0'
sessions = []
for session in bfd_session_ext.xpath("//bfd-session"):
    session_id_elem = session.xpath(".//no-refresh[contains(text(),'Session ID')]")
    session_neighbor_elem = session.find(".//session-neighbor")
    
    if session_id_elem:
        session_id = session_id_elem[0].text.split("Session ID: ")[-1].strip()
        
        # Exclude session_id = '0'
        if session_id != '0':
            session_neighbor = session_neighbor_elem.text if session_neighbor_elem is not None else "Unknown"
            sessions.append((session_id, session_neighbor))

# Fetch FPC slot information
fpc_info = dev.rpc.get_fpc_information()

# Extract FPC slot numbers where the state is "Online"
fpc_slots = []
for fpc in fpc_info.xpath("//fpc"):
    slot = fpc.find("slot").text
    state = fpc.find("state").text
    if state == "Online":
        fpc_slots.append(slot)

# Iterate over each session and each FPC slot
for session_id, session_neighbor in sessions:
    for slot in fpc_slots:
        target = 'fpc{}'.format(slot)
        bfd_session_shell = dev.rpc.request_pfe_execute(target=target, command='show pfe bfd id {}'.format(session_id))
        
        # Convert the bfd_session_shell element to a string
        bfd_session_shell_str = etree.tostring(bfd_session_shell, pretty_print=True).decode()

        # Construct the message based on the session status
        if "Session Status : DOWN" in bfd_session_shell_str:
            message = "Session ID {} (Neighbor: {}) on {} is down".format(session_id, session_neighbor, target)
        elif "Session DB doesn't exist" in bfd_session_shell_str:
            message = "Session ID {} (Neighbor: {}) on {} does not exist".format(session_id, session_neighbor, target)
        else:
            message = "Session ID {} (Neighbor: {}) on {} is up".format(session_id, session_neighbor, target)
        
        # Print the message
        print(message)
        
        # Generate a syslog with the message
        jcs.syslog("pfe.warning", message)

# Close the device connection
dev.close()
