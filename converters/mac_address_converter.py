import logging
import re
logger = logging.getLogger("converters/mac_address")


def converter(mac_address, **kwargs):
    """
    Cnovert to colon based MAC address
    :param mac_address: field value
    :return: string with capitalized first letter
    """

    if isinstance(mac_address, str):
        mac_address = mac_address.replace('-', ':').upper()
        if "0X" in mac_address: # DDS MAC Address format
            mac_address = mac_address.replace('0X', '')
            mac_address = ':'.join(mac_address[i:i + 2] for i in range(0, 12, 2))

        if ':' in mac_address:
            first_octet = mac_address.split(':')[0]
            second_char = first_octet[-1].upper()
            """
            There are 4 ranges of Locally Administered Address Ranges that can be used on a local network:
                x2-xx-xx-xx-xx-xx
                x6-xx-xx-xx-xx-xx
                xA-xx-xx-xx-xx-xx
                xE-xx-xx-xx-xx
            """
            if second_char == "2" or second_char == "6" or second_char == "A" or second_char == "E":
                logger.warning(
                    "%s is not a valid MAC address. It is a locally administered MAC address. The MAC address has been discarded.",
                    mac_address)
                return ""
            elif mac_address.startswith("00:50:56:"): #VMWARE Range
                logger.warning(
                    "%s is not a valid MAC address. It is a VMware MAC address. The MAC address has been discarded.",
                    mac_address)
                return ""

        elif ':' not in mac_address:
            try:
                mac_address = re.sub('[.:-]', '', mac_address).upper()  # remove delimiters and convert to lower case
                mac_address = ''.join(mac_address.split())  # remove whitespaces
                assert len(mac_address) == 12  # length should be now exactly 12 (eg. 008041aefd7e)
                assert mac_address.isalnum()  # should only contain letters and numbers
                # convert mac in canonical form (eg. 00:80:41:ae:fd:7e)
                output = ":".join(["%s" % (mac_address[i:i + 2]) for i in range(0, 12, 2)])
                return converter(output, **kwargs)
            except:
                logger.error("Unable to convert MAC %s. Setting to empty string.", mac_address, exc_info=True)
                return ""
    #     else:
    #         device['MacAddress'] = ':'.join(format(s, '02x') for s in bytes.fromhex(mac_address)).upper()

    if mac_address:
        return str(mac_address).upper()

    logger.error("Invalid MAC address format %s. Setting to empty string.", mac_address)
    return ""
