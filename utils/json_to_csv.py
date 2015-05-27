
import os
import argparse
import csv
import json

def main(args):
    dir = os.path.abspath(args.directory)
    if not os.path.isdir(dir):
        print "Error: %r is not a valid directory." % dir
        return

    with open(os.path.join(dir, '0.json')) as fields_file:
        fields = json.load(fields_file).keys()

    outfile = os.path.abspath(args.outfile)
    with open(outfile, 'wb') as outfile:
        writer = csv.DictWriter(outfile, fields)
        writer.writeheader()

        for file in os.listdir(dir):
            if file.endswith(".json"):
                with open(os.path.join(dir, file), 'rb') as data_file:
                    data = json.load(data_file)
                    data = dict((k, v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in data.iteritems())
                    writer.writerow(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", help="The directory containing the source *.json files.")
    parser.add_argument("outfile", help="The file to output.")

    args = parser.parse_args()

    main(args)
