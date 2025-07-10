from ncclient import manager
import xmltodict
import json
import getpass
import pandas
import sys
import jinja2
import logging
import time
import datetime
#<rpc-reply xmlns:junos="http://xml.juniper.net/junos/21.1R0/junos">
VM_MD5_SUM = "924aa5c91e1fae2b2015519dfc9be633"
OS_MD5_SUM = "30aba39958b2578751437027a1b800d4"

VM_PACKAGE = "junos-vmhost-install-mx-x86-64-23.4R2-S4.11.tgz"
OS_PACKAGE = "os-package.tgz"


def rollback_config(m: manager)-> None:
    """
    Rollback changes incase of a failure
    """
    print("Rolling Back changes")
    m.rollback()

def commit_config(m:manager)-> str:
    """
    Commit the config
    Return pass or error
    """
    print("Validating results")
    validate_results = m.validate()
    logging.info(validate_results)
    print("""
    Configuration Changes: 

    """,xmltodict.parse(m.compare_configuration().data_xml)['rpc-reply']['configuration-information']['configuration-output']
    )
    return list(xmltodict.parse(m.commit().data_xml)['rpc-reply'].keys())[1]

def get_bgp_neighbors(m: manager) -> list:
    """
    Retrieve all BGP Neighbors and their state
    :param: :m: Active Netconf Session
    """
    bgp_neighbors = []
    bgp_filter = "<get-bgp-neighbor-information></get-bgp-neighbor-information>"
    for neighbor in xmltodict.parse(m.rpc(bgp_filter).data_xml)['rpc-reply']['bgp-information']['bgp-peer']:
        bgp_neighbors.append(
            {
                "peer-address": neighbor['peer-address'],
                "peer-group": neighbor['peer-group'],
                "peer-state": neighbor['peer-state'],
                #"local-interface-name": neighbor['local-interface-name'] #Somehow the key isn't there despite in json return
            }
        )
    return bgp_neighbors
def update_bgp_neighbors(m: manager, state: str, change_number: str) -> None:
    """
    Takes in the netconf session and desired state and updates BGP neighbors

    Shutdown will update the groups with Graceful-Shutdown then wait 5 minutes before shutting the connection 
    """
    print("BGP Neighbor States before changes")
    bgp_neighbors = get_bgp_neighbors(m)
    print("******************")
    print(pandas.DataFrame(bgp_neighbors))
    if state.lower() == "graceful":
        try: 
            commands = []
            print("Enabling Graceful-Shudown to all groups") 
            for neighbor in bgp_neighbors:
                #Junos will append the TCP Port in the address, so we split the address via + and take the first occurance
                if neighbor['peer-address'].find('+') != -1:
                    neighbor['peer-address'] = neighbor['peer-address'].split("+")[0]
                    #set rpc config
                bgp_config_template = "set protocols bgp group {{ group }} graceful-shutdown sender local-preference 0"
                commands.append(jinja2.Template(bgp_config_template).render(group=neighbor['peer-group']))

            m.load_configuration(
                action="set",
                config=commands
            )
            print("Commiting changes: ",commit_config(m))
            ##
            print(
                """
                PLEASE ALLOW 15 MINUTES FOR TRAFFIC TO DRAIN BEFORE SHUTTING DOWN THE BGP NEIGHBORS
                """
            ,
            )
        except Exception as e:
            print(e)
            rollback_config
    elif state.lower() == "disabled":
        try:
            commands = []
            for neighbor in bgp_neighbors:
                #Junos will append the TCP Port in the address, so we split the address via + and take the first occurance
                if neighbor['peer-address'].find('+') != -1:
                    neighbor['peer-address'] = neighbor['peer-address'].split("+")[0]
                #Notification Message has a character limit
                bgp_config_template = "set protocols bgp group {{ group }} shutdown notify-message {{ change }}"
                commands.append(jinja2.Template(bgp_config_template).render(group=neighbor['peer-group'],change=change_number))
            m.load_configuration(
                action="set",
                config=commands
            )
            print("Commiting changes: ",commit_config(m))
        except Exception as e:
                print(e)
    elif state.lower() == "enabled":
        try:
            print("Removing Graceful shutdown")
            for neighbor in bgp_neighbors:
                #Junos will append the TCP Port in the address, so we split the address via + and take the first occurance
                if neighbor['peer-address'].find('+') != -1:
                    neighbor['peer-address'] = neighbor['peer-address'].split("+")[0]
                    #set rpc config
                bgp_config_template = "delete protocols bgp group {{ group }} graceful-shutdown"
                        
                try:
                    m.load_configuration(
                        action="set",
                        config=jinja2.Template(bgp_config_template).render(group=neighbor['peer-group']), 
                        format="text"
                    )
                finally:
                    continue
        except Exception as e:
            print(e)
            rollback_config(m)    
        
        try:
            print("Removing BGP shutdown")    
            for neighbor in bgp_neighbors:
                #Junos will append the TCP Port in the address, so we split the address via + and take the first occurance
                if neighbor['peer-address'].find('+') != -1:
                    neighbor['peer-address'] = neighbor['peer-address'].split("+")[0]
                    #set rpc config
                bgp_config_template = "delete protocols bgp group {{ group }} shutdown"
                try:
                    m.load_configuration(
                        action="set",
                        config=jinja2.Template(bgp_config_template).render(group=neighbor['peer-group']),
                        format="text"
                    )
                finally:
                    continue
            print("Commiting changes: ",commit_config(m))

        except Exception as e:
                print(e)
                rollback_config(m)
    #Sleep for BGP changes (Especially after removing shutdown)
    print("Waiting for BGP Changes: ")
    time.sleep(10)
    print("Post Change BGP Neighor Status:")
    print(pandas.DataFrame(get_bgp_neighbors(m)))

def get_interface_status(m: manager):
    print(
        xmltodict.parse(m.command("show interface terse",format="text").data_xml)['rpc-reply']['output']
    )

def set_chassis_interface(m: manager) -> None:
    """
    Set the interface config to have all 4 100gs and disable the 10g ports
    Returns and ok or error 
    """
    interface_commands = [
        "set chassis fpc 0 pic 0 port 2 speed 100g",
        "set chassis fpc 0 pic 0 port 3 speed 100g",
        "delete chassis fpc 0 pic 1 port 0",
        "delete chassis fpc 0 pic 1 port 1",
        "delete chassis fpc 0 pic 1 port 2",
        "delete chassis fpc 0 pic 1 port 3",
        "delete chassis fpc 0 pic 1 port 4",
        "delete chassis fpc 0 pic 1 port 5",
        "delete chassis fpc 0 pic 1 port 6",
        "delete chassis fpc 0 pic 1 port 7",
        "set chassis fpc 0 pic 1 number-of-ports 0"
    ]
    print("Pre Chassis Interface Status: ", get_interface_status(m))
    try:
        logging.info(
            m.load_configuration(
                action="set",
                config = interface_commands,
                format="text"
            )
        )
        print("Commiting Chassis Interface changes: ",commit_changes(m))

        get_interface_status(m)

    except Exception as e:
        print(e)
        rollback_config(m)


def get_dhcp_time(m: manager) -> None:
    current_dhcp_bindings = "<get-dhcp-server-binding-information></get-dhcp-server-binding-information>"

    print(pandas.DataFrame(xmltodict.parse(m.rpc(current_dhcp_bindings).data_xml)['rpc-reply']['dhcp-server-binding-information']['dhcp-binding']))

def update_dhcp_timers(m: manager, time: int) -> None:
    """
    Set DHCP lease time 
    """
    print("Current DHCP lease time configuration: ")
    print(xmltodict.parse(m.command("show access protocol-attributes default-dhcp dhcp maximum-lease-time").data_xml))['rpc-reply']['output']
    dhcp_config_template = "set access protocol-attributes default-dhcp dhcp maximum-lease-time {{ time }}"
    try:
        m.load_configuration(
            action="set",
            config=jinja2.Template(dhcp_config_template).render(time=time),
            format="text"
        )
        print("Commiting DHCP maximum lease time change: ", commit_config(m))
    except Exception as e:
        print(e)
        rollback_config(m)
        
def get_storage(m: manager) -> None:
    storage_filter = "<get-system-storage></get-system-storage>"
    results = xmltodict.parse(m.rpc(storage_filter).data_xml)['rpc-reply']['system-storage-information']['filesystem']
    print(pandas.DataFrame(results))
    #for filesystems in results:
    #    if "/dev/gpt/var" in filesystems['filesystem-name']:
    #        if filesystems["available-blocks"]

def upload_image(m: manager, location: str) -> str:
    pass

def check_image(m: manager) -> None:
    """
    Check VM and OS Package's MD5 Hash
    """

    vm_pkg_found = False
    os_pkg_found = False
    file_filter = "<file-list><path>/var/tmp</path></file-list>"
    results = xmltodict(m.rpc(file_filter).dataxml)['rpc-reply']
    for file in results['directory-list']['directoriy']:
        if VM_PACKAGE in file:
            vm_pkg_found = True
            if VM_MD5_SUM in xmltodict.parse(
                m.rpc("<get-checksum-information><path>/var/tmp/"+VM_PACKAGE+"</path></get-checksum-information>")
            ):
                print("VM MD5 Checksum matches")
        elif OS_PACKAGE in file:
            os_pkg_found = True
            if OS_MD5_SUM in xmltodict.parse(
                m.rpc("<get-checksum-information><path>/var/tmp/"+OS_PACKAGE+"</path></get-checksum-information>")
            ):
                print("OS Package MD5 Checksum matches")
    if vm_pkg_found:
        pass
    elif os_pkg_found:
        pass
    else:
        print("Missing Packages, please upload")
        sys.exit()

def main():
    """
    MX204 script
    """
    #Decide wither to set BGP graceful-shutdown, shutdown, or enable - Seperate as 3 choices as graceful-shutdown should be seperate to allow traffic to drain
    state = input("BGP State graceful/enabled/disabled: ")
    if state == "disabled":
        change_number = input("Enter CC number for shutdown notification: ") or "CC2-Testing"
    else:
        change_number = "None"

    try:
        with manager.connect(
            username = input("Username: "),
            password = getpass.getpass("Password: "),
            host = input("Host: ") or "66.129.235.201", #Juniper vLabs test
            port = input("Port (Leave blank for default 830): ") or 830,
            device_params = {'name':'junos'},
            hostkey_verify=False,
            look_for_keys=False,
            allow_agent=False,
            timeout=30
        ) as m:

           
            print("Checks")
            get_storage(m)

            #Set DHCP Lease time to 3600 work is being done; else reset the timer back to 2 mins
            if state.lower() == "disabed" or state.lower() == "graceful":
                update_dhcp_timers(m, 3600)
            else:
                update_dhcp_timers(m, 120)
            
            update_bgp_neighbors(m, state,change_number)

            """
            TODO 
            Call Chassis Interface config if BGP Neighbors are shut and the 4 port 100g are not configured
            Call Software Add - Reboot Done Manually
            """
            print("Please reboot manually")
        
    except Exception as e:
        print("Failed to connect")
if __name__ == "__main__":
    main()