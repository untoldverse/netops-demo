from ncclient import manager
import xmltodict
import json
import getpass
import pandas
import sys
#<rpc-reply xmlns:junos="http://xml.juniper.net/junos/21.1R0/junos">
VM_MD5_SUM = "924aa5c91e1fae2b2015519dfc9be633"
OS_MD5_SUM = "30aba39958b2578751437027a1b800d4"

VM_PACKAGE = "junos-vmhost-install-mx-x86-64-23.4R2-S4.11.tgz"
OS_PACKAGE = "os-package.tgz"

def commit_config(m:manager)-> str:
    """
    Commit the config
    Return pass or error
    """


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
def update_bgp_neighbors(m: manager, state: str) -> None:
    """
    Takes in the netconf session and desired state and updates BGP neighbors
    """

    bgp_neighbors = get_bgp_neighbors(m)
    for neighbor in bgp_neighbors:
        #Junos will append the TCP Port in the address, so we split the address via + and take the first occurance
        if "+" in neighbor['peer-address']:
            neighbor['peer-address'] = neighbor['peer-address'].split("+")[0]
        m.rpc("")
    
    #Print the 
    print(pandas.DataFrame(get_bgp_neighbors(m)))
    

def get_interface_stats(m: manager):
    pass

def set_chassis_interface(m: manager) -> str:
    """
    Set the interface config to have all 4 100gs and disable the 10g ports

    Returns and ok or error 
    """

def get_dhcp_time(m: manager) -> None:
    current_dhcp_bindings = "<get-dhcp-server-binding-information></get-dhcp-server-binding-information>"
    current_dhcp_time = """
    <get-config>
        <source>
            <running/>
        </source>
        <filter>
            <configuration>
                <access>
                    <protocol-attributes>
                        <name>default-dhcp</name>
                    </protocol-attributes>
                </access>
            </configuration>
        </filter>

    </get-config>
    """
    #print(pandas.DataFrame(xmltodict.parse(m.rpc(current_dhcp_time).data_xml)['rpc-reply']['data']['configuration']['access']['protocol']))
    print(pandas.DataFrame(xmltodict.parse(m.rpc(current_dhcp_bindings).data_xml)['rpc-reply']['dhcp-server-binding-information']['dhcp-binding']))
def update_dhcp_timers(m: manager, time: int) -> str:
    pass

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
    with manager.connect(
        username = "josh.mommers",
        password = getpass.getpass("Enter password: "),
        host = "nyc-eq9-ip-1",
        device_params = {'name':'junos'},
        hostkey_verify=False,
        look_for_keys=False,
        allow_agent=False,
    ) as m:

        bgp_neighbors = get_bgp_neighbors(m)
        print(pandas.DataFrame(bgp_neighbors))
        get_storage(m)
        get_dhcp_time(m)
        #with open("mx204.json","w") as f:
        #    f.write(json.dumps(bgp_neighbors,indent=2))
    

if __name__ == "__main__":
    main()