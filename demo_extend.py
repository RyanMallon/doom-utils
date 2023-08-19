#
# Very basic script to extend the length of a demo so the map
# end screen stays around longer. Useful for doing post commentary.
#
#   python3 demo_extend.py <infile> <outfile> <minutes>
#
import struct
import sys

if __name__ == '__main__':
    infile = sys.argv[1]
    outfile = sys.argv[2]
    tics = int(sys.argv[3]) * 35 * 60

    lump = open(infile, 'rb').read()
    offset = lump.find(b'\x80PWAD', 0xd)
    if offset == -1:
        if lump[:-1] == b'\x80':
            offset = len(lump) - 1
    if offset == -1:
        print('Cannot find demo end marker')
        sys.exit(1)

    head = lump[:offset]
    tail = lump[offset:]

    new_lump = head
    for _ in range(tics):
        new_lump += '\x00\x00\x00\x00'.encode()
    new_lump += tail

    open(outfile, 'wb').write(new_lump)
