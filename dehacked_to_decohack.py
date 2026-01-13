import sys
import re

class DehackedParser:
    def __init__(self, lines):
        self.lines = lines

        self.things = {}
        self.frames = {}
        self.codeptrs = {}

    def get_line(self):
        return self.lines[0].strip()

    def consume_line(self):
        return self.lines.pop(0).strip()

    def parse_prop_list(self, obj):
        while True:
            line = self.consume_line()
            if line == '':
                break

            prop = line.split('=')
            prop = [p.strip() for p in prop]
            obj[prop[0]] = prop[1]

    def parse_thing(self):
        m = re.match('Thing ([0-9]+) \(([^)]+)\)', self.get_line())
        if not m:
            raise Exception('Bad thing: {}'.format(self.get_line()))

        thing = {}
        thing_num = int(m.group(1))
        thing['name'] = m.group(2)

        self.consume_line()
        self.parse_prop_list(thing)
        self.things[thing_num] = thing

    def parse_frame(self):
        m = re.match('Frame ([0-9]+)', self.get_line())
        if not m:
            raise Exception('Bad frame: {}'.format(self.get_line()))

        frame = {}
        frame_num = int(m.group(1))

        self.consume_line()
        self.parse_prop_list(frame)
        self.frames[frame_num] = frame

    def parse_codeptr(self):
        self.consume_line()
        while True:
            line = self.consume_line()
            if line == '':
                break

            prop = line.split('=')
            prop = [p.strip() for p in prop]
            if prop[1] == 'NULL':
                continue

            frame_num = int(prop[0].split(' ')[1])

            self.codeptrs[frame_num] = 'A_{}'.format(prop[1])

    def parse(self):
        parsers = {
            # 'Patch File for DeHackEd'	: self.parse_header,
            'Thing'                     : self.parse_thing,
            'Frame'                     : self.parse_frame,
            '[CODEPTR]'                 : self.parse_codeptr,
        }

        while len(self.lines):
            line = self.get_line()

            if line.startswith('#') or line == '':
                # Skip comments/blank lines
                lines.pop(0)
                continue

            parsed = False
            for k, v in parsers.items():
                if line.startswith(k):
                    v()
                    parsed = True
                    break

            if not parsed:
                self.consume_line()

if __name__ == '__main__':
    lines = open(sys.argv[1], 'r').readlines()

    parser = DehackedParser(lines)
    parser.parse()

    print(parser.codeptrs)
