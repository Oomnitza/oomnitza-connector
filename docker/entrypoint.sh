#!/bin/bash

set -e

# Function to display help
display_help() {
    echo "Usage: $0 <role>"
    echo
    echo "Roles:"
    echo "  managed                                    - Start the cloud connector in managed mode"
    echo "  upload <name> [--testmode] [--save_data]   - Perform local connector upload"
    echo
    echo "Name:"
    echo "  The connector to utilize"
    echo
    echo "Args:"
    echo "  --testmode                                 - Skip publishing new records or updates to Oomnitza"
    echo "  --save_data                                - Store incoming records and outgoing records"
    echo
    echo "Example:"
    echo "  $0 managed"
    echo "  $0 upload ldap --testmode"
    echo ""
    exit 1
}

# Check if no arguments are provided
if [ $# -eq 0 ]; then
    display_help
fi

ROLE=$1
CONNECTOR=$2
ARGS=$3

# Validate arguments
if [ "$ROLE" != "managed" ] && [ "$ROLE" != "upload" ]; then
    echo "Invalid role: $ROLE"
    display_help
fi

# Use envsubst to replace variables in the template
envsubst < /docker/config.ini.envsubst > /app/config.ini

# Execute the application command based on the role
cd /app
if [ "$ROLE" == "managed" ]; then
    PYTHONPATH=. exec python connector.py --ini /app/config.ini
elif [ "$ROLE" == "upload" ]; then
    PYTHONPATH=. exec python connector.py --ini /app/config.ini upload $CONNECTOR $ARGS
fi
