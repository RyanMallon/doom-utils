import sys

from decohack_writer import DecohackWriter
from info_parser import InfoParser
from info import Info

if __name__ == '__main__':
    info_filename = sys.argv[1]

    info = Info()
    info_parser = InfoParser(info_filename)
    info_parser.parse(info)

    writer = DecohackWriter(info)
    writer.output_mobj(info.get_mobj_by_name(sys.argv[2]))
