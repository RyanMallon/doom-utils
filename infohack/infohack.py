import argparse
import sys

from dehacked_parser import DehackedParser
from dehacked_patch import DehackedPatch
from decohack_writer import DecohackWriter
from info_parser import InfoParser
from info import Info

from constants import DoomConstants

if __name__ == '__main__':
    info_filename = sys.argv[1]

    ap = argparse.ArgumentParser(prog='infohack',
                                 description='Tool for generating Decohack from info.c/dehacked')
    ap.add_argument('src_dir',
                    help='Doom source directory (use chocolate-doom/src/doom')
    ap.add_argument('-d', '--deh',
                    help='Dehacked patch file to apply')
    ap.add_argument('-D', '--debug-deh-patch', action='store_true',
                    help='Debug logs for applying dehacked patches')
    ap.add_argument('-t', '--things', nargs='*', default=[],
                    help='Names of things to output')
    ap.add_argument('-n', '--no-decohack', action='store_true',
                    help='Do not output Decohack')
    args = ap.parse_args()

    # Parse the info.c to build the initial states, mobjs, etc
    info = Info(DoomConstants)
    info_parser = InfoParser(args.src_dir)
    info_parser.parse(info)

    # Optionally apply a dehacked patch
    if args.deh:
        deh_patch = DehackedPatch(info, args)
        deh_parser = DehackedParser(open(args.deh, 'r').readlines(), deh_patch)
        deh_parser.parse()
        deh_patch.patch()

    if not args.no_decohack:
        writer = DecohackWriter(info)

        if len(args.things) == 0:
            mobj_list = info.mobjs
        else:
            mobj_list = [info.get_mobj_by_name(x) for x in args.things]

        for mobj in mobj_list:
            writer.output_mobj(mobj)
