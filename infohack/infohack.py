import argparse
import sys

from decohack_writer import DecohackWriter
from info_parser import InfoParser
from info import Info

if __name__ == '__main__':
    info_filename = sys.argv[1]

    ap = argparse.ArgumentParser(prog='infohack',
                                 description='Tool for generating Decohack from info.c/dehacked')
    ap.add_argument('info_filename',
                    help='Source info.c file (use chocolate-doom')
    ap.add_argument('-d', '--deh',
                    help='Dehacked patch file to apply')
    ap.add_argument('-t', '--things', nargs='*', default=[],
                    help='Names of things to output')
    args = ap.parse_args()

    info = Info()
    info_parser = InfoParser(args.info_filename)
    info_parser.parse(info)

    writer = DecohackWriter(info)

    if len(args.things) == 0:
        mobj_list = info.mobjs
    else:
        mobj_list = [info.get_mobj_by_name(x) for x in args.things]

    for mobj in mobj_list:
        writer.output_mobj(mobj)
