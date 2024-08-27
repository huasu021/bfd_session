from jnpr.junos import Device
from lxml import etree

def main():
    dev = Device()
    # Opens a connection
    dev.open()

    # Fetch FPC slot information
    fpc_info = dev.rpc.get_fpc_information()

    # Extract FPC slot numbers where the state is "Online"
    fpc_slots = []
    for fpc in fpc_info.xpath("//fpc"):
        slot = fpc.find("slot").text
        state = fpc.find("state").text
        if state == "Online":
            fpc_slots.append(slot)

    # Fetch extensive BFD session information
    bfd_session_ext = dev.rpc.get_bfd_session_information(extensive=True)
    
    # Parse the XML to find all "Session ID" and "session-neighbor" values
    sessions = []
    for session in bfd_session_ext.xpath("//bfd-session"):
        session_id_elem = session.find(".//no-refresh")
        session_neighbor_elem = session.find(".//session-neighbor")
        
        if session_id_elem is not None and "Session ID:" in session_id_elem.text:
            session_id = session_id_elem.text.split("Session ID: ")[-1].strip()
            session_neighbor = session_neighbor_elem.text if session_neighbor_elem is not None else "Unknown"
            sessions.append((session_id, session_neighbor))

    # Iterate over each session and each FPC slot
    for session_id, session_neighbor in sessions:
        for slot in fpc_slots:
            target = 'fpc{}'.format(slot)
            bfd_session_shell = dev.rpc.request_pfe_execute(target=target, command='show pfe bfd id {}'.format(session_id))
            
            # Convert the bfd_session_shell element to a string
            bfd_session_shell_str = etree.tostring(bfd_session_shell, pretty_print=True).decode()

            # Check the content for specific strings and include session-neighbor in the output
            if "Session Status : DOWN" in bfd_session_shell_str:
                print("Session ID {} (Neighbor: {}) on {} is down".format(session_id, session_neighbor, target))
            elif "Session DB doesn't exist" in bfd_session_shell_str:
                print("Session ID {} (Neighbor: {}) on {} does not exist".format(session_id, session_neighbor, target))
            else:
                print("Session ID {} (Neighbor: {}) on {}: unknown status".format(session_id, session_neighbor, target))

    dev.close()

if __name__ == '__main__':
    main()
