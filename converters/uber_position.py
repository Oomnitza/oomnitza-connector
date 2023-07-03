

def converter(field, record, value, params):
    """
    A user in Uber's LDAP system is a contractor or employee based on email address.

    :param value: field value
    :return: 'Contractor' or 'Employee'
    """
    if value and value.endswith("@uber.com"):
        return "Employee"
    return "Contractor"
